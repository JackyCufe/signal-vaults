"""飞书 Bot 通道：WebSocket 长连接（官方推荐的个人开发接入方式）。

架构（收发分离）:
- 收: lark_oapi.ws.Client 长连接接收群消息事件（无需公网服务器/IP白名单, 自动重连）
- 发: bot 身份 OpenAPI 主动发消息回群（需 im:message 权限）

配置 (.env, 不入库):
    FEISHU_APP_ID=cli_xxx
    FEISHU_APP_SECRET=xxx
    FEISHU_TARGET_CHAT=oc_xxx      # 可选: 指定接收日报的群; 缺省=用户在群里说"日报"的群

获取方式: https://open.feishu.cn → 开发者后台 → 创建企业自建应用
  1. 凭证页拿 App ID / App Secret
  2. 权限管理开通: im:message(或 im:message:send_as_bot)、im:message.receive_v1 相关只读权限
  3. 事件订阅方式选「使用长连接接收事件」, 添加事件: 接收消息 im.message.receive_v1
  4. 应用发布 → 版本创建与发布 → 管理员扫码通过
  5. 把 bot 拉进目标群

运行:
    signal-vaults feishu          # 前台守护: 收群消息, 识别指令并回日报
群内指令:
    日报            → 跑微信群日报(daily 1)+公众号(mp 3)+hn+reddit, 全部回发群里
    hn / reddit     → 单独跑对应信息源
    帮助 / hello    → 回复可用指令说明
"""
import json
import os
import threading

from . import config

NL = "\n"


def feishu_ws_ready():
    return bool(os.environ.get("FEISHU_APP_ID") and os.environ.get("FEISHU_APP_SECRET"))


# ---------- 发送 (OpenAPI, bot 身份) ----------

def _client():
    import lark_oapi as lark
    return lark.Client.builder() \
        .app_id(os.environ["FEISHU_APP_ID"]) \
        .app_secret(os.environ["FEISHU_APP_SECRET"]) \
        .build()


def send_text(chat_id, text):
    """bot 主动发文本消息到群; 返回 (ok, msg)"""
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (CreateMessageRequest,
                                     CreateMessageRequestBody)
    try:
        client = _client()
        req = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(json.dumps({"text": text}))
                .build()) \
            .build()
        resp = client.im.v1.message.create(req)
        if resp.success():
            return True, ""
        return False, "code={} msg={}".format(resp.code, resp.msg)
    except Exception as e:
        return False, str(e)


def digest_to_text(digest, title):
    """digest dict → 飞书纯文本日报（不带群ID; 链接用 post 富文本才是超链接, text 只能裸URL）"""
    m = digest["meta"]
    lines = ["【{}】近{}天 | {}条源".format(
        title, m.get("days", 1), m.get("total", "?")), ""]
    for i, k in enumerate(digest["hot"][:8], 1):
        lines.append("{}. {}".format(i, k.get("topic", "")))
        lines.append("   {}".format(k.get("detail", "")))
    res = digest.get("resources") or []
    if res:
        lines += ["", "— 资源/链接 —"]
        for r in res[:8]:
            if isinstance(r, dict) and r.get("url"):
                lines.append("- {}{}".format(
                    (r.get("title") or r["url"])[:60], NL + r["url"]))
            elif isinstance(r, dict):
                lines.append("- {}".format(r.get("title", "")))
    return NL.join(lines)[:6000]


def send_post(chat_id, title, lines):
    """发送 post 富文本: lines = [(text, href|None), ...]
    多行支持: text 内含 \n 时拆成多行; 空行 → 空段落(序号间留白)
    """
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (CreateMessageRequest,
                                     CreateMessageRequestBody)
    paragraphs = []
    for text, href in lines:
        for seg in text.split("\n"):
            if not seg.strip():
                paragraphs.append([])  # 空段落 = 空行
            elif href:
                paragraphs.append([{"tag": "a", "text": seg, "href": href}])
            else:
                paragraphs.append([{"tag": "plain_text", "content": seg}])
    content = {"post": {"zh_cn": {"title": title, "content": paragraphs}}}
    try:
        client = _client()
        req = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("post")
                .content(json.dumps(content, ensure_ascii=False))
                .build()) \
            .build()
        resp = client.im.v1.message.create(req)
        if resp.success():
            return True, ""
        return False, "code={} msg={}".format(resp.code, resp.msg)
    except Exception as e:
        return False, str(e)


