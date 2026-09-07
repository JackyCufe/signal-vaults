# -*- coding: utf-8 -*-
"""知识日报 — 分片 LLM 提炼 + 合并去重 + 渲染 + Discord 推送"""
import os
import re
import json
import time
import glob
import sqlite3
import urllib.request

from . import config, collector, llm

NL = chr(10)
PARTS_DIR = os.path.join(config.WORK_DIR, "parts")
os.makedirs(PARTS_DIR, exist_ok=True)

PROMPT_HEAD = ("你是AI前沿知识筛选员。以下是微信群「{chat}」最近{days}天聊天记录的第{part}部分(共{n}条)。"
               "【筛选铁律】只提取知识型内容: AI/LLM/Agent新技术、工具、模型发布、论文、开源项目、"
               "技术教程、实践经验、行业数据、有信息量的事件。八卦/斗嘴/日常闲聊/梗图/情绪表达一律忽略。"
               "【链接铁律】resources 里的 url 字段只能逐字复制聊天记录中真实出现的链接; "
               "群里没发过链接就输出空数组, 严禁自己补全/构造/推测任何 URL。"
               "{trace_rule}"
               "只输出JSON(不要markdown):")
PROMPT_EXAMPLE = ('{"knowledge":[{"topic":"知识点","detail":"2-3句: 是什么/为什么重要/怎么用","who":"分享者"@REFS_DEMO@}],'
                  '"resources":[{"title":"名称","url":"聊天记录中的原始链接","note":"一句话说明"}]}')
PROMPT_EMPTY = '{"knowledge":[],"resources":[]}'


def _trace_params():
    """消息溯源开关: SIG_VAULTS_TRACE=1 时 LLM 输出 refs 字段引用消息编号"""
    import os as _os
    enabled = _os.environ.get("SIG_VAULTS_TRACE", "0") == "1"
    return enabled, (",\"refs\":[1234,1240]" if enabled else ""), (
        "【溯源铁律】knowledge 每条必须带 refs 字段: 从输入行首的 [#编号] 里逐字复制与该知识点直接相关的消息编号(2-5个); "
        "严禁编造输入中不存在的编号。" if enabled else "")


def _chat_key(u):
    return re.sub(r"[^A-Za-z0-9]", "_", u)[:40]


def _thumbs_with_context(msgs, max_imgs=8, ctx_chars=120):
    out = []
    for i, m in enumerate(msgs):
        if not (m.get("thumb") and os.path.exists(m["thumb"])):
            continue
        when = time.strftime("%H:%M", time.localtime(m["ts"]))
        who = m["sender"] or "群友"
        ctx = []
        for j in range(max(0, i - 3), min(len(msgs), i + 3)):
            if j == i:
                continue
            t = msgs[j].get("display", "").strip()
            if t and not t.startswith("["):
                ctx.append(t[:60])
        desc = "{} {}分享 | 前后文: {}".format(when, who, " / ".join(ctx[:2]) or "(无讨论)")
        out.append({"path": m["thumb"], "desc": desc[:ctx_chars + 40]})
        if len(out) >= max_imgs:
            break
    return out


def _parse_llm_json(raw):
    """解析 LLM 输出的 JSON; 输出被截断时自动补齐 ']} 收尾, 尽量抢救已生成的条目"""
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # 截断的 JSON: 丢弃最后一个不完整对象后补 ']}' 再试
    m2 = re.search(r"\{.*", raw, re.S)
    if m2:
        s = m2.group(0).rstrip()
        # 从后往前找最后一个完整对象 "}," 或 "}" 边界
        last = s.rfind("},")
        if last > 0:
            s = s[:last + 1] + "]}"
            try:
                return json.loads(s)
            except Exception:
                pass
        # 整个就是单个不完整对象: 补引号/括号尝试
        s2 = s.rstrip(",")
        for tail in ("\"}", "\"}]}", "}", "]}", "\""):
            try:
                return json.loads(s2 + tail)
            except Exception:
                continue
    raise ValueError("无法解析 LLM JSON: " + repr(raw[:80]))


