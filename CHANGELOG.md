# Changelog

本文件记录 signal-vaults 的全部迭代历史。最新在前。

## v1.3 (2026-09) — 微信增强版：飞书卡片 + 原文溯源 + 链接校验

### 飞书端
- **卡片推送**（`signal_vaults/feishu.py`）：1.0 结构 interactive 卡片（顶层 elements），格式定稿——
  首行群名+统计 → 编号知识点（加粗标题/摘要/署名/📎原文引用块）→ hr 分割 → 资源/链接区（纯可点击链接）
- **WebSocket 长连接 bot**：群内 @bot 双向交互，无需公网回调
- 卡片发送后按 message_id 精确回查验收（message.list 分页缓存不可靠）

### 原文溯源（SIG_VAULTS_TRACE=1）
- LLM 提炼时引用消息编号（refs），代码校验必须是本群真实 local_id，防编造
- 📎 原始上下文只显示 refs 指向的消息原文（radius=0，不带邻居消息），逐字保留
- 控制字符清洗（\u0001 等会令飞书服务端静默丢弃整个 elements）
- refs 经 LLM 重排后用互含子串映射回条目（fuzzy topic→refs mapping）

### 链接校验
- 只拦「聊天记录里从未出现过的域名」（LLM 编造的典型特征）；域名出现过即放行
- URL 两侧统一还原 `&amp;` 转义；白名单从消息 raw 全文收集（display 截断 120 字符会丢参数）
- 被拦的编造链接从资源区完全移除（连标题都不出现）
- 可点击链接使用 markdown 内嵌 `[文字](URL)` 写法（服务端转为 a 标签；裸 a 元素会被拒收）

### 其他
- 群名显示解析（永不显示 chatroom ID）
- 分片提炼缓存按 refs 完整性失效重跑

## v1.2 (2026-08) — 推送通道

- Discord webhook 推送（HTTP 200 校验）
- 飞书 rich-text post → interactive 卡片演进
- 主题/风格定制环境变量（SIG_VAULTS_TOPIC / SIG_VAULTS_STYLE）

## v1.1 (2026-08) — 公众号源

- 公众号文章聚合（MP_LIST 名单维护于 `signal_vaults/daily.py`）
- `signal-vaults mp <天数>` 子命令

## v1.0 (2026-08) — 初始版本

- 本机微信数据采集（本地 DB 解密，密钥不上传）
- 微信群聊日报：`signal-vaults daily <天数> "<群名>"`
- LLM 分片提炼（DeepSeek 兼容 API / codex login 自动后端）
- Markdown 日报输出至 `work/know_*.txt`
- `signal-vaults doctor` / `groups` 环境自检