def digest_post_lines(digest):
    """digest → post 行列表: [(text, href|None)] — markdown 对齐版
    序号行加粗不可用(post 无 md), 用「N. 标题」+ 空行分隔每个条目
    """
    m = digest["meta"]
    out = [("近{}天 | 共{}条源消息".format(m.get("days", 1), m.get("total", "?")), None)]
    for i, k in enumerate(digest["hot"][:8], 1):
        out.append(("", None))  # 条目间空行
        out.append(("{}. {}".format(i, k.get("topic", "")), None))
        out.append(("{}".format(k.get("detail", "")), None))
        who = k.get("who", "")
        if who:
            out.append(("   —— {}".format(who), None))
    res = digest.get("resources") or []
    if res:
        out.append(("", None))
        out.append(("—— 资源/链接 ——", None))
        for r in res[:10]:
            if isinstance(r, dict) and r.get("url"):
                out.append(("· " + (r.get("title") or r["url"])[:60], r["url"]))
            elif isinstance(r, dict):
                out.append(("· " + r.get("title", ""), None))
    return out


def push_feishu(digest, txt_path=None):
    """兼容 daily.py 的旧入口: 若配置了 WS 版凭证且有目标群, 主动推送日报。"""
    if not (feishu_ws_ready() and os.environ.get("FEISHU_TARGET_CHAT")):
        print("  (未配置 FEISHU_APP_ID/SECRET 或 FEISHU_TARGET_CHAT, 跳过飞书推送)")
        return 0
    chat = os.environ["FEISHU_TARGET_CHAT"]
    ok, msg = send_post(chat, "Signal Vaults 日报", digest_post_lines(digest))
    if not ok:  # post 失败(内容超限等)退回纯文本
        ok, msg2 = send_text(chat, digest_to_text(digest, "Signal Vaults 日报"))
        msg = msg2 if not ok else msg
    print("  -> 飞书推送 {}".format("OK" if ok else "失败: " + msg))
    return 200 if ok else -1


# ---------- 接收 (WS 长连接守护) ----------

HELP = ("Signal Vaults 指令:{}"
        "• 日报 — 微信群+公众号+HN+Reddit 全部跑一遍{}"
        "• hn — Hacker News 日报{}"
        "• reddit [子版块...] — Reddit 日报{}"
        "• 群聊日报 [天数] [群名] — 只跑微信群{}"
        "• 帮助 — 显示本说明")


def _run_and_reply(source_fn, chat_id, label):
    def worker():
        try:
            digest, txt_path = source_fn()
            send_text(chat_id, digest_to_text(digest, label))
            if txt_path:
                send_text(chat_id, "完整版见本地: {}".format(txt_path))
        except Exception as e:
            send_text(chat_id, "执行失败: {}".format(str(e)[:200]))
    threading.Thread(target=worker, daemon=True).start()


