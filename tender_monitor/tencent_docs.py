"""腾讯在线文档客户端（基于腾讯文档开放平台 OpenAPI v3）。

官方文档：https://docs.qq.com/open/document/app/
- OAuth 刷新令牌：GET https://docs.qq.com/oauth/v2/token
- 读取范围：      GET  /openapi/spreadsheet/v3/files/{fileId}/{sheetId}/{range}
- 批量更新：      POST /openapi/spreadsheet/v3/files/{fileId}/batchUpdate  (updateRangeRequest)

鉴权头：Access-Token / Client-Id / Open-Id
"""
import logging
import requests

from .config import config
from .store import TABLE_COLUMNS, record_to_table_row

log = logging.getLogger(__name__)

BASE = "https://docs.qq.com"
OAUTH_TOKEN_URL = "https://docs.qq.com/oauth/v2/token"

# A1 表示法列字母（16 列 A..P）
COL_LETTERS = [chr(ord("A") + i) for i in range(len(TABLE_COLUMNS))]
LAST_COL = COL_LETTERS[-1]           # "P"
LINK_COL_INDEX = TABLE_COLUMNS.index("原文链接")  # 用于生成超链接单元格

# 单次读取行数上限
PAGE_ROWS = 650


class TencentDocsClient:
    """腾讯文档客户端，支持按 file_id/sheet_id 操作不同表格。"""

    def __init__(self, file_id=None, sheet_id=None):
        self.file_id = file_id or config.TENCENT_FILE_ID
        self.sheet_id = sheet_id or config.TENCENT_SHEET_ID
        self.client_id = config.TENCENT_CLIENT_ID
        self.client_secret = config.TENCENT_CLIENT_SECRET
        self.refresh_token = config.TENCENT_REFRESH_TOKEN
        self.access_token = None
        self.open_id = None

    def use_table(self, file_id, sheet_id="000001"):
        """切换到另一张表格。"""
        self.file_id = file_id
        self.sheet_id = sheet_id

    # ---------- OAuth ----------
    def refresh(self):
        """用 refresh_token 换取 access_token。返回新的 refresh_token（会轮换）。"""
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        resp = requests.get(OAUTH_TOKEN_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"刷新令牌失败: {data}")
        self.access_token = data["access_token"]
        self.open_id = data.get("user_id") or data.get("openid") or ""
        new_refresh = data.get("refresh_token", self.refresh_token)
        self.refresh_token = new_refresh
        log.info("腾讯文档 access_token 刷新成功 open_id=%s", self.open_id)
        return new_refresh

    def _headers(self):
        return {
            "Access-Token": self.access_token,
            "Client-Id": self.client_id,
            "Open-Id": self.open_id,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _ok(data):
        return data.get("ret", data.get("code", 0)) in (0, None)

    # ---------- 读取 ----------
    def _read_range(self, a1_range):
        url = f"{BASE}/openapi/spreadsheet/v3/files/{self.file_id}/{self.sheet_id}/{a1_range}"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not self._ok(data):
            raise RuntimeError(f"读取失败 {a1_range}: {data}")
        grid = (data.get("data") or {}).get("gridData") or {}
        return grid.get("rows") or []

    @staticmethod
    def _cell_text(cell):
        cv = (cell or {}).get("cellValue") or {}
        if "text" in cv:
            return cv.get("text", "")
        if "link" in cv:
            return (cv.get("link") or {}).get("url", "")
        if "number" in cv:
            return str(cv.get("number", ""))
        return ""

    def read_all_rows(self):
        """读取整张表，返回 list[dict]（按表头列名）。首行为表头则跳过。"""
        all_rows = []
        start = 1
        while True:
            end = start + PAGE_ROWS - 1
            a1 = f"A{start}:{LAST_COL}{end}"
            rows = self._read_range(a1)
            if not rows:
                break
            for r in rows:
                vals = [self._cell_text(c) for c in (r.get("values") or [])]
                all_rows.append(vals)
            if len(rows) < PAGE_ROWS:
                break
            start = end + 1
        result = []
        for i, vals in enumerate(all_rows):
            if i == 0 and vals and vals[0] in ("序号", TABLE_COLUMNS[0]):
                continue
            row = {TABLE_COLUMNS[j]: (vals[j] if j < len(vals) else "")
                   for j in range(len(TABLE_COLUMNS))}
            result.append(row)
        return result

    def data_row_count(self):
        """已有数据行数（不含表头）。"""
        return len(self.read_all_rows())

    # ---------- 写入 ----------
    def _cell(self, col_name, value):
        if col_name == "原文链接" and value:
            return {"cellValue": {"link": {"url": value, "text": value}}}
        if col_name == "序号" and isinstance(value, (int, float)):
            return {"cellValue": {"number": value}}
        return {"cellValue": {"text": str(value)}}

    def ensure_header(self):
        """若首行不是表头则写入表头。"""
        rows = self._read_range(f"A1:{LAST_COL}1")
        first = rows[0]["values"][0] if rows and rows[0].get("values") else None
        first_text = self._cell_text(first) if first else ""
        if first_text != TABLE_COLUMNS[0]:
            self._update_range(0, [{c: c for c in TABLE_COLUMNS}])

    def _update_range(self, start_row, table_rows):
        """把若干行写入指定起始行（0-based）。table_rows 为 list[dict]。"""
        grid_rows = []
        for tr in table_rows:
            grid_rows.append({"values": [self._cell(c, tr.get(c, "")) for c in TABLE_COLUMNS]})
        body = {
            "requests": [{
                "updateRangeRequest": {
                    "sheetId": self.sheet_id,
                    "gridData": {"startRow": start_row, "startColumn": 0, "rows": grid_rows},
                }
            }]
        }
        url = f"{BASE}/openapi/spreadsheet/v3/files/{self.file_id}/batchUpdate"
        resp = requests.post(url, headers=self._headers(), json=body, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if not self._ok(data) and "responses" not in data:
            raise RuntimeError(f"写入失败: {data}")

    def append_records(self, records, start_index):
        """把新记录追加到表格底部（不覆盖已有数据）。

        start_index: 追加行的起始序号（如已有 23 行则从 24 开始）。
        """
        if not records:
            return 0
        self.ensure_header()
        existing = self.data_row_count()
        start_row = existing + 1              # 0-based：表头占第 0 行
        table_rows = [record_to_table_row(rec, start_index + i)
                      for i, rec in enumerate(records)]
        for i in range(0, len(table_rows), PAGE_ROWS):
            batch = table_rows[i:i + PAGE_ROWS]
            self._update_range(start_row + i, batch)
        log.info("腾讯文档(file=%s)追加 %d 行，起始行(0-based)=%d",
                 self.file_id, len(table_rows), start_row)
        return len(table_rows)
