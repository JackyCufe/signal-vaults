---
name: signal-vaults
description: 安装、首次配置或运行 signal-vaults：从本机微信生成微信群和公众号 Markdown 知识日报，并可推送到 Discord。适用于用户要初始化日报、选择群聊、维护公众号名单或排查推送。
---

# Signal Vaults

用本仓库的 `signal-vaults` CLI 从用户本机微信数据生成 Markdown 日报。
交互固定为**两轮**；实际运行分**三轮**（环境检测 → 采集生成 → 推送/交付）。
日常运行（非首次）时，直接执行用户已确认过的命令，不再重复提问。

---

## 第一轮交互：安装后一次性问齐（3 个问题放在同一条消息里）

用户说"clone 这个仓库并运行"后，先完成准备动作：

```bash
git clone https://github.com/JackyCufe/signal-vaults.git   # 已在仓库内则跳过
cd signal-vaults
pip install .        # 依赖克隆超时 → 设置 HTTPS_PROXY 后重试
signal-vaults doctor # 只报告状态，不读取/显示密钥内容
```

然后**在同一条消息里**发出以下 3 问 + 1 提示，逐字保持顺序：

> 1️⃣ **推送方式**：日报你要推送到 Discord，还是仅保存到本地？
> 2️⃣ **目标群聊**：请提供要生成日报的群聊名称（不确定名称可让我运行 `signal-vaults groups` 列出候选）。
> 3️⃣ **目标公众号**：请提供要追踪的公众号名称（当前名单：`数字生命卡兹克`、`刘小排r`，可增删）。
>
> 💡 如果你想推送 Discord：请先检查项目根目录 `.env`（可从 `.env.example` 复制）中是否已填写 `DISCORD_BOT_TOKEN` 和 `DISCORD_CHANNEL_ID`。还没有的话，等我按你的回答给你配置教程。

用户作答后**如实记录**（推送偏好、群名、公众号名单），第一轮交互结束。
不得在这轮里追问额外问题，不得代替用户做选择。

---

## 第二轮交互：按用户回答走三分支

### 分支 ①｜仅本地 + 两个来源齐全 → 直接开干

- 不需要 Discord，且群聊/公众号名称都已给出。
- 直接执行第三轮（见下），产出 `work/know_*.txt`，报告文件路径即完成。

### 分支 ②｜要 Discord 但没配置 → 先教学，后确认

1. 输出配置教学：指向 `docs/discord-setup.md`（手把手图文教程），并附极简步骤概要：
   - 开发者门户创建 Application → Bot 页复制 Token
   - 开启 **Message Content Intent** → OAuth2 URL 邀请 bot 进服务器（勾 Send Messages）
   - Discord 开发者模式下右键频道复制 Channel ID
   - 写入本地 `.env` 的 `DISCORD_BOT_TOKEN` / `DISCORD_CHANNEL_ID`（国内网络另配 `PUSH_PROXY`）
2. **不要**让用户把 token 粘贴到聊天里；token 只进 `.env` 文件。
3. 用户配置完成后，运行 `signal-vaults doctor` 确认显示 Discord 已配置。
4. 回头二次确认：**"群聊 = X、公众号 = Y，是否确认开始生成？"** —— 用户确认后才进入第三轮。

### 分支 ③｜要 Discord 且已配置 → 直接开干 + 推送

- `.env` 中 token/channel 齐全（doctor 确认通过）。
- 直接执行第三轮，完成后必须核对推送日志 `-> Discord HTTP 200` 并向用户报告。

---

## 第三轮运行：实际执行

```bash
signal-vaults daily <天数> "<已确认的群名>"   # 群聊日报
signal-vaults mp <天数>                        # 公众号日报
```

- 结果文件：`work/know_*.txt`（Markdown）
- 交付前自检（三条都必须过）：
  1. 内容为可读 Markdown
  2. 不出现 `gh_xxx` 等内部 ID
  3. 链接均为完整 URL，且来自聊天记录原文
- Discord 模式：确认日志出现 `-> Discord HTTP 200`；失败时按 `docs/discord-setup.md` 的常见问题表排查后重试一次。
- 仅本地模式：向用户报告文件绝对路径即完成。

## 运行命令参考

```bash
signal-vaults doctor
signal-vaults groups
signal-vaults groups 关键词
signal-vaults daily 2 "已确认的群名"
signal-vaults mp 3
```

`mp` 没有文章时输出"无文章"是正常结果。

## LLM 选择

默认建议在 `.env` 中设置：

```env
LLM_BACKEND=auto
```

`auto` 会优先使用已配置的兼容 API；未提供 `LLM_API_KEY` 时，会使用本机 `codex login` 的登录态（前提是 Codex CLI 可用）。因此 Codex 路径不需要额外的 LLM API Key。若用户明确要求，可设置 `LLM_BACKEND=codex` 或 `LLM_BACKEND=api`。

## 安全红线（任何分支都必须遵守）

- **禁止**读取、上传或展示 `all_keys.json`（等同于聊天记录访问凭证）
- **禁止**修改 `~/.wechat-cli/` 目录
- **禁止**要求用户在聊天中发送 token / API key；一切密钥只进本地 `.env`
- **禁止**把聊天记录原文发送给用户以外的服务
- 仅处理用户本人设备上的微信数据

## 相关文档

- Discord 配置手把手教程（含截图位与常见问题）：`docs/discord-setup.md`
- 配置模板：`.env.example`