def _handle_command(text, chat_id):
    t = text.strip().lower()
    from . import daily, external
    if t in ("帮助", "hello", "hi", "帮助。"):
        send_text(chat_id, HELP.format(NL, NL, NL, NL, NL))
    elif t == "日报":
        send_text(chat_id, "收到, 开始生成全套日报(群聊+公众号+HN+Reddit), 需几分钟...")
        _run_and_reply(lambda: _full_daily(), chat_id, "Signal Vaults 全套日报")
    elif t in ("hn", "hacker news"):
        send_text(chat_id, "收到, 生成 Hacker News 日报...")
        _run_and_reply(lambda: external.build_source_digest("hn", 1), chat_id, "Hacker News 日报")
    elif t.startswith("reddit"):
        parts = t.split()
        subs = [s.lstrip("r/") for s in parts[1:] if not s.isdigit()] or None
        send_text(chat_id, "收到, 生成 Reddit 日报...")
        _run_and_reply(lambda: external.build_source_digest("reddit", 1, subs=subs), chat_id, "Reddit 日报")
    elif t.startswith("群聊日报"):
        parts = t.split()
        days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        group = " ".join(parts[2:]) or None
        send_text(chat_id, "收到, 生成微信群聊日报(近{}天)...".format(days))
        _run_and_reply(lambda: _group_daily(days, group), chat_id, "微信群聊日报")
    else:
        send_text(chat_id, "没听懂「{}」。{}".format(text[:30], HELP.format(NL, NL, NL, NL, NL)[:80]))


def _full_daily():
    """全套日报: 聚合微信群+公众号+HN+Reddit 到一个 digest"""
    from . import collector, daily, external
    from .sources import HackerNewsSource, RedditSource
    us, msgs = collector.fetch_messages("Agentic Lab", 1)
    parts = daily.summarize_chunks(us, msgs, 1)
    d1 = daily.merge_knowledge(us, parts, 1, len(msgs), raw_msgs=msgs)
    items = HackerNewsSource(limit=30).fetch(1)
    d2 = external._digest_for_source("Hacker News", items, 1)
    ritems = RedditSource(subs=["LocalLLaMA", "programming"]).fetch(1)
    d3 = external._digest_for_source("Reddit", ritems, 1)
    merged = {
        "hot": (d1["hot"] + d2["hot"] + d3["hot"])[:15],
        "resources": d1.get("resources", []) + d2.get("resources", [])[:5] + d3.get("resources", [])[:5],
        "meta": {"chat": "Agentic Lab + HN + Reddit", "days": 1,
                 "total": d1["meta"]["total"] + d2["meta"]["total"] + d3["meta"]["total"],
                 "days_label": "近1天", "raw_chat": None, "thumbs": [], "files": []},
    }
    txt_path = os.path.join(config.WORK_DIR, "know_full.txt")
    open(txt_path, "w", encoding="utf-8").write(daily.render_text(merged))
    return merged, txt_path


def _group_daily(days, group):
    from . import collector, daily
    us, msgs = collector.fetch_messages(group or "Agentic Lab", days)
    parts = daily.summarize_chunks(us, msgs, days)
    d = daily.merge_knowledge(us, parts, days, len(msgs), raw_msgs=msgs)
    txt_path = os.path.join(config.WORK_DIR, "know_ws_group.txt")
    open(txt_path, "w", encoding="utf-8").write(daily.render_text(d))
    return d, txt_path


def start_ws():
    """启动 WS 长连接守护（阻塞, 供 CLI 前台运行/进程守护）。"""
    if not feishu_ws_ready():
        print("缺少 FEISHU_APP_ID / FEISHU_APP_SECRET 环境变量")
        print("配置方法见 SKILL.md『飞书 Bot(WebSocket)』一节")
        return 1
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

    def on_msg(data: P2ImMessageReceiveV1) -> None:
        try:
            msg = data.event.message
            if msg.message_type != "text":
                return
            content = json.loads(msg.content)
            text = content.get("text", "")
            chat_id = msg.chat_id
            print("[feishu-ws] 收到: {}".format(text[:40]))
            _handle_command(text, chat_id)
        except Exception as e:
            print("[feishu-ws] 处理消息失败:", e)

    event_handler = lark.EventDispatcherHandler.builder(
        "", "").register_p2_im_message_receive_v1(on_msg).build()

    client = lark.ws.Client(
        os.environ["FEISHU_APP_ID"],
        os.environ["FEISHU_APP_SECRET"],
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO)
    print("[feishu-ws] WebSocket 长连接启动, 等待群指令... (Ctrl+C 退出)")
    client.start()
    return 0
