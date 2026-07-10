"""企业微信群机器人推送模块。

通过群机器人 Webhook 将招标信息周报推送到企微群。推送内容按数据权限分层：
  1. 全量摘要（Ken：全部数据）— 表格链接 + 看板链接 + 各类别条目
  2. 物码分类摘要（Mon：仅物码）
  3. 即时零售/到家分类摘要（Benny：仅即时零售）
  4. 到店分类摘要（David：仅到店）

要点：
1. 强制 UTF-8 编码发送，避免中文乱码；
2. 每周最多推送一次（本地 data/last_push_date.txt 标记，防重复推送）。
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta

import requests

from .config import config

log = logging.getLogger(__name__)

PUSH_MARKER = os.environ.get("PUSH_MARKER_FILE", "data/last_push_date.txt")


def _today_bj():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")


def _send_text(text):
    """发送文本消息到企微群机器人。"""
    payload = {"msgtype": "text", "text": {"content": text}}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    try:
        resp = requests.post(config.WECOM_WEBHOOK_URL, data=body, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") == 0:
            log.info("企微推送成功")
            return True
        log.warning("企微推送返回异常: %s", data)
        return False
    except Exception as e:
        log.warning("企微推送失败: %s", e)
        return False


def build_full_summary(new_records, sheet_url, dashboard_url, run_date):
    """全量摘要消息（Ken：全部数据）— 含表格链接 + 看板链接 + 各类别条目。"""
    count = len(new_records)
    lines = [
        f"【招标信息监控周报】{run_date}",
        f"本周新增招标信息：{count} 条",
    ]
    if sheet_url:
        lines.append(f"在线表格（查看全部并填写跟进）：{sheet_url}")
    if dashboard_url:
        lines.append(f"跟进看板：{dashboard_url}")
    lines.append("")

    if count:
        by_cat = {}
        for rec in new_records:
            by_cat.setdefault(rec.get("类别", ""), []).append(rec)
        lines.append("新增条目：")
        for cat in ("物码", "即时零售", "到店"):
            recs = by_cat.get(cat, [])
            if not recs:
                continue
            lines.append(f"[{cat}] {len(recs)} 条")
            for rec in recs:
                title = rec.get("招标标题", "")
                deadline = rec.get("截止时间", "") or "见公告"
                lines.append(f"  - {title}（截止 {deadline}）")
    else:
        lines.append("本周暂无符合条件的新增招标信息。")

    return "\n".join(lines)


def build_category_message(category, records, sheet_url, dashboard_url, run_date):
    """按类别的精简消息，标注对应负责人。格式与全量一致，但仅含该类别。"""
    owner_map = {"物码": "Mon", "即时零售": "Benny", "到店": "David"}
    owner = owner_map.get(category, "")
    count = len(records)
    lines = [
        f"【招标信息监控周报】{run_date}",
        f"👤 {owner}（仅{category}）",
        f"本周新增招标信息：{count} 条",
    ]
    if sheet_url:
        lines.append(f"在线表格（查看全部并填写跟进）：{sheet_url}")
    if dashboard_url:
        lines.append(f"跟进看板：{dashboard_url}")
    lines.append("")

    if count:
        lines.append("新增条目：")
        lines.append(f"[{category}] {count} 条")
        for rec in records:
            title = rec.get("招标标题", "")
            deadline = rec.get("截止时间", "") or "见公告"
            lines.append(f"  - {title}（截止 {deadline}）")
    else:
        lines.append("本周暂无符合条件的该类别新增招标。")

    return "\n".join(lines)


def _already_pushed_today():
    if os.path.exists(PUSH_MARKER):
        try:
            with open(PUSH_MARKER, "r", encoding="utf-8") as f:
                return f.read().strip() == _today_bj()
        except Exception:
            return False
    return False


def _mark_pushed_today():
    os.makedirs(os.path.dirname(PUSH_MARKER) or ".", exist_ok=True)
    with open(PUSH_MARKER, "w", encoding="utf-8") as f:
        f.write(_today_bj())


def push_daily(new_records, sheet_url, dashboard_url_all, dashboard_url_map, run_date, force=False):
    """按数据权限分层推送到企微群。force=True 可强制推送（用于手动测试）。

    dashboard_url_map: {"物码": url, "即时零售": url, "到店": url}
    """
    if not config.wecom_enabled():
        log.warning("未配置 WECOM_WEBHOOK_URL，跳过企微推送")
        return False
    if not force and _already_pushed_today():
        log.info("今日已推送过（%s），跳过本次推送", _today_bj())
        return False

    ok_all = True

    # 1) 全量摘要（Ken：全部数据）
    text = build_full_summary(new_records, sheet_url, dashboard_url_all, run_date)
    if not _send_text(text):
        ok_all = False

    # 2) 按类别分别推送分类摘要（Mon/Benny/David）
    #    使用各分类自己的在线表格链接和看板链接
    sheet_map = config.category_sheet_urls()
    for category in ("物码", "即时零售", "到店"):
        recs = [r for r in new_records if r.get("类别") == category]
        cat_sheet = sheet_map.get(category, sheet_url)
        dash_url = dashboard_url_map.get(category, dashboard_url_all)
        text = build_category_message(category, recs, cat_sheet, dash_url, run_date)
        if not _send_text(text):
            ok_all = False

    if ok_all:
        _mark_pushed_today()
    return ok_all
