---
name: signal-vaults
description: 安装、首次配置或运行 signal-vaults：从本机微信生成微信群和公众号 AI 知识日报，推送飞书卡片和 Discord。适用于用户要初始化日报、选择群聊、维护公众号名单或排查推送。
---

# Signal Vaults

用本仓库的 `signal-vaults` CLI 从用户本机微信数据生成 Markdown 知识日报（微信群聊 + 公众号），推送飞书卡片 / Discord。
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

> 1️⃣ **推送方式**：要不要推送到飞书 / Discord？还是仅保存到本地？（可以都要，也可以只要其中一个）
> 2️⃣ **目标群聊**：请提供要生成日报的群聊名称（不确定名称可让我运行 `signal-vaults groups` 列出候选）。
> 3️⃣ **目标公众号**：请提供要追踪的公众号名称（初始名单为空，名单存于 `signal_vaults/daily.py` 的 `MP_LIST`，用户报名称后你协助填入；格式见该文件内注释）。
>
> 💡 飞书需要自建应用凭证（FEISHU_APP_ID/SECRET + FEISHU_TARGET_CHAT），配置教程：`docs/feishu-setup.md`；Discord 需要 bot token（DISCORD_BOT_TOKEN/CHANNEL_ID），配置教程：`docs/discord-setup.md`。还没配置的话，等我按你的回答给你配置教程。

用户作答后**如实记录**（是否推送、推送到哪个端、目标群聊名称、公众号名单），第一轮交互结束。
不得在这轮里追问额外问题，不得代替用户做选择。
注意：第 2 问确定的是**微信群聊**目标（日报数据源），第 3 问确定的是**公众号**追踪名单——两者独立，别混淆。

---

## 第二轮交互：按用户回答走分支

### 分支 ①｜仅本地 + 两个来源齐全 → 直接开干

- 不需要推送，且群聊/公众号名称都已给出。
- 直接执行第三轮（见下），产出 `work/know_*.txt`，报告文件路径即完成。

### 分支 ②｜要推送但没配置 → 先教学，后确认

1. 按用户选择的端输出配置教学：
   - **飞书**：指向 `docs/feishu-setup.md`（手把手图文教程）+ 极简概要：创建企业自建应用 → 复制 App ID/Secret → 权限开通 `im:message` 等 → 事件订阅选【长连接】+ `im.message.receive_v1` → 发布版本 → bot 拉进目标群 → chat_id 填 `FEISHU_TARGET_CHAT`
   - **Discord**：指向 `docs/discord-setup.md`（手把手图文教程）+ 极简概要：开发者门户创建 Application → Bot 页复制 Token → 开启 Message Content Intent → 邀请 bot 进服务器 → Channel ID 写入 `.env`
2. **不要**让用户把任何 token 粘贴到聊天里；密钥只进本地 `.env`。
3. 配置完成后运行 `signal-vaults doctor` 确认所选项已配置。
4. 二次确认：**"群聊 = X、公众号 = Y、推送到 [飞书/Discord/两者]，是否确认开始生成？"** —— 确认后才进入第三轮。

### 分支 ③｜已配置 → 直接开干 + 推送

- 直接执行第三轮，完成后核对日志：飞书 `-> 飞书推送 OK`、Discord `-> Discord HTTP 200`，向用户报告。

---

## 第三轮运行：实际执行

```bash
signal-vaults daily <天数> "<已确认的群名>"   # 群聊日报
signal-vaults mp <天数>                        # 公众号日报
```

- 结果文件：`work/know_*.txt`（Markdown）；分片缓存 `work/parts/`
- **飞书卡片格式（已定稿）**：首行群名+统计 → 编号知识点（加粗标题/摘要/署名/📎原文引用块）→ hr → 资源/链接区（纯可点击链接）
- **溯源**：`SIG_VAULTS_TRACE=1` 时每条知识点附📎原文引用块（逐字原文，refs 经代码校验防编造）
- **链接校验**：只放行聊天记录中真实出现过的域名；LLM 编造的链接被拦且不出现在卡片里
- 交付前自检（三条都必须过）：
  1. 内容为可读 Markdown
  2. 不出现 `gh_xxx` 等内部 ID（群名一律解析，不显示 chatroom ID）
  3. 链接均为完整 URL，且域名来自聊天记录原文
- Discord 模式：确认日志出现 `-> Discord HTTP 200`
- 仅本地模式：向用户报告文件绝对路径即完成

## 运行命令参考

```bash
signal-vaults doctor
signal-vaults groups [关键词]
signal-vaults daily 2 "已确认的群名"
signal-vaults mp 3
```

`mp` 没有文章时输出"无文章"是正常结果。

## LLM 选择

默认建议在 `.env` 中设置：

```env
LLM_BACKEND=auto
```

`auto` 会优先使用已配置的兼容 API；未提供 `LLM_API_KEY` 时，会使用本机 `codex login` 的登录态（前提是 Codex CLI 可用）。若用户明确要求，可设置 `LLM_BACKEND=codex` 或 `LLM_BACKEND=api`。

## 安全红线（任何分支都必须遵守）

- **禁止**读取、上传或展示 `all_keys.json`（等同于聊天记录访问凭证）
- **禁止**修改 `~/.wechat-cli/` 目录
- **禁止**要求用户在聊天中发送 token / API key；一切密钥只进本地 `.env`
- **禁止**把聊天记录原文发送给用户以外的服务
- 仅处理用户本人设备上的微信数据

## 相关文档

- 配置模板：`.env.example`
- 飞书配置手把手教程（含截图位）：`docs/feishu-setup.md`
- Discord 配置手把手教程：`docs/discord-setup.md`
- 迭代历史：`CHANGELOG.md`
