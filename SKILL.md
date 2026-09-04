---
name: signal-vaults
description: 安装、首次配置或运行 signal-vaults：从本机微信生成微信群和公众号 Markdown 知识日报，并可推送到 Discord。适用于用户要初始化日报、选择群聊、维护公众号名单或排查推送。
---

# Signal Vaults

用本仓库的 `signal-vaults` CLI 从用户本机微信数据生成 Markdown 日报。首次使用时，按下面的顺序引导；日常运行时，只执行用户已经确认的来源。

## 首次配置的对话流程

1. 确认项目已安装。若当前目录不是本仓库，克隆仓库并运行 `pip install .`；若依赖下载超时，按系统设置 `HTTPS_PROXY` 后重试。
2. 运行 `signal-vaults doctor`，只报告微信数据、密钥、LLM 后端和 Discord 的状态，不读取或显示密钥文件内容。
3. **先检查 Discord。** 若 doctor 显示未配置，明确告诉用户：本地 Markdown 仍可生成，但不会自动推送；询问用户是否要启用推送。用户选择启用时，给出下方的 Discord 配置步骤，并要求用户自行把 Token 和 Channel ID 写进本地 `.env`。不要要求用户在聊天中发送 Token。
4. 再询问用户要接入哪个微信群：
   - 用户已给出精确群名时，只处理这个群。
   - 用户不知道群名或明确要求查看候选时，运行 `signal-vaults groups` 或 `signal-vaults groups <关键词>`，展示结果后让用户选择。
   - 不得为了寻找“有消息的群”而扫描、读取或代跑其他群。
5. 提醒用户确认公众号名单。当前项目的公众号日报只读取 `signal_vaults/daily.py` 中的 `MP_LIST`；先说明现有名单，再请用户确认要保留、增加或移除哪些公众号。用户确认后才修改该名单；对外不展示 `gh_xxx` 内部 ID。
6. 完成上述选择后，运行用户确认的群聊日报和/或公众号日报，并检查 `work/know_*.txt` 是否为可读 Markdown、是否隐藏内部 ID、链接是否为完整 URL。Discord 已配置时确认推送结果。

## 运行命令

```bash
signal-vaults doctor
signal-vaults groups
signal-vaults groups 关键词
signal-vaults daily 2 "已确认的群名"
signal-vaults mp 3
```

群名由用户确认后才可传给 `daily`。`mp` 没有文章时输出“无文章”是正常结果。

## LLM 选择

默认建议在 `.env` 中设置：

```env
LLM_BACKEND=auto
```

`auto` 会优先使用已配置的兼容 API；未提供 `LLM_API_KEY` 时，会使用本机 `codex login` 的登录态（前提是 Codex CLI 可用）。因此 Codex 路径不需要额外的 LLM API Key。若用户明确要求，可设置 `LLM_BACKEND=codex` 或 `LLM_BACKEND=api`。

## Discord 配置

引导用户完成以下步骤：

1. 打开 <https://discord.com/developers/applications>，创建 Application，然后在 **Bot** 页面创建 Bot 并复制 Token。
2. 通过 OAuth2 URL Generator 把 Bot 邀请进目标服务器；目标 Channel 至少授予 `View Channel`、`Send Messages`、`Embed Links`、`Attach Files`。
3. 在 Discord 开启 Developer Mode，右键目标 Channel 并复制 Channel ID。
4. 在项目根目录将 `.env.example` 复制为 `.env`，仅在本地填写：

```env
DISCORD_BOT_TOKEN=...
DISCORD_CHANNEL_ID=...
LLM_BACKEND=auto
```

5. 重新运行 `signal-vaults doctor`，确认显示“Discord 推送 = 已配置”。

`.env` 不得提交到 Git，也不得在终端输出、报告或对话中回显 Token。Discord 的价值是可按群聊、公众号或主题创建不同 Channel；当前版本一次推送到配置的一个 Channel。

## 微信前置条件和边界

- 缺微信数据目录：记录“本机未安装微信或未登录过”，停止微信数据相关步骤。
- 缺 `~/.wechat-cli/all_keys.json`：Windows 运行 `wechat-cli init`；macOS/Linux 运行 `sudo wechat-cli init`，之后重跑 doctor。
- 不读取、展示、上传或提交 `all_keys.json`、`.env`、聊天原文或 Discord Token。
- 只处理用户本人设备上的数据和用户明确确认的群聊/公众号来源。

## 完成时的汇报

简要汇报安装、doctor、Discord、已选群聊、公众号名单、执行命令、输出文件和推送结果；失败时附关键错误及已尝试的安全修复。不要在报告中复制聊天原文或密钥。
