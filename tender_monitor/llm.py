"""DeepSeek 大模型模块：负责判定相关性并把搜索结果解析为结构化招标信息字段。

使用 DeepSeek 的 OpenAI 兼容接口 + JSON 输出模式。
"""
import json
import logging
import requests

from .config import config

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一名专业的招标信息分析助手。你的任务是判断给定网页是否为某一监控主题下的"真实招标/采购/询价公告或强相关商机线索"，并抽取结构化字段。

判定规则：
1. 必须是招标、采购、询价、竞争性磋商、中标结果等商机线索，或与该主题强相关的采购需求。
2. 排除：纯广告推广页、软件下载页、与招标无关的新闻资讯、课程培训售卖、SEO 垃圾页。
3. 类别只能是给定的 category，不要改写。

严格只输出 JSON，不要输出任何多余文字。"""

USER_TEMPLATE = """监控主题(category): {category}
该主题关键词示例: {keywords}

网页标题: {title}
网页链接: {url}
网页摘要: {snippet}

请输出如下 JSON：
{{
  "relevant": true/false,          // 是否为该主题下真实招标/强相关商机，false 则其余字段可为空
  "招标编号": "",
  "招标标题": "",                   // 规范化后的标题
  "招标单位": "",                   // 招标单位/采购人
  "招标方式": "",                   // 如 公开招标/竞争性磋商/询价/直接采购 等，未知填 未知
  "采购内容": "",                   // 采购内容/信息摘要，60字以内
  "预算金额": "",                   // 必须带单位（万元/元），如"89万元"；未披露填 未披露
  "发布时间": "",                   // YYYY-MM-DD，未知留空
  "截止时间": "",                   // 投标截止时间 YYYY-MM-DD 或含时刻，未知留空
  "项目地点": "",                   // 省市，未知填 全国/详见公告
  "信息来源平台": "",               // 招标公告发布的平台/网站名称，如"中国政府采购网""乙方宝""采招网"等；未知留空
  "联系方式": ""                    // 从公告摘取联系人+手机/电话/邮箱，如"联系人:张工 手机:139xxxx 邮箱:x@x.com"；未知留空
}}"""


def _chat_json(system, user):
    """调用 DeepSeek chat，强制 JSON 输出。"""
    url = config.DEEPSEEK_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 800,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def extract_tender(category, keywords, item):
    """把一条搜索结果解析为结构化招标信息。

    返回 dict（含 relevant 字段）；解析失败返回 None。
    """
    user = USER_TEMPLATE.format(
        category=category,
        keywords="、".join(keywords[:12]),
        title=item.get("title", ""),
        url=item.get("url", ""),
        snippet=(item.get("snippet", "") or "")[:1500],
    )
    try:
        data = _chat_json(SYSTEM_PROMPT, user)
    except Exception as e:
        log.warning("DeepSeek 解析失败 url=%s err=%s", item.get("url"), e)
        return None

    if not data.get("relevant"):
        return None

    # 类别与来源兜底
    data["类别"] = category
    data["资料来源"] = item.get("url", "")
    if not data.get("发布时间") and item.get("date"):
        data["发布时间"] = item["date"][:10]
    if not data.get("项目地点"):
        data["项目地点"] = "全国/详见公告"
    if not data.get("预算金额"):
        data["预算金额"] = "未披露"
    if not data.get("招标标题"):
        data["招标标题"] = item.get("title", "")
    if not data.get("信息来源平台"):
        data["信息来源平台"] = ""
    return data
