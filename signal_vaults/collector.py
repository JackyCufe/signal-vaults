# -*- coding: utf-8 -*-
"""消息采集 — 解密 SQLCipher 库 + 会话定位 + 消息/附件提取 (Windows/macOS/Linux)"""
import os
import re
import json
import time
import sqlite3
import hashlib
import datetime

from . import config

try:
    import zstandard as zstd
    _ZD = zstd.ZstdDecompressor()
except ImportError:
    _ZD = None

from wechat_cli.core.crypto import full_decrypt as _full_decrypt
from wechat_cli.core.crypto import decrypt_wal as _decrypt_wal

TYPE_NAMES = {1: "文本", 3: "图片", 34: "语音", 43: "视频", 47: "表情", 48: "位置",
              49: "链接/文件", 10002: "撤回", 10000: "系统", 51: "卡片"}


def _load_keys() -> dict:
    kf = config.resolve_keys_file()
    if not os.path.exists(kf):
        raise FileNotFoundError(
            "未找到密钥文件 {}。请先运行 `wechat-cli init` (微信需处于登录状态)".format(kf))
    return json.load(open(kf, encoding="utf-8"))


def decrypt_db(rel_path: str, enc_key: bytes, force=False) -> str:
    """解密单个库到工作目录 (mtime 增量跳过)"""
    src = os.path.join(config.resolve_db_dir(), rel_path)
    dst = os.path.join(config.DEC_DIR, rel_path.replace("\\", "_").replace("/", "_"))
    os.makedirs(config.DEC_DIR, exist_ok=True)
    if os.path.exists(dst) and not force and \
       os.path.getmtime(dst) > os.path.getmtime(src) - 60:
        return dst
    tmp = dst + ".tmp"
    _full_decrypt(src, tmp, enc_key)
    _decrypt_wal(src + "-wal", tmp, enc_key)
    os.replace(tmp, dst)
    return dst


def ensure_core_dbs() -> dict:
    """解密 message_*/contact/session 核心库, 返回 {rel_path: 解密后路径}"""
    outs = {}
    for rel, info in _load_keys().items():
        if re.match(r"(message.message_[0-9]+|contact.contact|session.session)\.db$", rel):
            outs[rel] = decrypt_db(rel, bytes.fromhex(info["enc_key"]))
    return outs


def ensure_biz_dbs() -> dict:
    """解密公众号消息库 biz_message_*"""
    outs = {}
    for rel, info in _load_keys().items():
        if "biz_message" in rel:
            outs[rel] = decrypt_db(rel, bytes.fromhex(info["enc_key"]))
    return outs


def find_chat(keyword: str):
    """按关键词找会话, 返回 [(username, nick, remark)]"""
    db = os.path.join(config.DEC_DIR, "contact_contact.db")
    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT username, nick_name, remark FROM contact "
        "WHERE (nick_name LIKE ? OR remark LIKE ? OR username LIKE ?) "
        "AND (is_in_chat_room=1 OR username NOT LIKE '%@chatroom%') LIMIT 5",
        ("%{}%".format(keyword), "%{}%".format(keyword), "%{}%".format(keyword))).fetchall()
    con.close()
    return rows


def _dec_content(raw):
    if isinstance(raw, bytes) and raw[:4] == b"\x28\xb5\x2f\xfd" and _ZD:
        try:
            raw = _ZD.decompress(raw, max_output_size=1 << 24)
        except Exception:
            return "[解压失败]"
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    return raw


def fetch_messages(keyword: str, days: int = 2):
    """拉取会话最近 N 天消息, 返回 (username, [msg dicts])"""
    ensure_core_dbs()
    chats = find_chat(keyword)
    if not chats:
        raise LookupError("找不到会话: {}".format(keyword))
    username = chats[0][0]
    table = "Msg_" + hashlib.md5(username.encode()).hexdigest()
    msgs = []
    for db in sorted(_glob_decrypted("message_message_*.db")):
        con = sqlite3.connect(db)
        try:
            tabs = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if table not in tabs:
                continue
            since = int(time.time()) - days * 86400
            rows = con.execute(
                "SELECT local_id, create_time, local_type, message_content, "
                "WCDB_CT_message_content, real_sender_id "
                "FROM {} WHERE create_time > ? ORDER BY create_time".format(table),
                (since,)).fetchall()
        finally:
            con.close()
        wx2nick = _nick_map()
        for lid, ts, ltype, content, ct, sender in rows:
            raw = _dec_content(content)
            sender_name = ""
            m = re.match(r"^([@\w\-]+):\n", raw)
            if m:
                sender_name = wx2nick.get(m.group(1), m.group(1))
                raw = raw[m.end():]
            elif sender:
                sender_name = "id{}".format(sender)
            item = {"ts": ts, "type": ltype, "type_name": TYPE_NAMES.get(ltype, str(ltype)),
                    "sender": sender_name, "local_id": lid, "raw": raw}
            if raw.startswith("<?xml") or raw.startswith("<msg"):
                title = re.search(r"<title>(.*?)</title>", raw, re.S)
                url = re.search(r"<url>(.*?)</url>", raw, re.S)
                item["title"] = title.group(1).strip() if title else ""
                item["url"] = url.group(1).strip() if url else ""
                item["display"] = "[{}] {}".format(item["type_name"], item["title"]) + \
                    (" -> {}".format(item["url"][:120]) if item["url"] else "")
            else:
                item["display"] = raw.strip()[:500]
            msgs.append(item)
    msgs.sort(key=lambda x: x["ts"])
    for a in find_thumbs(username, days):
        for m in msgs:
            if m["local_id"] == a["local_id"] and abs(m["ts"] - a["ts"]) < 86400:
                m["thumb"] = a["path"]
                break
    return username, msgs


