# Signal Vaults

**微信群 / 公众号 AI 知识日报** — 本地解密微信数据库 → LLM 提炼知识 → 飞书卡片 / Discord 推送。

为 **AI Agent（Codex / Claude Code / 任何 CLI Agent）** 设计：单命令运行、环境变量配置、JSON 中间产物、零交互。

> 解密与密钥提取基于 [wechat-cli-plus](https://github.com/maomao3334/wechat-cli-plus)（Apache-2.0），支持 **微信 4.1.x**，跨 **Windows / macOS / Linux** 三平台。本仓库在其上实现日报业务层。

迭代历史见 [CHANGELOG.md](CHANGELOG.md)。

---

## 它做什么

| 命令 | 功能 |
|---|---|
| `signal-vaults doctor` | 环境自检：数据目录 / 密钥 / LLM / 推送配置 |
| `signal-vaults groups [关键词]` | 列出群与会话（供 Agent 选择目标群） |
| `signal-vaults daily [days] [群...]` | 群聊知识日报：分片 LLM 提炼 → 知识点 + 术语科普 + 资源链接，带缓存与重试 |
| `signal-vaults mp [days]` | 公众号文章日报：抓取推送 → LLM 写推荐语 → 输出 |

输出默认写到 `work/know_*.txt`；配置了飞书 / Discord 环境变量则同时推送。

## 核心能力（v1.3）

- **飞书卡片推送**：1.0 结构 interactive 卡片，格式定稿——首行群名+统计 → 编号知识点（标题/摘要/署名/📎原文引用块）→ 资源/链接区（纯可点击链接）。WebSocket 长连接 bot 支持群内 @bot 交互。
- **原文溯源**（`SIG_VAULTS_TRACE=1`）：LLM 提炼时引用消息编号（refs），代码校验必须是本群真实存在的消息 ID，防编造；卡片内逐字展示被引用的消息原文（只显示 refs 指向的消息，不带邻居）。
- **链接校验**：只放行聊天记录中真实出现过的域名；LLM 凭空编造的链接一律拦截且不出现在卡片里。
- **群名解析**：卡片永不显示 chatroom ID，一律解析为群名称。

## 快速开始

```bash
# 0) 前置：微信桌面端已登录过、数据库在本机（微信进程无需常驻）
pip install git+https://github.com/maomao3334/wechat-cli-plus.git

# 1) 提取数据库密钥（微信需处于登录状态；Windows 直接跑，macOS/Linux 需 sudo）
wechat-cli init
#    生成 ~/.wechat-cli/all_keys.json + config.json（数据目录自动检测）

# 2) 安装本工具
pip install .

# 3) 配置 LLM（任何 OpenAI 兼容端点）
export LLM_API_KEY=sk-xxx
export LLM_BASE_URL=https://api.deepseek.com        # 示例
export LLM_MODEL=deepseek-chat
```

## 配置（.env 或环境变量）

| 变量 | 说明 |
|---|---|
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | LLM 必填（OpenAI 兼容端点） |
| `LLM_BACKEND` | `auto`（默认）/ `api` / `codex`；auto 优先 API，无 key 时用 codex 登录态 |
| `SIGNAL_VAULTS_KEYS_FILE` | 微信密钥文件路径（默认 `~/.wechat-cli/all_keys.json`） |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书自建应用凭证（WebSocket 长连接） |
| `FEISHU_TARGET_CHAT` | 接收日报的群 chat_id（`oc_` 开头） |
| `DISCORD_BOT_TOKEN` / `DISCORD_CHANNEL_ID` | Discord 推送（可选） |
| `PUSH_PROXY` | 推送代理（如 `http://127.0.0.1:7897`） |
| `SIG_VAULTS_TRACE` | `1` 开启消息溯源（卡片附📎原文引用块） |
| `SIG_VAULTS_TOPIC` / `SIG_VAULTS_STYLE` | 主题聚焦 / 语气风格定制 |

### 飞书应用配置步骤

1. [open.feishu.cn](https://open.feishu.cn) → 开发者后台 → 创建企业自建应用
2. 「凭证与基础信息」复制 App ID / App Secret → 填入 `.env`
3. 「权限管理」开通 `im:message`（获取与发送单聊/群组消息）
4. 「事件与回调」→ 订阅方式选【使用长连接接收事件】→ 添加事件 `im.message.receive_v1`
5. 「版本管理与发布」→ 创建版本 → 发布（管理员扫码通过）
6. 把 bot 拉进目标群，群 chat_id 填入 `FEISHU_TARGET_CHAT`

## 日常运行

```bash
signal-vaults daily 1 "群名"     # 群聊日报（近1天）
signal-vaults mp 3               # 公众号日报（近3天）
signal-vaults doctor             # 环境自检
signal-vaults groups [关键词]    # 列出可选群
```

- 分片提炼结果缓存在 `work/parts/`，重跑只处理新增消息
- 推送顺序：飞书卡片 → Discord；都未配置则仅输出本地文件

## 公众号名单

公众号追踪名单维护于 `signal_vaults/daily.py` 的 `MP_LIST`（名称 + 抓取配置，文件内有格式注释）。

## 交付自检（Agent 适用）

1. 输出为可读 Markdown
2. 不出现 `gh_xxx` 等内部 ID
3. 链接均为完整 URL 且来自聊天记录原文（域名必须在聊天中出现过）

## 安全红线

- **禁止**读取、上传或展示 `all_keys.json`（等同于聊天记录访问凭证）
- **禁止**修改 `~/.wechat-cli/` 目录
- **禁止**要求用户在聊天中发送 token / API key；一切密钥只进本地 `.env`
- **禁止**把聊天记录原文发送给用户以外的服务
- 仅处理用户本人设备上的微信数据

## 相关文档

- Discord 配置教程：`docs/discord-setup.md`
- 配置模板：`.env.example`
- 迭代历史：`CHANGELOG.md`