def summarize_chunks(username, msgs, days, lookback_label="1"):
    """按 ≤1800 字符分片调 LLM (避开网关非流式超时), 带缓存, 失败不缓存"""
    parts_out, slices = [], []
    cur, cur_len = [], 0
    for m in msgs:
        line_len = min(300, len(m.get("display", ""))) + 40
        if cur and cur_len + line_len > 1800:
            slices.append(cur)
            cur, cur_len = [], 0
        cur.append(m)
        cur_len += line_len
    if cur:
        slices.append(cur)
    nchunks = len(slices)
    for idx in range(nchunks):
        ch = slices[idx]
        pf = os.path.join(PARTS_DIR, "{}_know_d{}_p{}.json".format(
            _chat_key(username), lookback_label, idx))
        if os.path.exists(pf):
            parts_out.append(json.load(open(pf, encoding="utf-8")))
            print("  part{}/{} (cached)".format(idx + 1, nchunks), flush=True)
            continue
        trace_on, refs_demo, trace_rule = _trace_params()
        text = format_msgs_for_llm(ch, limit_chars=2000, with_ids=trace_on)
        head = PROMPT_HEAD.format(chat=collector.group_name(username) or username,
                                  days=days, part=idx + 1, n=len(ch),
                                  trace_rule=trace_rule)
        prompt = head + NL + PROMPT_EXAMPLE.replace("@REFS_DEMO@", refs_demo) + NL + "没有知识内容就输出 " + PROMPT_EMPTY
        data, ok = None, False
        for attempt in range(3):
            try:
                raw = llm.chat(text, system=prompt)
                data = _parse_llm_json(raw)
                ok = True
                break
            except Exception as e:
                print("  part{} retry{}: {}".format(idx + 1, attempt + 1, str(e)[:60]), flush=True)
                time.sleep(2 * attempt + 1)
        if not ok:
            print("  part{} FAILED -> 不缓存, 下次重试".format(idx + 1), flush=True)
            parts_out.append({"knowledge": [], "resources": [], "jargon": [], "_failed": True})
            continue
        json.dump(data, open(pf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        parts_out.append(data)
        print("  part{}/{} done".format(idx + 1, nchunks), flush=True)
    return parts_out


def format_msgs_for_llm(msgs, limit_chars=45000, with_ids=False):
    lines, budget = [], limit_chars
    for m in msgs:
        tag = "[#{}] ".format(m["local_id"]) if with_ids else ""
        line = "{}[{}] {}: {}".format(
            tag,
            time.strftime("%m-%d %H:%M", time.localtime(m["ts"])), m["sender"], m["display"])
        if len(line) > 300:
            line = line[:300] + "..."
        if budget - len(line) < 0:
            break
        budget -= len(line)
        lines.append(line)
    return NL.join(lines)


def collect_context(username, refs, radius=0):
    """按消息编号取原文: 只取 refs 自身那几条(默认不扩展邻居), 逐字保留原文片段。
    返回 [(local_id, time_str, sender, text)]; 编号无效时只返回存在的。"""
    if not refs:
        return []
    from . import collector
    us, msgs = collector.fetch_messages(username, days=90)
    by_id = {m["local_id"]: m for m in msgs}
    ordered = sorted(msgs, key=lambda m: m["local_id"])
    idx_of = {m["local_id"]: i for i, m in enumerate(ordered)}
    picked = {}
    for ref in refs:
        if ref not in by_id:
            continue
        i = idx_of[ref]
        for j in range(max(0, i - radius), min(len(ordered), i + radius + 1)):
            picked[ordered[j]["local_id"]] = ordered[j]
    out = []
    for _, m in sorted(picked.items(), key=lambda kv: kv[1]["local_id"]):
        txt = (m.get("display") or m.get("raw") or "")
        # 清理数字噪声: appmsg 分享卡片的 [消息ID] 前缀
        txt = re.sub(r"^\[\d{6,}\]\s*", "", txt)
        # 超长 URL 截断显示
        txt = re.sub(r"(https?://[^\s]{60})[^\s]+", r"...", txt)
        txt = txt.replace("&amp;", "&")
        # 控制字符会导致飞书卡片整个 elements 被服务端丢弃(实测), 全部剔除
        txt = "".join(ch for ch in txt if ord(ch) >= 32 or ch == "\n")[:160]
        out.append((m["local_id"],
                    time.strftime("%m-%d %H:%M", time.localtime(m["ts"])),
                    m.get("sender") or "?", txt))
    return out


def merge_knowledge(username, parts, days, total, raw_msgs=None):
    know, res = [], []
    # 收集聊天记录中真实出现过的 URL (白名单校验用)
    # 注: 从 raw 全文抓取 (display 截断 120 字符会丢 URL 参数), 且含域名级兑底
    raw_urls = set()
    for m in (raw_msgs or []):
        u = m.get("url") or ""
        if u:
            # collector 里 url 存的是 xml 原文, 可能带 CDATA 后缀 "]]", 清理后入库
            u = u.replace("]]", "").strip()
            if u.startswith("http"):
                raw_urls.add(u)
        blob = (m.get("raw") or "") + " " + (m.get("display") or "")
        for um in re.finditer(r"https?://[^\s\"'<>】]+", blob):
            raw_urls.add(um.group(0).replace("&amp;", "&"))
    for p in parts:
        know += p.get("knowledge", [])
        res += p.get("resources", [])
    seen, kd = set(), []
    for k in know:
        key = (k.get("topic", "") or "")[:30]
        if key and key not in seen:
            seen.add(key)
            kd.append(k)
    seen, rd = set(), []
    for r in res:
        key = (r.get("title", "") or r.get("url", "") or "")[:40]
        if key and key not in seen:
            seen.add(key)
            # URL 白名单: 只保留聊天记录中真实出现过的; LLM 补编的一律丢弃 url (保留标题当纯文字)
            # 注意: LLM 常逐字复制 xml 转义态(&amp;), 白名单两侧都要先还原成真实 URL 再比对
            # 匹配策略: 逐字子串 -> 失败则域名级兑底 (分享卡片链接在 xml 里常被转义/截断)
            if isinstance(r, dict) and r.get("url"):
                u = r["url"].strip().replace("&amp;", "&")
                r = dict(r)
                r["url"] = u
                exact = any(u == ru or u in ru or ru in u for ru in raw_urls)
                if not exact:
                    # 域名级兑底仅限微信文章卡片(xml 转义/截断造成同域形态差异);
                    # 其他域名必须精确匹配, 严禁放行 LLM 自补的同域链接
                    try:
                        from urllib.parse import urlparse
                        udom = urlparse(u if u.startswith("http") else "https://" + u).netloc
                        if udom in ("mp.weixin.qq.com",):
                            exact = any(urlparse(ru).netloc == udom
                                        for ru in raw_urls if ru.startswith("http"))
                    except Exception:
                        exact = False
                if not exact:
                    print("    [链接校验] 丢弃非聊天记录来源 URL: {}".format(u[:60]))
                    r.pop("url", None)
            rd.append(r)
    hot = kd
    # 溯源开关: 校验 refs 合法性 (必须是本群真实存在的 local_id, 防LLM编造)
    import os as _os
    if _os.environ.get("SIG_VAULTS_TRACE", "0") == "1" and raw_msgs:
        valid_ids = {m["local_id"] for m in raw_msgs}
        for k in hot:
            refs = [r for r in (k.get("refs") or [])
                    if isinstance(r, int) and r in valid_ids][:5]
            if refs:
                k["refs"] = refs
            else:
                k.pop("refs", None)
    try:
        brief = json.dumps(kd[:40], ensure_ascii=False)[:16000]
        raw = llm.chat(
            "以下是群内知识条目。合并同类项按重要性排序, 输出Top3-8 JSON(每条保留原条目的 refs 字段, 逐字复制; 原条目没有 refs 就不带): "
            + '{"hot":[{"topic":"...","detail":"2-3句: 是什么/为什么重要/怎么用","who":"...","refs":[1234]}]}',
            system=brief)
        hot_llm = _parse_llm_json(raw).get("hot", None)
        if hot_llm:
            # LLM 重排会改写 topic 文字, 用互含子串匹配把已校验 refs 映射回去
            refd = [(k["topic"], k.get("refs")) for k in hot if k.get("refs")]
            for k in hot_llm:
                t = (k.get("topic") or "")
                for ot, refs in refd:
                    if (t[:20] and (t[:20] in ot or ot[:20] in t)) or                        (t and ot and (t in ot or ot in t)):
                        k["refs"] = refs
                        break
            hot = hot_llm
    except Exception:
        pass
    return {"hot": hot, "resources": rd,
            "meta": {"chat": username, "days": days, "total": total}}


def render_text(digest):
    m = digest["meta"]
    gname = collector.group_name(m["raw_chat"]) if m.get("raw_chat") else m["chat"]
    lines = ["群聊: " + gname + (" (" + m["days_label"] + ")" if m.get("days_label") else ""),
             "共计 {} 条消息 (近{}天) | 生成 {}".format(
                 m["total"], m["days"], time.strftime("%Y-%m-%d %H:%M")),
             "", "## AI 前沿知识精选"]
    for i, k in enumerate(digest["hot"], 1):
        lines.append("{}. **{}**  — {}".format(i, k.get("topic"), k.get("who", "")))
        lines.append("   " + str(k.get("detail", "")))
        refs = k.get("refs")
        if refs:
            ctx = collect_context(m["raw_chat"], refs)
            if ctx:
                lines.append("   <details><summary>📎 原始上下文({}条)</summary>".format(len(ctx)))
                for _lid, ts, who, txt in ctx:
                    lines.append("   > [{}] {}: {}".format(ts, who, txt.replace(NL, " ")))
                lines.append("   </details>")
    lines.append("")
    lines.append("## 资源/链接")
    for r in digest["resources"]:
        if isinstance(r, dict):
            if r.get("url"):
                lines.append("- {} {}".format(r.get("title", ""), r.get("url", "")))
            else:
                lines.append("- {}".format(r.get("title", "")))
        else:
            lines.append("- " + str(r))
    return NL.join(lines)


def push_discord(digest, txt_path=None):
    if not config.discord_ready():
        print("  (未配置 DISCORD_BOT_TOKEN/DISCORD_CHANNEL_ID, 跳过推送)")
        return 0
    token, ch = config.DISCORD_BOT_TOKEN, config.DISCORD_CHANNEL_ID
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(
        {"https": config.PUSH_PROXY} if config.PUSH_PROXY else {}))
    m = digest["meta"]
    gname = collector.group_name(m["raw_chat"]) if m.get("raw_chat") else m["chat"]

    embed_desc = ""
    for i, k in enumerate(digest["hot"][:6], 1):
        embed_desc += "**{}. {}** — {}{}{}{}{}".format(
            i, k.get("topic"), k.get("who", ""), NL, k.get("detail", ""), NL, NL)
    embed_desc = embed_desc[:3900] or "(无)"

    boundary = "----smd" + str(int(time.time()))
    attachments, blobs = [], []
    idx = 0
    for t in digest.get("thumbs", []):
        p = t["path"] if isinstance(t, dict) else t
        desc = t.get("desc", "群内图片") if isinstance(t, dict) else "群内图片"
        if os.path.exists(p):
            attachments.append({"id": idx, "filename": os.path.basename(p),
                                "description": desc})
            blobs.append((os.path.basename(p), open(p, "rb").read(), "image/jpeg"))
            idx += 1
    for p in digest.get("files", []):
        if os.path.exists(p):
            attachments.append({"id": idx, "filename": os.path.basename(p)})
            blobs.append((os.path.basename(p), open(p, "rb").read(),
                          "application/octet-stream"))
            idx += 1

    CRLF = chr(13) + chr(10)
    payload = {
        "content": "**{}**{} — 共计 **{}** 条消息".format(
            gname, " ({})".format(m["days_label"]) if m.get("days_label") else "",
            m["total"]),
        "embeds": [{"title": "AI 前沿知识精选",
                    "description": embed_desc,
                    "color": 0x5865F2,
                    "footer": {"text": "筛选自 {} 条消息".format(m["total"])}}],
        "attachments": attachments,
    }
    if digest.get("resources"):
        rdesc = ""
        for r in digest["resources"][:8]:
            if isinstance(r, dict) and r.get("url"):
                title = (r.get("title") or r.get("url"))[:80]
                rdesc += "[{}]({}){}{}{}".format(
                    title, r["url"], NL, (r.get("note") or "") + NL if r.get("note") else "", NL)
        if rdesc:
            payload["embeds"].append({
                "title": "资源/链接",
                "description": rdesc[:3900],
                "color": 0x57F287})
    body = ("--" + boundary + CRLF +
            'Content-Disposition: form-data; name="payload_json"' + CRLF + CRLF +
            json.dumps(payload, ensure_ascii=False) + CRLF).encode("utf-8")
    for a in attachments:
        fname = a["filename"]
        blob, ctype = next((b, c) for n, b, c in blobs if n == fname)
        body += ("--" + boundary + CRLF +
                 'Content-Disposition: form-data; name="files[{}]"; filename="{}"'.format(
                     a["id"], fname) + CRLF +
                 "Content-Type: " + ctype + CRLF + CRLF).encode("utf-8")
        body += blob + CRLF.encode()
    body += ("--" + boundary + "--" + CRLF).encode()

    req = urllib.request.Request(
        "https://discord.com/api/v10/channels/{}/messages".format(ch),
        data=body,
        headers={"Authorization": "Bot " + token,
                 "Content-Type": "multipart/form-data; boundary=" + boundary,
                 "User-Agent": "DiscordBot (https://github.com/JackyCufe/signal-vaults, 1.0)"},
        method="POST")
    r = opener.open(req, timeout=120)
    return r.status


def run_groups(group_keywords, days=1):
    results = []
    for kw in group_keywords:
        llm.LLM_USAGE.clear()
        print("=== {} ===".format(kw), flush=True)
        try:
            username, msgs = collector.fetch_messages(kw, days)
            if not msgs:
                print("  无消息, 跳过", flush=True)
                continue
            thumbs = []  # 群聊图片暂不推送, 确认图片有用后再启用 _thumbs_with_context
            files = [f for f in collector.find_files(username, days)
                     if os.path.getsize(f) < 8 * 1024 * 1024]
            parts = summarize_chunks(username, msgs, days, lookback_label=str(days))
            d = merge_knowledge(username, parts, days, len(msgs), raw_msgs=msgs)
            d["meta"]["raw_chat"] = username
            d["meta"]["days_label"] = ""
            d["thumbs"] = thumbs[:8]
            d["files"] = files[:5]
            txt = render_text(d)
            txt_path = os.path.join(config.WORK_DIR,
                                    "know_{}.txt".format(_chat_key(username)))
            open(txt_path, "w", encoding="utf-8").write(txt)
            st = push_discord(d, txt_path)
            from . import feishu
            fs = feishu.push_feishu(d, txt_path)
            u_in = sum(u["in"] for u in llm.LLM_USAGE)
            u_out = sum(u["out"] for u in llm.LLM_USAGE)
            print("  -> Discord HTTP {} ({}条, 知识{}条, 链接{}条) [tokens in={} out={}]".format(
                st, d["meta"]["total"], len(d["hot"]), len(d.get("resources", [])),
                u_in, u_out), flush=True)
            results.append((kw, st))
        except Exception as ex:
            print("  失败: {}".format(ex), flush=True)
            results.append((kw, str(ex)))
    return results


def _subscribed_ghs(days):
    """仅取【已订阅】公众号(靠 extra_buffer 品牌订阅位): {gh_id: 显示名}
    订阅判定: contact 表 extra_buffer 第4字节=0x03/0x83 (微信支付/微信运动等必然订阅号均命中此模式)
    """
    import hashlib as _hl
    contact_db = os.path.join(config.DEC_DIR, "contact_contact.db")
    names = {}
    try:
        con = sqlite3.connect(contact_db)
        for username, nick in con.execute(
                "SELECT username, nick_name FROM contact "
                "WHERE username LIKE 'gh_%' AND delete_flag=0 "
                "AND substr(extra_buffer,4,1) IN (X'03', X'83')"):
            names[username] = nick or username
        con.close()
    except Exception:
        pass
    found = {}
    since = time.time() - days * 86400
    for db in sorted(glob.glob(os.path.join(config.DEC_DIR, "message_biz_message_*.db"))):
        try:
            con = sqlite3.connect(db)
            ghs = [r[0] for r in con.execute(
                "SELECT user_name FROM Name2Id WHERE user_name LIKE 'gh_%'")]
            tabs = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            for gh in ghs:
                if gh in found or gh not in names:
                    continue
                t = "Msg_" + _hl.md5(gh.encode()).hexdigest()
                if t in tabs and con.execute(
                        "SELECT 1 FROM {} WHERE create_time > ? LIMIT 1".format(t),
                        (since,)).fetchone():
                    found[gh] = names.get(gh, gh)
            con.close()
        except Exception:
            pass
    return found


# 公众号抓取清单: 只抓这里的号 (显示名: gh_id); 想增删直接改这个 dict
# gh_id 查法: signal-vaults groups 无关; 在微信 contact 库里搜公众号昵称得到 username
MP_LIST = {
    # "示例公众号": "gh_xxxxxxxxxxxx",
}


def run_mp(days=3, ghs=None):
    """公众号文章日报 (仅抓取 MP_LIST 清单内的订阅号; ghs: {显示名: gh_id}"""
    if not ghs:
        ghs = MP_LIST
    print("=== 公众号文章采集 === ({} 个公众号, 近{}天)".format(len(ghs), days), flush=True)
    arts = collector.fetch_articles(days, ghs)
    for name, lst in arts.items():
        print("  {}: {} 篇 (近{}天)".format(name, len(lst), days), flush=True)
    all_arts = [a for lst in arts.values() for a in lst]
    all_arts.sort(key=lambda x: -x["ts"])
    if not all_arts:
        print("  无文章", flush=True)
        return
    text = NL.join("[{}] {}: {} — {}".format(
        a["time"], a["gh"], a["title"], (a.get("digest") or "")[:120]) for a in all_arts)
    head = ("以下是最近{}天关注的AI类公众号文章推送列表。默认全部保留, "
            "给每篇写1-2句推荐语(这篇文章讲什么/值得读的点); "
            "纯生活游记等与AI/科技完全无关的才标记skip。只输出JSON(不要markdown):").format(days)
    example = '{"articles":[{"title":"原文标题(一字不差)","note":"1-2句推荐语","skip":false}]}'
    notes = {}
    try:
        raw = llm.chat(text[:16000], system=head + NL + example)
        for it in _parse_llm_json(raw).get("articles", []):
            notes[it.get("title", "")] = (it.get("note", ""), bool(it.get("skip")))
    except Exception as e:
        print("  LLM推荐语失败, 退回原文摘要: {}".format(str(e)[:60]), flush=True)
    hot, res = [], []
    for a in all_arts:
        note, skip = notes.get(a["title"], (a.get("digest") or "", False))
        if skip:
            continue
        d = note or a.get("digest") or ""
        hot.append({"topic": a["title"], "detail": d, "who": ""})
        res.append({"title": a["title"], "url": a["url"], "note": d})
    digest = {"hot": hot, "resources": res, "jargon": [],
              "meta": {"chat": "公众号文章", "days": days, "total": len(all_arts)},
              "thumbs": [], "files": []}
    txt = render_text(digest)
    txt_path = os.path.join(config.WORK_DIR, "know_gongzhonghao.txt")
    open(txt_path, "w", encoding="utf-8").write(txt)
    st = push_discord(digest, txt_path)
    from . import feishu
    feishu.push_feishu(digest, txt_path)
    print("-> Discord HTTP {} ({}篇, 精选{}条)".format(st, len(all_arts), len(hot)), flush=True)
