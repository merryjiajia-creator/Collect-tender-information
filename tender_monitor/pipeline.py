"""主流程编排：搜索 → DeepSeek 解析 → 去重 → 写入在线表格（按类别拆分）→ 生成看板 → 企微推送。"""
import logging
import os
from datetime import datetime, timezone, timedelta

from .config import config
from .keywords import CATEGORIES, TENDER_QUALIFIERS
from . import search as search_mod
from . import llm
from . import wecom
from . import dashboard as dash
from .store import (load_store, save_store, seen_links, normalize_record)
from .tencent_docs import TencentDocsClient

log = logging.getLogger(__name__)

TOKEN_FILE = "data/tencent_refresh_token.txt"
MAX_LLM_CANDIDATES = int(os.environ.get("MAX_LLM_CANDIDATES", "120"))


def _bj_now():
    return datetime.now(timezone(timedelta(hours=8)))


def _parse_date(value):
    """尽力把各种格式的日期字符串解析为 date，失败返回 None。"""
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日", "%Y-%m-%d %H:%M",
                "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(value[:len(fmt) + 4], fmt).date()
        except ValueError:
            continue
    import re
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", value)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        except ValueError:
            return None
    return None


def filter_by_date(records, cutoff_str, run_date):
    """按收集规则过滤记录。"""
    cutoff = _parse_date(cutoff_str) or datetime(2026, 6, 1).date()
    kept, dropped_pub, dropped_deadline = [], 0, 0
    for rec in records:
        pub = _parse_date(rec.get("发布时间", ""))
        if pub is not None and pub < cutoff:
            dropped_pub += 1
            continue
        deadline = _parse_date(rec.get("截止时间", ""))
        if deadline is not None and deadline < run_date.date():
            dropped_deadline += 1
            continue
        kept.append(rec)
    log.info("日期过滤：发布时间早于 %s 丢弃 %d 条；截止已过期丢弃 %d 条；保留 %d 条",
             cutoff_str, dropped_pub, dropped_deadline, len(kept))
    return kept


def _load_refresh_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            tok = f.read().strip()
            if tok:
                return tok
    return config.TENCENT_REFRESH_TOKEN


