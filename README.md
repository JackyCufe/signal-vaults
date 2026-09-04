# Hermes WeChat

**微信群 / 公众号 AI 知识日报** — 本地解密微信数据库 → LLM 提炼知识 → Discord/终端输出。

为 **AI Agent（Codex / Claude Code / 任何 CLI Agent）** 设计：单命令运行、环境变量配置、JSON 中间产物、零交互。

> 解密与密钥提取基于 [wechat-cli-plus](https://github.com/maomao3334/wechat-cli-plus)（Apache-2.0），支持 **微信 4.1.x**，跨 **Windows / macOS / Linux** 三平台。本仓库在其上实现日报业务层。

---

## 它做什么

| 命令 | 功能 |
|---|---|
| `signal-vaults doctor` | 环境自检：数据目录 / 密钥 / LLM / 推送配置 |
| `signal-vaults groups [关键词]` | 列出群与会话（供 Agent 选择目标群） |
| `signal-vaults daily [days] [群...]` | 群聊知识日报：分片 LLM 提炼 → 知识点 + 术语科普 + 资源链接，带缓存与重试 |
| `signal-vaults mp [days]` | 公众号文章日报：抓取推送 → LLM 写推荐语 → 输出 |

输出默认写到 `work/know_*.txt`；配置了 Discord 环境变量则同时推送（含图片附件与 embed 卡片）。

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
export LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4   # 智谱示例
export LLM_MODEL=glm-4-flash

# 4) 自检 + 运行
signal-vaults doctor
signal-vaults daily 1 "Agentic" "Data Go"     # 群名支持模糊匹配，先 signal-vaults groups 看列表
signal-vaults mp 3                            # 公众号日报
```

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `LLM_API_KEY` | ✅ | OpenAI 兼容 API Key |
| `LLM_BASE_URL` | | 默认智谱 `https://open.bigmodel.cn/api/paas/v4`；DeepSeek: `https://api.deepseek.com/v1` |
| `LLM_MODEL` | | 默认 `glm-4-flash` |
| `LLM_PROXY` | | 可选代理 `http://127.0.0.1:7897` |
| `SIGNAL_VAULTS_DB_DIR` | | 微信 `db_storage` 目录（默认自动检测） |
| `SIGNAL_VAULTS_KEYS_FILE` | | 密钥文件（默认 `~/.wechat-cli/all_keys.json`） |
| `SIGNAL_VAULTS_WORK_DIR` | | 工作目录（默认 `./work`） |
| `DISCORD_BOT_TOKEN` / `DISCORD_CHANNEL_ID` | | 配置后自动推送 Discord |
| `PUSH_PROXY` | | Discord 推送代理（默认跟随 `LLM_PROXY`） |

## 平台兼容性

| 平台 | 密钥提取 (`wechat-cli init`) | 本工具 | 备注 |
|---|---|---|---|
| **Windows** | ✅ | ✅ | 微信 4.1.x Config.Cipher 扫描 |
| **macOS** | ✅（需 sudo） | ✅ | 数据目录：`~/Library/Containers/com.tencent.xinWeChat/...` |
| **Linux** | ✅（需 sudo） | ✅ | |

跨平台差异（数据目录检测、路径分隔符、附件目录结构）由上游 `wechat-cli` 统一处理；本仓库只做业务层，无平台分支代码。

## 🤖 Agent 启动提示词

把下面这段直接发给 Codex / Claude Code 等 Agent，它就能从零跑通：

```text
任务：用 signal-vaults 生成本机微信群的知识日报。

步骤：
1. 环境自检：运行 `signal-vaults doctor`。任何 [!!] 项按提示修复：
   - 缺数据目录 → 确认微信已在本机登录过，或设 SIGNAL_VAULTS_DB_DIR 指向 db_storage
   - 缺密钥 → 运行 `wechat-cli init`（微信需登录状态；macOS/Linux 加 sudo）
   - 缺 LLM_API_KEY → 向用户索要，或读取本地 .env 文件
2. 选群：运行 `signal-vaults groups` 查看群列表（或 `signal-vaults groups 关键词` 模糊搜索）。
3. 生成日报：`signal-vaults daily <天数> "<群名1>" "<群名2>"`；公众号用 `signal-vaults mp <天数>`。
4. 结果在 work/know_*.txt（Markdown），已配置 Discord 则同时推送。
5. 故障处理：
   - LLM 超时 → 脚本自带 3 次重试；连续失败检查 LLM_BASE_URL/网络代理
   - 首次运行慢属正常（分片 LLM 调用），结果分片缓存在 work/parts/，重跑秒级
   - 解密报错 → 删 work/decrypted/ 重跑（会全量重解）
不要做的：不要读取或上传 all_keys.json、不要修改 ~/.wechat-cli/、不要把聊天记录发给用户以外的服务。
```

## 架构

```
signal_vaults/
├── config.py     # 环境变量配置层（零硬编码、零敏感信息）
├── llm.py        # OpenAI 兼容 /chat/completions（标准库实现，无 SDK 依赖）
├── collector.py  # SQLCipher 解密(mtime增量) + 会话定位 + 消息/图片/文件/公众号提取
├── daily.py      # 分片 LLM 提炼(≤1800字符/片+缓存+重试) + 合并去重 + Discord multipart 推送
└── cli.py        # doctor / groups / daily / mp 四个子命令
```

## 性能与缓存

- 解密：~120 MB/s，mtime 增量跳过（日常 <1s，全量 ~5s）
- LLM：每片 ≤1800 字符（规避网关非流式超时），分片结果持久缓存于 `work/parts/`，**失败不缓存**（下次自动重试）
- 日常增量运行 2~5 分钟；冷启动 6~8 分钟

## 免责声明

本项目仅用于处理**本人自己设备上**的微信数据（个人知识管理）。请勿用于监控他人、批量采集或任何违反微信使用条款的场景。密钥文件（`all_keys.json`）等同于聊天记录的访问凭证，切勿提交到版本库或分享给他人。

## License

Apache-2.0（继承上游 [wechat-cli-plus](https://github.com/maomao3334/wechat-cli-plus)）
