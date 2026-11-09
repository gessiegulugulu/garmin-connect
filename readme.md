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

`.github/workflows/publish-sport.yml` 每 3 天北京时间 8:30 同步 Garmin 并生成健康周报（以 2026-10-23 为起点，跨月保持三天间隔）；修改计划、页面脚本或数据后也会更新。流程只修改网站仓库中的 `content/sport.md`，再由原有 Hugo Action 构建，页面地址为：

<https://gessiegulugulu.github.io/sport/>

首次使用: 
1. 在本仓库的 `Settings -> Secrets and variables -> Actions` 中添加名为 `WEBSITE_REPO_TOKEN` 的 secret。其值应为一个 fine-grained personal access token，配置如下：

   - Repository access：只选择 `gessiegulugulu/gessiegulugulu.github.io`
   - Repository permissions：`Contents` 设为 `Read and write`

2. 添加 `GARMIN_TOKENS_JSON` secret：内容为本机已登录的 `~/.garminconnect/garmin_tokens.json`。不需要上传邮箱或密码。可在本机执行：

   ```bash
   gh secret set GARMIN_TOKENS_JSON --repo gessiegulugulu/garmin-connect < ~/.garminconnect/garmin_tokens.json
   ```

   使用 Garmin 中国区账号时，另设置 Actions variable `GARMIN_IS_CN=true`。

3. 配置后在 Actions 页面手动运行一次 `Publish sport page`。

同步成功后，刷新的 Garmin 会话会以 AES-256 加密后保存在 Actions 缓存中，下一次运行优先恢复最新会话。缓存只上传 `session.gpg` 密文，不上传 token JSON；加密密钥来自 `GARMIN_TOKENS_JSON`，不需要新增 GitHub 写权限。数据抓取失败时也会保存已刷新的授权，避免下一次重复使用旧 refresh token。

`GARMIN_TOKENS_JSON` 是初始授权和缓存加密依据。重新设置它会切换到新的缓存，适用于授权失效或缓存被清理后的恢复。GitHub 会清理超过 7 天未访问的缓存，因此长时间停用后可能需要重新上传已验证的有效授权，再手动运行发布。不要将明文 token 放进仓库或构建产物。

### 页面与数据口径

- 页面采用浅色渐变与磨砂玻璃卡片，左侧展示从今天起的 7 天运动计划，右侧为一周健康指标，下方为运动记录和一周变化。电脑、平板和手机分别适配；点击计划或指标卡可展开明细。
- 最近一周按上海时间取昨天结束的 7 个完整自然日。例如 2026-10-23 更新时，健康数据为 10-16 至 10-22，计划为 10-23 至 10-29。
- 计划优先读取 `TRAINING_PLAN.md`，未覆盖的日期读取 `MONTHLY_ROUTINE.md`；都没有的日期显示“待安排”。页面不会重复过期计划或自行生成训练安排。
- 身体电量为每日最高值的周均值；呼吸为每日清醒呼吸均值的周均值（次/分），卡片下方另列睡眠呼吸均值；夜间 HRV、睡眠时长和压力取有记录日期的均值；活动展示累计步数。睡眠使用专用睡眠摘要，HRV 使用每晚均值，不再对 Garmin 的滚动七日均值重复平均。
- 每张指标卡标明有效记录天数。缺失数据保留为空，不计入均值；图表不连接缺失日期。缺失睡眠不解释为睡了 0 小时；计划不算作完成记录。
- `data/garmin-week.json` 只保存每日指标和运动摘要，不含授权、账号标识、运动名称中的私人地点或 GPS 轨迹。未配置 Garmin secret 时，只显示缓存中仍位于最近一周内的数据，并标明同步状态；已配置授权但同步失败时停止发布，保留线上版本。
- 网页构建本身只依赖 Python 标准库；联网同步使用 `scripts/requirements-dashboard.txt` 中固定版本的 Garmin 客户端。

### 本地更新与预览

```bash
# 在已安装 Garmin 客户端的 Python 环境中，同步最近一周
python3 scripts/sync_garmin_data.py

# 生成供 Hugo 发布的 Markdown
python3 scripts/build_sport_page.py --output dist/sport.md

# 生成可直接用浏览器打开的独立页面
python3 scripts/build_sport_page.py --standalone --output dist/sport.html

# 检查日期范围、数据缺失处理和计划覆盖规则
python3 -m unittest discover -s tests -v
```

同步和构建均支持 `--date YYYY-MM-DD`，便于复现某一天的滚动窗口；构建可用 `--data` 指定另一份周数据。

## todo
- [x] 配置skills
    - [x] 健康数据的分析和问答
    - [x] 七日复盘与七日计划
    - [x] 每日复盘与当天调整
    - [x] 根据需求修改计划
- [x] 配置memory：见 [memory.md](memory.md)
- [x] 待定是否做可视化或者邮件推送