def _glob_decrypted(pattern):
    return sorted(glob_patterns(config.DEC_DIR, pattern))


def glob_patterns(d, pattern):
    import glob
    return glob.glob(os.path.join(d, pattern))


def _nick_map() -> dict:
    con = sqlite3.connect(os.path.join(config.DEC_DIR, "contact_contact.db"))
    wx2nick = {r[0]: r[1] for r in con.execute(
        "SELECT username, nick_name FROM contact")}
    con.close()
    return wx2nick


def find_thumbs(username: str, days: int):
    """图片缩略图: <base>/cache/<月>/Message/<md5>/Thumb/{localId}_{ts}_thumb.jpg"""
    md5 = hashlib.md5(username.encode()).hexdigest()
    out = []
    cache = os.path.join(config.base_dir(), "cache")
    if not os.path.isdir(cache):
        return out
    now = time.time()
    for month in os.listdir(cache):
        mdir = os.path.join(cache, month, "Message", md5, "Thumb")
        if not os.path.isdir(mdir):
            continue
        for f in os.listdir(mdir):
            m = re.match(r"(\d+)_(\d+)_thumb\.(jpg|png)$", f)
            if m:
                ts = int(m.group(2))
                if now - ts <= days * 86400 * 1.2:
                    out.append({"local_id": int(m.group(1)), "ts": ts,
                                "path": os.path.join(mdir, f)})
    return out


def find_files(username: str, days: int):
    """文件附件: <base>/msg/attach/<md5>/ 下的明文文件 (排除 .dat)"""
    md5 = hashlib.md5(username.encode()).hexdigest()
    out = []
    root = os.path.join(config.base_dir(), "msg", "attach", md5)
    if not os.path.isdir(root):
        return out
    now = time.time()
    for dirpath, _d, files in os.walk(root):
        for f in files:
            if f.endswith(".dat"):
                continue
            p = os.path.join(dirpath, f)
            try:
                if now - os.path.getmtime(p) <= days * 86400 * 1.2:
                    out.append(p)
            except OSError:
                pass
    return out


def group_name(username: str) -> str:
    try:
        con = sqlite3.connect(os.path.join(config.DEC_DIR, "contact_contact.db"))
        row = con.execute("SELECT nick_name, remark FROM contact WHERE username=?",
                          (username,)).fetchone()
        con.close()
        if row:
            return row[1] or row[0] or username
    except Exception:
        pass
    return username


def _xml_get(raw, tag):
    m = re.search("<{0}>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?</{0}>".format(tag), raw, re.S)
    return m.group(1).strip() if m else ""


def fetch_articles(days=3, ghs=None):
    """公众号文章: gh_id -> (标题/链接/摘要)。ghs: {"显示名": "gh_xxx"}"""
    ensure_biz_dbs()
    ghs = ghs or {}
    out = {name: [] for name in ghs}
    since = time.time() - days * 86400
    for db in sorted(glob_patterns(config.DEC_DIR, "message_biz_message_*.db")):
        con = sqlite3.connect(db)
        try:
            gh_in_db = {r[0] for r in con.execute(
                "SELECT user_name FROM Name2Id WHERE user_name LIKE 'gh_%'")}
            for name, gh in ghs.items():
                if gh not in gh_in_db:
                    continue
                t = "Msg_" + hashlib.md5(gh.encode()).hexdigest()
                if t not in {r[0] for r in con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'")}:
                    continue
                rows = con.execute(
                    "SELECT create_time, message_content FROM {} "
                    "WHERE create_time > ? ORDER BY create_time".format(t),
                    (since,)).fetchall()
                for ts, c in rows:
                    raw = _dec_content(c)
                    title = _xml_get(raw, "title")
                    if title:
                        out[name].append({
                            "ts": ts, "title": title,
                            "url": _xml_get(raw, "url"),
                            "digest": _xml_get(raw, "digest"), "gh": name,
                            "time": datetime.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")})
        finally:
            con.close()
    for name in out:
        out[name].sort(key=lambda x: -x["ts"])
    return out