def _save_refresh_token(tok):
    os.makedirs(os.path.dirname(TOKEN_FILE) or ".", exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(tok)


def collect_candidates():
    """按三类主题搜索，返回去重后的候选项 [(category, keywords, item)]。"""
    candidates = []
    seen_urls = set()
    for category, keywords in CATEGORIES.items():
        for kw in keywords:
            query = f"{kw} {TENDER_QUALIFIERS[0]} {TENDER_QUALIFIERS[1]}"
            for item in search_mod.search(query):
                url = (item.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append((category, keywords, item))
    log.info("搜索得到候选 %d 条（已按链接去重）", len(candidates))
    return candidates


def _write_category_table(client, category, records, store_len):
    """将某类别的新记录写入对应的独立在线表格。返回成功写入的记录数。"""
    file_id, sheet_id = config.category_file_config(category)
    if not file_id:
        log.warning("未配置 %s 的独立表格 file_id，跳过写入", category)
        return 0

    client.use_table(file_id, sheet_id)
    # 序号从该表格已有数据行数 + 1 开始
    existing = client.data_row_count()
    start_idx = existing + 1
    client.append_records(records, start_idx)
    return len(records)


def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_date = _bj_now().strftime("%Y-%m-%d")
    log.info("===== 招标监控任务开始 %s =====", run_date)

    # 1. 载入本地数据仓
    store = load_store(config.STORE_PATH)
    known = seen_links(store)
    log.info("已有记录 %d 条", len(store))

    # 2. 搜索候选
    candidates = collect_candidates()
    fresh = [(c, k, it) for (c, k, it) in candidates
             if (it.get("url") or "").strip() not in known]
    fresh = fresh[:MAX_LLM_CANDIDATES]
    log.info("待 DeepSeek 解析的新链接 %d 条", len(fresh))

    # 3. DeepSeek 解析 + 相关性过滤
    new_records = []
    new_links = set()
    for category, keywords, item in fresh:
        url = (item.get("url") or "").strip()
        if url in new_links:
            continue
        data = llm.extract_tender(category, keywords, item)
        if not data:
            continue
        rec = normalize_record(data, category)
        if not rec["资料来源"]:
            rec["资料来源"] = url
        new_records.append(rec)
        new_links.add(url)
        if len(new_records) >= config.MAX_NEW_PER_RUN:
            break
    log.info("解析出符合条件的新增招标 %d 条", len(new_records))

    # 3.5 按收集规则过滤
    new_records = filter_by_date(new_records, config.PUBLISH_DATE_CUTOFF, _bj_now())

    # 4. 写入腾讯在线表格 — 按类别拆分到独立表格
    sheet_url_all = config.SHEET_URL  # 全量汇总表链接（兼容旧配置）
    sheet_url_map = config.category_sheet_urls()

    if config.tencent_enabled() and new_records:
        try:
            client = TencentDocsClient()
            client.refresh_token = _load_refresh_token()
            rotated = client.refresh()
            _save_refresh_token(rotated)

            # 按类别分组，写入各自表格
            by_cat = {}
            for rec in new_records:
                by_cat.setdefault(rec.get("类别", ""), []).append(rec)

            for cat, recs in by_cat.items():
                _write_category_table(client, cat, recs, len(store))

            # 回读同步跟进信息（从各类别表格）
            _sync_followup_all(store + new_records, client)
        except Exception as e:
            log.warning("腾讯文档同步失败（保留本地数据，继续生成看板）：%s", e)
    else:
        log.warning("未配置腾讯文档参数或无新增记录，跳过在线表格写入")

    # 5. 合并到本地仓
    store = store + new_records
    save_store(config.STORE_PATH, store)

    # 6. 生成看板（按权限拆分：全部 + 物码 + 即时零售 + 到店）
    dash_dir = config.DASHBOARD_DIR
    updated_str = _bj_now().strftime("%Y-%m-%d %H:%M")
    dash_paths = {}

    # 全量看板（Ken）
    path_all = os.path.join(dash_dir, "index.html")
    dash.write_dashboard(store, path_all, updated=updated_str)
    dash_paths["all"] = path_all

    # 按类别拆分看板
    dash_cat_map = {"物码": "mon", "即时零售": "benny", "到店": "david"}
    for cat, slug in dash_cat_map.items():
        path_cat = os.path.join(dash_dir, f"{slug}.html")
        dash.write_dashboard(store, path_cat, updated=updated_str, categories=[cat])
        dash_paths[slug] = path_cat

    log.info("看板已生成：%s", ", ".join(dash_paths.values()))

    # 7. 企微推送（按权限分层）
    base_dash = config.DASHBOARD_URL.rstrip("/") if config.DASHBOARD_URL else ""
    dash_url_all = f"{base_dash}/index.html" if base_dash else ""
    dash_url_map = {"物码": f"{base_dash}/mon.html" if base_dash else "",
                    "即时零售": f"{base_dash}/benny.html" if base_dash else "",
                    "到店": f"{base_dash}/david.html" if base_dash else ""}
    wecom.push_daily(new_records, sheet_url_all, dash_url_all, dash_url_map, run_date)

    log.info("===== 任务结束：新增 %d 条，累计 %d 条 =====", len(new_records), len(store))
    return {"new": len(new_records), "total": len(store)}


def _sync_followup_all(records, client):
    """从所有分类表格回读跟进信息，按原文链接匹配覆盖本地记录。"""
    categories = ["物码", "即时零售", "到店"]
    all_rows = []
    for cat in categories:
        file_id, sheet_id = config.category_file_config(cat)
        if not file_id:
            continue
        try:
            client.use_table(file_id, sheet_id)
            rows = client.read_all_rows()
            all_rows.extend(rows)
        except Exception as e:
            log.warning("回读 %s 表格失败：%s", cat, e)

    by_link = {r.get("原文链接", "").strip(): r for r in all_rows if r.get("原文链接")}
    for rec in records:
        row = by_link.get(rec.get("资料来源", "").strip())
        if not row:
            continue
        for src_col, dst_key in [("跟进团队", "跟进团队"), ("跟进人", "跟进人"),
                                  ("跟进状态", "跟进状态"), ("备注", "备注")]:
            if row.get(src_col):
                rec[dst_key] = row[src_col]
