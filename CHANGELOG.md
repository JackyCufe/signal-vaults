# Changelog

本文件记录 signal-vaults 的全部迭代历史。最新在前。

## v1.0.0 (2026-09) — 首个正式发布

### Added

- **微信群聊知识日报**：本机解密微信数据库 → 分片 LLM 提炼 → 知识点 + 术语科普 + 资源链接，分片缓存与重试（`signal-vaults daily <天数> "<群名>"`）
- **公众号文章日报**：追踪名单聚合推送文章 → LLM 撰写推荐语（`signal-vaults mp <天数>`）
- **飞书卡片推送**：1.0 结构 interactive 卡片，格式定稿——首行群名+统计 → 编号知识点（加粗标题/摘要/署名/📎原文引用块）→ hr 分割 → 资源/链接区（纯可点击链接）；WebSocket 长连接 bot 支持群内 @bot 交互
- **Discord 推送**：embed 渲染与飞书卡片对齐（同样的溯源块与链接区），HTTP 200 校验
- **消息溯源**（`SIG_VAULTS_TRACE=1`）：LLM 提炼时引用消息编号（refs），代码校验必须是本群真实存在的消息 ID，防编造；卡片逐字展示被引用的消息原文（只显示 refs 指向的消息，不带邻居）
- **链接校验**：三级来源验证——域名必须在聊天记录中出现过 → URL 路径必须在原文有踪迹 → LLM 编造的链接（如自拼的 GitHub 仓库路径、不存在的官方文档地址）一律拦截且不出现在卡片里；URL 两侧统一还原 `&amp;` 转义，白名单从消息 raw 全文收集
- **环境自检**：`signal-vaults doctor`（数据目录/密钥/LLM/推送配置）、`signal-vaults groups [关键词]`
- **主题/风格定制**：`SIG_VAULTS_TOPIC` / `SIG_VAULTS_STYLE` 环境变量
- **LLM 后端自动选择**：`LLM_BACKEND=auto` 优先 OpenAI 兼容 API，无 key 时回落本机 Codex CLI 登录态
- **配置教程**：`docs/feishu-setup.md`（11 步图文，最小权限集 + 批量导入 JSON）、`docs/discord-setup.md`

### Fixed

- 飞书卡片偶发空白：v2 结构（body.elements）会被服务端静默丢弃，固定使用 1.0 结构（顶层 elements）；消息中的控制字符（如 `\u0001`）也会导致整卡被丢，构建时强制清洗
- 超链接时有时无：裸 `a` 元素会被服务端拒收，链接统一用 markdown 内嵌 `[文字](URL)` 写法
- 群聊 ID 泄漏进卡片标题：一律经 `group_name()` 解析为群名称
- refs 在 LLM 重排后丢失：topic 文字被改写导致精确匹配失败，改用互含子串映射
- URL 白名单误杀真实链接 / 放行编造链接：转义还原 + raw 全文收集 + 域名级与路径级来源验证逐层收紧
- Windows 控制台 UTF-8 输出、截断的 LLM JSON 容错恢复

### Security

- 密钥（微信/飞书/Discord/LLM）只存本地 `.env`，绝不入库；git 历史经全量扫描确认零泄漏
- 聊天数据仅在本机处理，原文不发送给用户以外的服务
- 飞书应用权限文档化最小权限集，避免全量授权

---

## 内部预览 (2026-08)

v1.0.0 之前的内部迭代（hermes-wechat v0.1.0 起）：微信采集与日报管线、Discord webhook 推送、公众号源、飞书 post → 卡片演进、HN/Reddit 外部源雏形（未纳入本发布范围，将出现在后续版本）。
