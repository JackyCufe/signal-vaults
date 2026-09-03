---
name: signal-vaults
description: 微信群/公众号 AI 知识日报生成：本仓库（signal-vaults）的 signal-vaults CLI 从本地解密微信数据库提取消息，LLM 提炼知识，输出 Markdown 日报。当用户要求生成微信日报、群聊知识总结、运行 signal-vaults 命令时使用。
---

# Signal Vaults — 微信知识日报 Skill（signal-vaults CLI）

## 目标
通过 `signal-vaults` CLI（本仓库 `signal_vaults/` Python 包，`pip install .` 安装）生成本机微信群聊/公众号的 AI 知识日报。

## 何时使用
- 用户要求"生成微信日报 / 总结群聊知识 / 公众号文章摘要"
- 用户提到 `signal-vaults daily` / `signal-vaults mp` / `signal-vaults groups` / `signal-vaults doctor`

## 工作流

### 1. 环境自检
```bash
signal-vaults doctor
```
- 任何 `[!!]` 项按提示修复：
  - 缺数据目录 → 确认微信已在本机登录过，或设 `HERMES_DB_DIR` 指向 `.../db_storage`
  - 缺密钥 → 运行 `wechat-cli init`（微信需登录状态；macOS/Linux 加 sudo）
  - 缺 `LLM_API_KEY` → 向用户索要，或读取本地 `.env`

### 2. 选群
```bash
signal-vaults groups           # 列出全部群与会话
signal-vaults groups 关键词     # 模糊搜索群名
```

### 3. 生成日报
```bash
signal-vaults daily <天数> "<群名1>" "<群名2>"   # 群聊知识日报
signal-vaults mp <天数>                          # 公众号文章日报
```
- 输出：`work/know_*.txt`（Markdown）
- 配置了 `DISCORD_BOT_TOKEN` + `DISCORD_CHANNEL_ID` 则同时推送 Discord

### 4. 排障
- LLM 超时 → 脚本自带 3 次重试；连续失败检查 `LLM_BASE_URL` / `LLM_PROXY`
- 首次运行慢属正常（分片 LLM 调用）；分片缓存于 `work/parts/`，重跑秒级
- 解密报错 → 删 `work/decrypted/` 重跑（会全量重解）

## 安全红线（必须遵守）
- **禁止**读取、上传或展示 `all_keys.json`（等同于聊天记录访问凭证）
- **禁止**修改 `~/.wechat-cli/` 目录
- **禁止**把聊天记录原文发送给用户以外的服务
- 仅处理用户本人设备上的微信数据

## 关键环境变量
| 变量 | 必填 | 说明 |
|---|---|---|
| `LLM_API_KEY` | ✅ | OpenAI 兼容 API Key |
| `LLM_BASE_URL` | | 默认智谱 v4；DeepSeek: `https://api.deepseek.com/v1` |
| `LLM_MODEL` | | 默认 `glm-4-flash` |
| `HERMES_DB_DIR` / `HERMES_KEYS_FILE` / `HERMES_WORK_DIR` | | 路径覆盖（默认自动检测） |
| `DISCORD_BOT_TOKEN` / `DISCORD_CHANNEL_ID` | | 可选，自动推送 |

## 解耦说明
本 SKILL.md 只描述调用方式与安全约束；全部业务逻辑在 `signal_vaults/` Python 包内（`pip install .`），不依赖 SKILL.md 内容运行。
