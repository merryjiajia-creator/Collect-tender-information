"""搜索模块：支持博查(bocha)、Serper(Google API)。

默认使用博查，对中国招标网站覆盖最佳。博查免费额度每月 1000 次，
对于每周一次的任务绰绰有余。

统一返回结构：
    {"title": str, "url": str, "snippet": str, "date": str}
"""
import logging

import requests

from .config import config

log = logging.getLogger(__name__)


def _search_bocha(query, count, freshness):
    """博查 AI 搜索，适合中文招标网站。免费额度：1000次/月。
    文档：https://open.bochaai.com
    """
    url = "https://api.bochaai.com/v1/web-search"
    headers = {
        "Authorization": f"Bearer {config.BOCHA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "summary": True,
        "count": count,
        "freshness": freshness,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    results = []
    pages = (((data or {}).get("data") or {}).get("webPages") or {}).get("value") or []
    for p in pages:
        results.append({
            "title": p.get("name", ""),
            "url": p.get("url", ""),
            "snippet": p.get("summary") or p.get("snippet", ""),
            "date": p.get("datePublished") or p.get("dateLastCrawled", "") or "",
        })
    return results


def _search_serper(query, count, freshness):
    """Serper.dev（Google 搜索 API）。文档：https://serper.dev"""
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": config.SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    tbs_map = {"oneDay": "qdr:d", "oneWeek": "qdr:w", "oneMonth": "qdr:m"}
    payload = {"q": query, "gl": "cn", "hl": "zh-cn", "num": count}
    if freshness in tbs_map:
        payload["tbs"] = tbs_map[freshness]
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for p in data.get("organic", []):
        results.append({
            "title": p.get("title", ""),
            "url": p.get("link", ""),
            "snippet": p.get("snippet", ""),
            "date": p.get("date", "") or "",
        })
    return results


_SEARCHERS = {
    "bocha": _search_bocha,
    "serper": _search_serper,
}


def search(query, count=None, freshness=None):
    """按配置的搜索引擎执行一次搜索，失败返回空列表。"""
    count = count or config.MAX_RESULTS_PER_KEYWORD
    freshness = freshness or config.SEARCH_FRESHNESS
    try:
        fn = _SEARCHERS.get(config.SEARCH_PROVIDER, _search_bocha)
        return fn(query, count, freshness)
    except Exception as e:
        log.warning("搜索失败 query=%s err=%s", query, e)
        return []
