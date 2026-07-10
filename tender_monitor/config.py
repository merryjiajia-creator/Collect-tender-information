"""集中读取环境变量配置。所有密钥、ID、Token 均通过环境变量注入，代码中不出现明文。"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # 在 GitHub Actions 中通过 Secrets 注入环境变量，无需 .env
    pass


def _get(name, default=None, required=False):
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(f"缺少必需的环境变量: {name}")
    return val


class Config:
    # ---------- DeepSeek 大模型 ----------
    DEEPSEEK_API_KEY = _get("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = _get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = _get("DEEPSEEK_MODEL", "deepseek-chat")

    # ---------- 搜索引擎（bocha 博查 / serper Google API���----------
    # 博查免费额度 1000次/月，对中文招标网站覆盖最佳
    SEARCH_PROVIDER = _get("SEARCH_PROVIDER", "bocha").lower()
    BOCHA_API_KEY = _get("BOCHA_API_KEY", "")
    SERPER_API_KEY = _get("SERPER_API_KEY", "")
    SEARCH_FRESHNESS = _get("SEARCH_FRESHNESS", "oneWeek")   # oneDay/oneWeek/oneMonth/noLimit
    MAX_RESULTS_PER_KEYWORD = int(_get("MAX_RESULTS_PER_KEYWORD", "8"))
    MAX_NEW_PER_RUN = int(_get("MAX_NEW_PER_RUN", "60"))     # 单次运行最多新增条数，防止超量

    # ---------- 收集规则 ----------
    # 仅采集该日期（含）之后发布的招标；以及投标截止时间尚未过期的招标
    PUBLISH_DATE_CUTOFF = _get("PUBLISH_DATE_CUTOFF", "2026-06-01")

    # ---------- 腾讯在线文档 OpenAPI 通用认证 ----------
    TENCENT_CLIENT_ID = _get("TENCENT_CLIENT_ID", "")
    TENCENT_CLIENT_SECRET = _get("TENCENT_CLIENT_SECRET", "")
    TENCENT_REFRESH_TOKEN = _get("TENCENT_REFRESH_TOKEN", "")

    # ---------- 腾讯在线文档 — 按类别拆分的独立表格 ----------
    # 每张表格有独立的 file_id / sheet_id / 公开链接
    TENCENT_FILE_WM = _get("TENCENT_FILE_WM", "")       # 物码表格 file_id
    TENCENT_SHEET_WM = _get("TENCENT_SHEET_WM", "000001")
    SHEET_URL_WM = _get("SHEET_URL_WM", "")

    TENCENT_FILE_JS = _get("TENCENT_FILE_JS", "")       # 即时零售表格 file_id
    TENCENT_SHEET_JS = _get("TENCENT_SHEET_JS", "000001")
    SHEET_URL_JS = _get("SHEET_URL_JS", "")

    TENCENT_FILE_DD = _get("TENCENT_FILE_DD", "")       # 到店表格 file_id
    TENCENT_SHEET_DD = _get("TENCENT_SHEET_DD", "000001")
    SHEET_URL_DD = _get("SHEET_URL_DD", "")

    # 兼容旧配置：若未配置分类表格，回退到统一表格
    TENCENT_FILE_ID = _get("TENCENT_FILE_ID", "")
    TENCENT_SHEET_ID = _get("TENCENT_SHEET_ID", "000001")
    SHEET_URL = _get("SHEET_URL", "")

    @classmethod
    def category_sheet_urls(cls):
        """返回各类别的在线表格链接 dict。若未单独配置则回退到统一链接。"""
        return {
            "物码": cls.SHEET_URL_WM or cls.SHEET_URL,
            "即时零售": cls.SHEET_URL_JS or cls.SHEET_URL,
            "到店": cls.SHEET_URL_DD or cls.SHEET_URL,
        }

    @classmethod
    def category_file_config(cls, category):
        """返回某类别对应的 (file_id, sheet_id)。未配置则返回统一表格。"""
        mapping = {
            "物码": (cls.TENCENT_FILE_WM or cls.TENCENT_FILE_ID,
                      cls.TENCENT_SHEET_WM if cls.TENCENT_FILE_WM else cls.TENCENT_SHEET_ID),
            "即时零售": (cls.TENCENT_FILE_JS or cls.TENCENT_FILE_ID,
                          cls.TENCENT_SHEET_JS if cls.TENCENT_FILE_JS else cls.TENCENT_SHEET_ID),
            "到店": (cls.TENCENT_FILE_DD or cls.TENCENT_FILE_ID,
                      cls.TENCENT_SHEET_DD if cls.TENCENT_FILE_DD else cls.TENCENT_SHEET_ID),
        }
        return mapping.get(category, (cls.TENCENT_FILE_ID, cls.TENCENT_SHEET_ID))

    # ---------- 企业微信群机器人 ----------
    WECOM_WEBHOOK_URL = _get("WECOM_WEBHOOK_URL", "")    # 群机器人 Webhook URL

    # ---------- 看板 ----------
    DASHBOARD_URL = _get("DASHBOARD_URL", "")               # 看板公开链接（GitHub Pages）
    DASHBOARD_DIR = _get("DASHBOARD_DIR", "dashboard")      # 看板输出目录

    # ---------- 本地数据 ----------
    STORE_PATH = _get("STORE_PATH", "data/store.json")      # 去重与备份的本地数据仓
    DASHBOARD_PATH = _get("DASHBOARD_PATH", "dashboard/index.html")

    @classmethod
    def tencent_enabled(cls):
        return bool(cls.TENCENT_CLIENT_ID and cls.TENCENT_CLIENT_SECRET
                    and cls.TENCENT_REFRESH_TOKEN
                    and (cls.TENCENT_FILE_ID or cls.TENCENT_FILE_WM
                         or cls.TENCENT_FILE_JS or cls.TENCENT_FILE_DD))

    @classmethod
    def wecom_enabled(cls):
        return bool(cls.WECOM_WEBHOOK_URL)


config = Config()
