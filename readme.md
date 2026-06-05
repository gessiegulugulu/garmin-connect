同步佳明手表的数据给AI，让AI给出更好的运动建议和分析。

## 佳明mcp
仓库地址: https://github.com/Taxuspt/garmin_mcp

装都不用自己装
```bash
Install the Garmin MCP server from https://github.com/Taxuspt/garmin_mcp, authenticate with garmin-mcp-auth, and add it to my MCP configuration without storing my Garmin email or password.
```
运行命令来填写账号和密码
```bash
/home/cair/anaconda3/envs/garmin/bin/garmin-mcp-auth
```
一些配置文件的地址
```bash
~/.garminconnect # OAuth token
~/.codex/config.toml # codex mcp配置
```

## 训练系统

- 当前七日计划：[TRAINING_PLAN.md](TRAINING_PLAN.md)
- 长期训练偏好：[memory.md](memory.md)
- 历史分析与调整：[history](history)

本地 skills 位于 `.agents/skills/`，共享训练协议位于 `.agents/training-system.md`。Codex 通常会自动检测修改；若技能未出现，重新加载 Codex 窗口或开启新会话。

### 使用方法

1. 自由分析身体状态：
   ```text
   $garmin-health-chat 我今天起床很累，结合最近数据分析可能原因
   ```
2. 每周复盘并生成未来七日计划：
   ```text
   $garmin-weekly-plan 复盘之前七天，并制定之后七天的训练计划
   ```
3. 根据昨日训练和今日恢复调整当天计划：
   ```text
   $garmin-daily-adjust 看看我昨天练得怎么样，调整今天的安排
   ```
4. 根据聊天中的新要求修改现有计划：
   ```text
   $garmin-plan-edit 周六不能去健身房，把当天改为居家训练
   ```

技能允许自然语言触发，显式写 `$skill-name` 保证调用

## 自动发布训练页面

`.github/workflows/publish-sport.yml` 在每周一 8:30 生成训练页面，并只更新网站仓库中的 `static/sport/index.html`。原有的 Hugo 部署 Action 会在收到该提交后正常构建，页面地址为：

<https://gessiegulugulu.github.io/sport/>

首次使用: 
1. 在本仓库的 `Settings -> Secrets and variables -> Actions` 中添加名为 `WEBSITE_REPO_TOKEN` 的 secret。其值应为一个 fine-grained personal access token，配置如下：

   - Repository access：只选择 `gessiegulugulu/gessiegulugulu.github.io`
   - Repository permissions：`Contents` 设为 `Read and write`

2. 配置后在 Actions 页面手动运行一次 `Publish sport page`

## todo
- [x] 配置skills
    - [x] 健康数据的分析和问答
    - [x] 七日复盘与七日计划
    - [x] 每日复盘与当天调整
    - [x] 根据需求修改计划
- [x] 配置memory：见 [memory.md](memory.md)
- [x] 待定是否做可视化或者邮件推送
