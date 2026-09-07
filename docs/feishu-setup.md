# 飞书 Bot 配置手把手教程

飞书推送走**企业自建应用 + WebSocket 长连接**：无需公网服务器 / 回调地址，本机直连；既能**推卡片日报**进群，也能在群里 **@bot 交互**。

配置完成后写入项目根目录 `.env`（不要把真实 `.env` 提交到 Git）。

---

## 第 1 步：创建企业自建应用

1. 打开 [open.feishu.cn](https://open.feishu.cn)，用你的飞书账号登录
2. 进入 **开发者后台** → **创建企业自建应用**

![打开飞书开放平台并进入开发者后台](assets/feishu/01-create-app-open-feishu.png)

3. 填写应用名称（如 `Signal Vaults`）和描述，创建

![填写应用名称与描述](assets/feishu/02-create-app-fill-name.png)

![应用创建完成](assets/feishu/03-create-app-created.png)

---

## 第 2 步：获取凭证

1. 应用详情页 → **凭证与基础信息**
2. 复制 **App ID**（`cli_` 开头）和 **App Secret**

![凭证与基础信息页，复制 App ID 和 App Secret](assets/feishu/04-credentials-appid-secret.png)

写入项目根目录 `.env`：

```env
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 第 3 步：开通权限

1. 左侧 **权限管理**
2. 开通以下**最小权限集**（满足日报推送 + 群内 @bot 交互所需，不要全量授权）：

| 权限 | 用途 |
|---|---|
| `im:message` | 发送消息（日报卡片） |
| `im:message:send_as_bot` | 以 bot 身份发消息 |
| `im:message.group_at_msg:readonly` | 接收群里 @bot 的消息（交互命令） |
| `im:message.p2p_msg:readonly` | 接收单聊消息（可选，私聊交互用） |
| `im:chat:readonly` | 读取群信息（群名解析，卡片不显示 chatroom ID） |
| `im:resource` | 发送图片资源（缩略图附件） |

> 💡 权限管理页支持**批量导入**：点「开通权限」旁的批量导入，粘贴以下 JSON 一次开通：

```json
{
  "scopes": {
    "tenant": [
      "im:message",
      "im:message:send_as_bot",
      "im:message.group_at_msg:readonly",
      "im:message.p2p_msg:readonly",
      "im:message:readonly",
      "im:chat:read",
      "im:chat:readonly",
      "im:resource"
    ]
  }
}
```

![权限批量导入](assets/feishu/05-scopes-import.png)

> ⚠️ **安全提示**：只开上表所列权限即可。开放平台权限列表很长（文档/多维表格/邮箱等），全量勾选会过度授权，开源使用场景不需要。

---

## 第 4 步：订阅事件（长连接方式）

1. 左侧 **事件与回调** → 订阅方式选择 **【使用长连接接收事件】**

![选择长连接接收事件](assets/feishu/06-events-long-connection.png)

2. **添加事件** → 搜索并添加：
   - `im.message.receive_v1`（**必需**：接收消息，@bot 交互靠它）
   - 可选按需：`im.chat.member.bot.added_v1`（bot 进群事件）、`im.message.recalled_v1` 等

3. 同一页面的 **回调配置**（「事件配置」右边）也选择 **长连接**，并勾选 **卡片回传交互**（卡片按钮回调用）

![回调配置同样选长连接并勾选卡片回传交互](assets/feishu/07-callback-config-long-connection.png)

---

## 第 5 步：发布应用

1. 左侧 **版本管理与发布** → **创建版本**
2. 填写版本号（如 `1.0.0`）和更新说明，点击最下方 **保存**
3. **申请发布** → 管理员（可能是你自己）扫码通过

![创建版本并申请发布](assets/feishu/08-version-publish.png)

---

## 第 6 步：把 bot 拉进目标群

1. 在飞书客户端打开目标群 → **设置** → **群机器人** → **添加机器人** → 选刚发布的 `Signal Vaults`

![群里添加机器人](assets/feishu/09-group-add-bot.png)

2. 获取群 chat_id：在群里 **@bot 发一句 `群ID`**（或使用你已有的查询方式），得到 `oc_` 开头的 ID

![获取群 chat_id](assets/feishu/10-group-chat-id.png)

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

![群里收到的日报卡片](assets/feishu/11-verify-daily-card.png)

---

## 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `doctor` 显示飞书未配置 | `.env` 里 App ID/Secret 没填或没保存 |
| 推送成功但群里看不到卡片 | bot 没拉进目标群；或 `FEISHU_TARGET_CHAT` 不是该群的 `oc_` ID |
| @bot 没反应 | 第 4 步长连接没选 / `im.message.receive_v1` 没订阅 / 应用没发布 |
| 卡片按钮点了没反应 | 第 4 步回调配置没勾「卡片回传交互」 |
| 卡片空白 | 旧版本卡片结构问题，更新到最新代码（≥ v1.3） |
| 想换推送群 | 更新 `.env` 的 `FEISHU_TARGET_CHAT` 为新群 ID 即可 |

---

## 安全提醒

- App Secret 等同于应用凭证：**只写本地 `.env`，绝不提交 Git、绝不发到聊天**
- 权限按需开通（见第 3 步最小权限集），不要全量授权
- bot 拉进群后可读取群消息（用于日报），请注意目标群的隐私边界
