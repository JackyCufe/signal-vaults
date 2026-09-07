# 飞书 Bot 配置手把手教程

> 📷 **截图占位说明**：本文档目前为骨架，标有「📷 截图」的位置待补实际操作截图（截图文件放 `docs/assets/feishu/`，命名与标注一致）。

---

## 概览

飞书推送走**企业自建应用 + WebSocket 长连接**：

- 无需公网服务器 / 回调地址，本机直连
- 既能**推卡片日报**进群，也能在群里 **@bot 交互**（查群、跑日报）
- 配置完成后写入项目根目录 `.env`（不要把真实 `.env` 提交到 Git）

---

## 第 1 步：创建企业自建应用

1. 打开 [open.feishu.cn](https://open.feishu.cn)，用你的飞书账号登录
2. 进入 **开发者后台** → **创建企业自建应用**
3. 填写应用名称（如 `Signal Vaults`）和描述，创建

📷 截图：`01-create-app.png`（开发者后台首页 + 创建入口）

---

## 第 2 步：获取凭证

1. 应用详情页 → **凭证与基础信息**
2. 复制 **App ID**（`cli_` 开头）和 **App Secret**

📷 截图：`02-credentials.png`（凭证页，Secret 打码处可后期补）

写入项目根目录 `.env`：

```env
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 第 3 步：开通权限

1. 左侧 **权限管理**
2. 搜索并开通：
   - `im:message`（获取与发送单聊、群组消息）
   - `im:message.group_at_msg`（接收群聊中 @bot 的消息，用于交互）
   - `im:chat`（获取群信息，用于群名解析）

📷 截图：`03-scopes.png`（权限页，已开通列表）

---

## 第 4 步：订阅事件（长连接方式）

1. 左侧 **事件与回调** → 订阅方式选择 **【使用长连接接收事件】**
2. **添加事件** → 搜索并添加：
   - `im.message.receive_v1`（接收消息，交互命令必需）

📷 截图：`04-long-connection.png`（长连接选择页）
📷 截图：`05-add-event.png`（事件添加页）

---

## 第 5 步：发布应用

1. 左侧 **版本管理与发布** → **创建版本**
2. 填写版本号（如 `1.0.0`）和更新说明
3. **申请发布** → 管理员（可能是你自己）扫码通过

📷 截图：`06-publish.png`（版本发布页）

---

## 第 6 步：把 bot 拉进目标群

1. 在飞书客户端打开目标群 → **设置** → **群机器人** → **添加机器人** → 选刚发布的 `Signal Vaults`
2. 获取群 chat_id：在群里 **@bot 发一句 `群ID`**（或使用你已有的查询方式），得到 `oc_` 开头的 ID

📷 截图：`07-add-bot-to-group.png`（群机器人添加页）

写入 `.env`：

```env
FEISHU_TARGET_CHAT=oc_xxxxxxxxxxxxxxxxxx
```

---

## 第 7 步：验证

```bash
signal-vaults doctor          # 应显示 飞书 已配置
signal-vaults daily 1 "群名"  # 推送一张卡片到目标群
```

- 群里收到「Signal Vaults 知识日报」卡片即成功
- 卡片格式：首行群名+统计 → 编号知识点（含 📎 原文引用块，需 `SIG_VAULTS_TRACE=1`）→ 资源/链接区（可点击链接）

📷 截图：`08-card-received.png`（群里收到的日报卡片）

---

## 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `doctor` 显示飞书未配置 | `.env` 里 App ID/Secret 没填或没保存 |
| 推送成功但群里看不到卡片 | bot 没拉进目标群；或 `FEISHU_TARGET_CHAT` 不是该群的 `oc_` ID |
| @bot 没反应 | 第 4 步长连接没选 / 事件没订阅 / 应用没发布 |
| 卡片空白 | 旧版本卡片结构问题，更新到最新代码（≥ v1.3） |
| 想换推送群 | 更新 `.env` 的 `FEISHU_TARGET_CHAT` 为新群 ID 即可 |

---

## 安全提醒

- App Secret 等同于应用凭证：**只写本地 `.env`，绝不提交 Git、绝不发到聊天**
- bot 拉进群后可读取群消息（用于日报），请注意目标群的隐私边界
