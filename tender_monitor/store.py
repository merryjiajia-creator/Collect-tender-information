"""本地数据仓与表结构定义。

- 本地 store.json 是去重与历史备份的可靠来源（由 GitHub Action 提交回仓库）。
- 在线表格是 15 列的展示视图；看板从 store.json（含全部卡片字段）生成，
  并把跟进团队/跟进人/跟进状态从在线表格回写同步。
"""
import json
import os

from .keywords import TEAM_MAP, DEFAULT_STATUS

# 在线表格 16 列表头（信息来源平台 紧跟在 类别 之后）
TABLE_COLUMNS = [
    "序号", "类别", "信息来源平台", "招标标题", "招标单位", "发布时间",
    "截止时间", "预算金额", "原文链接", "项目地点",
    "采购内容（信息摘要）", "联系人以及联系方式",
    "跟进团队", "跟进人", "跟进状态", "备注",
]

# 完整记录字段（store.json 内含全部卡片字段）
RECORD_FIELDS = [
    "类别", "招标编号", "招标标题", "招标单位", "招标方式", "采购内容",
    "预算金额", "发布时间", "截止时间", "项目地点", "信息来源平台",
    "联系方式", "资料来源",
    "跟进团队", "跟进人", "跟进状态", "备注",
]


def normalize_record(data, category=None):
    """把 LLM 抽取结果补齐为完整记录。"""
    cat = category or data.get("类别", "")
    rec = {
        "类别": cat,
        "招标编号": data.get("招标编号", "") or "",
        "招标标题": data.get("招标标题", "") or "",
        "招标单位": data.get("招标单位", "") or "",
        "招标方式": data.get("招标方式", "") or "未知",
        "采购内容": data.get("采购内容", "") or "",
        "预算金额": data.get("预算金额", "") or "未披露",
        "发布时间": data.get("发布时间", "") or "",
        "截止时间": data.get("截止时间", "") or "",
        "项目地点": data.get("项目地点", "") or "全国/详见公告",
        "信息来源平台": data.get("信息来源平台", "") or "",
        "联系方式": data.get("联系方式", "") or "",
        "资料来源": data.get("资料来源", "") or data.get("原文链接", "") or "",
        # 跟进团队按类别自动分配；跟进人/备注留空；状态默认待跟进
        "跟进团队": TEAM_MAP.get(cat, ""),
        "跟进人": "",
        "跟进状态": DEFAULT_STATUS,
        "备注": "",
    }
    return rec


def record_to_table_row(rec, index):
    """把完整记录转换为在线表格 16 列的一行（dict）。"""
    return {
        "序号": index,
        "类别": rec.get("类别", ""),
        "信息来源平台": rec.get("信息来源平台", ""),
        "招标标题": rec.get("招标标题", ""),
        "招标单位": rec.get("招标单位", ""),
        "发布时间": rec.get("发布时间", ""),
        "截止时间": rec.get("截止时间", ""),
        "预算金额": rec.get("预算金额", ""),
        "原文链接": rec.get("资料来源", ""),
        "项目地点": rec.get("项目地点", ""),
        "采购内容（信息摘要）": rec.get("采购内容", ""),
        "联系人以及联系方式": rec.get("联系方式", ""),
        "跟进团队": rec.get("跟进团队", ""),
        "跟进人": rec.get("跟进人", ""),
        "跟进状态": rec.get("跟进状态", ""),
        "备注": rec.get("备注", ""),
    }


def load_store(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_store(path, records):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def seen_links(records):
    return {r.get("资料来源", "").strip() for r in records if r.get("资料来源")}
