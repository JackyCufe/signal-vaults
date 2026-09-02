# -*- coding: utf-8 -*-
"""LLM 调用 — 标准 OpenAI 兼容 /chat/completions, 零 SDK 依赖。

任何兼容端点都可用 (智谱/DeepSeek/Kimi/OpenAI/本地 vLLM...):
  export LLM_API_KEY=sk-xxx
  export LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
  export LLM_MODEL=glm-4-flash
"""
import json
import urllib.request

from . import config

LLM_USAGE = []  # [{"in":..,"out":..,"total":..,"est":bool}]


def chat(prompt_text: str, system: str = "", max_tokens: int = 4000, timeout: int = 300) -> str:
    if not config.LLM_API_KEY:
        raise RuntimeError(
            "缺少 LLM_API_KEY 环境变量。示例: "
            "export LLM_API_KEY=sk-xxx LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4 LLM_MODEL=glm-4-flash")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt_text})
    body = {"model": config.LLM_MODEL, "messages": messages, "max_tokens": max_tokens}
    handlers = []
    if config.LLM_PROXY:
        handlers.append(urllib.request.ProxyHandler(
            {"http": config.LLM_PROXY, "https": config.LLM_PROXY}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(
        config.LLM_BASE_URL + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + config.LLM_API_KEY,
                 "Content-Type": "application/json"},
        method="POST")
    r = opener.open(req, timeout=timeout)
    data = json.loads(r.read().decode("utf-8"))
    u = data.get("usage") or {}
    if u:
        LLM_USAGE.append({"in": u.get("prompt_tokens", 0),
                          "out": u.get("completion_tokens", 0),
                          "total": u.get("total_tokens", 0), "est": False})
    else:
        tin = (len(system) + len(prompt_text)) // 2
        LLM_USAGE.append({"in": tin, "out": 200, "total": tin + 200, "est": True})
    return data["choices"][0]["message"]["content"]
