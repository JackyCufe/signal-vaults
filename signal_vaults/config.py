# -*- coding: utf-8 -*-
"""环境变量驱动配置 — 所有敏感信息来自 env / 本地文件, 代码零硬编码。

环境变量:
  SIGNAL_VAULTS_DB_DIR        微信数据目录 (.../db_storage), 缺省自动检测
  SIGNAL_VAULTS_KEYS_FILE     密钥文件, 缺省 ~/.wechat-cli/all_keys.json (wechat-cli init 生成)
  SIGNAL_VAULTS_WORK_DIR      工作目录 (解密库/缓存/输出), 缺省 ./work
  LLM_API_KEY          OpenAI 兼容 API Key (必填才能调 LLM)
  LLM_BASE_URL         缺省 https://open.bigmodel.cn/api/paas/v4 (智谱)
  LLM_MODEL            缺省 glm-4-flash
  LLM_PROXY            可选, 如 http://127.0.0.1:7897
  DISCORD_BOT_TOKEN    可选, 配置后自动推送 Discord
  DISCORD_CHANNEL_ID   可选
"""
import os


def _env(name, default=""):
    return os.environ.get(name, default)


# ---------- 微信数据 ----------
DB_DIR = _env("SIGNAL_VAULTS_DB_DIR")
KEYS_FILE = _env("SIGNAL_VAULTS_KEYS_FILE")
WORK_DIR = os.path.abspath(_env("SIGNAL_VAULTS_WORK_DIR") or os.path.join(os.getcwd(), "work"))
DEC_DIR = os.path.join(WORK_DIR, "decrypted")


def resolve_db_dir() -> str:
    """db_storage 目录: env 优先, 否则复用 wechat-cli 的三平台自动检测"""
    global DB_DIR
    if DB_DIR:
        return DB_DIR
    try:
        from wechat_cli.core.config import auto_detect_db_dir
        DB_DIR = auto_detect_db_dir() or ""
    except Exception:
        DB_DIR = ""
    if not DB_DIR:
        raise FileNotFoundError(
            "未找到微信数据目录。请先运行 `wechat-cli init`, "
            "或设置 SIGNAL_VAULTS_DB_DIR 指向 .../db_storage")
    return DB_DIR


def resolve_keys_file() -> str:
    global KEYS_FILE
    if KEYS_FILE:
        return KEYS_FILE
    KEYS_FILE = os.path.join(os.path.expanduser("~"), ".wechat-cli", "all_keys.json")
    return KEYS_FILE


def base_dir() -> str:
    """微信账号数据根目录 (db_storage 的上一级, 即 wxid_xxx 目录)"""
    p = resolve_db_dir()
    return os.path.dirname(p) if os.path.basename(p) == "db_storage" else p


# ---------- LLM (OpenAI 兼容 /chat/completions) ----------
LLM_API_KEY = _env("LLM_API_KEY")
LLM_BASE_URL = _env("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
LLM_MODEL = _env("LLM_MODEL", "glm-4-flash")
LLM_PROXY = _env("LLM_PROXY")

# ---------- Discord 推送 (可选) ----------
DISCORD_BOT_TOKEN = _env("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = _env("DISCORD_CHANNEL_ID")
PUSH_PROXY = _env("PUSH_PROXY") or LLM_PROXY


def discord_ready() -> bool:
    return bool(DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID)
