# Discord Bot 配置手把手教程

> 本教程教你从零创建一个 Discord 服务器和 Bot，拿到 `DISCORD_BOT_TOKEN` 和 `DISCORD_CHANNEL_ID`，填入项目 `.env`，让日报自动推送到你的频道。
> 全程约 8 分钟，只需要浏览器和 Discord 客户端。

---

## 第 1 步：新建一个 Discord 服务器

> 如果你已有现成的服务器（想用现有频道收日报），可以跳到第 2 步。

1. 打开 Discord 客户端（桌面版或网页版均可，https://discord.com）
2. 在左侧服务器列表最下方，点击 **「+ 添加服务器」**
3. 选择 **「Create my own」** → 「For me and my friends」之类的模板均可
4. 输入服务器名（比如 `Signal Vaults`），可选上传头像，点 **「创建」**
5. 创建后默认会有一个 `#常规` 文字频道；建议右键改名为 `#wechat`（专门收微信日报，后面频道 ID 就用它）

![第1步：点击添加服务器](assets/discord/step1-add-server.png)

选择「亲自创建」，输入服务器名（如 `Signal Vaults`）

![第1步：创建 Signal Vault 服务器和 wechat 频道](assets/discord/step1-server-wechat-channel.png)

---

## 第 2 步：创建 Discord 应用

1. 打开浏览器，访问 Discord 开发者门户：**https://discord.com/developers/applications**
2. 用你的 Discord 账号登录
3. 点击右上角 **「New Application」**
4. 输入名字（比如 `signal-vaults-bot`），勾选同意条款，点 **「Create」**

![第2步：New Application 按钮](assets/discord/step2-new-application.png)

![第2步：填写应用名并创建](assets/discord/step2-create-app-dialog.png)

---

## 第 3 步：获取 Bot Token（DISCORD_BOT_TOKEN）

1. 在左侧边栏点击 **「Bot」**
2. 找到 **「Token」** 区域，点击 **「Reset Token」**，确认弹窗
3. **立即复制**弹出的 token（只显示这一次！）
   - Token 长这样：`MTU0NDI3NDk1NzY3MDk0...`（一长串字母数字点分格式）
   - ⚠️ 这是 bot 的"密码"，**绝不外泄、不要提交到 git、不要截进图里**
4. 把 token 填入项目根目录 `.env`（没有就请codex从 `.env.example` 复制一份）：

```
DISCORD_BOT_TOKEN=粘贴你的token
```

![第3步：Bot 页面找到 Reset Token](assets/discord/step3-bot-token.png)

---

## 第 4 步：开启 Message Content Intent

1. 还是在 **「Bot」** 页面，往下滚动找到 **「Privileged Gateway Intents」**
2. 打开 **「Message Content Intent」** 开关
3. 点页面底部 **「Save Changes」**

> ⚠️ 不开这个开关，bot 会连不上（报错 `Used disallowed intents`）。

![第4步：Privileged Gateway Intents 开关](assets/discord/step4-message-content-intent.png)

---

## 第 5 步：把 Bot 邀请进你的服务器

1. 左侧边栏点击 **「OAuth2」→「URL Generator」**
2. 在 **Scopes** 勾选 `bot`
3. 在下方 **Bot Permissions** 勾选 `Send Messages`（发送消息）
4. 复制页面底部生成的 **邀请链接**，粘贴到浏览器打开
5. 在服务器下拉框里选中**第 1 步创建的服务器**（如 `Signal Vaults`），点授权

![第5步：OAuth2 URL Generator 勾选权限](assets/discord/step5-oauth-url-generator.png)

![第5步：选择刚创建的服务器并授权](assets/discord/step5-authorize-server.png)

---

## 第 6 步：获取频道 ID（DISCORD_CHANNEL_ID）

1. 在 Discord 客户端：**设置 → 高级 → 开发者模式**，打开
2. 右键点击你想接收日报的**文字频道**（如 `#wechat`；第 1 步新建的服务器即 `#常规`改名后的频道）
3. 点 **「复制服务器 ID」→「复制频道 ID」**（开发者模式下右键菜单里会出现"复制 ID"）
4. 填入 `.env`：

```
DISCORD_CHANNEL_ID=粘贴频道ID
```

![第6步：开启开发者模式](assets/discord/step6-developer-mode.png)

![第6步：右键频道复制 Channel ID](assets/discord/step6-copy-channel-id.png)

---

## 第 7 步：测试连通性

国内网络需要代理。在 `.env` 里补一行：

```
PUSH_PROXY=http://127.0.0.1:7897   # 换成你自己的代理端口，如果不知道可以让AI查一下
```

然后跑一次日报验证：

```bash
signal-vaults daily 1 "某个群名"
```

看到日志末尾 `-> Discord HTTP 200` 就说明推送成功了，去频道里看日报吧 🎉

---

## 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| `WebSocket closed with 4004` | token 无效（被重置过/复制不全） | 回第 2 步重新 Reset Token |
| `Used disallowed intents` | 没开 Message Content Intent | 回第 3 步 |
| `Missing Permissions` / `403` | bot 没被邀请进该频道所在服务器，或没发消息权限 | 回第 4 步重新邀请并勾 Send Messages |
| `Discord HTTP 0` / 连接超时 | 网络被墙 | 配置 `PUSH_PROXY`，确认代理在运行 |
| 发了消息但频道看不到 | channel ID 填错 | 回第 5 步重新复制 |

---

## 安全提醒

- token 等同于 bot 账号的控制权，泄露后任何人可以用你的 bot 身份发消息
- `.env` 已被 `.gitignore` 排除，**永远不要**把它提交进 git
- 怀疑泄露：立刻回开发者门户 **Reset Token**，旧 token 立即失效
