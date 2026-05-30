# AGENTS.md · 给后续协作开发的注意事项

最后更新：2026-05-29
项目：美股 KOL 推特监控
配套文档：
- 设计：[docs/DESIGN.md](docs/DESIGN.md)
- 实施：[docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md)
- 测试：[docs/TESTING.md](docs/TESTING.md)
- 运维：[docs/OPERATIONS.md](docs/OPERATIONS.md)

> 这份文档面向接手或扩展本项目的 AI 助手 / 工程师，记录"光看代码看不出来"的决策和坑。请在重大改动前先读完，并在踩坑后回来更新"已知问题与教训"区。

---

## 0. 已经预先创建的文件

不要重新创建以下文件，直接复用 / 增量编辑：

- `config/kols.yaml` — 53 位 KOL，按字母序，handle 大小写如 X 实际显示
- `config/settings.yaml` — 全部可调参数（调度、抓取、媒体、AI、发布、保留、日志）
- `.env.example` — 环境变量模板，复制为 `.env` 填值
- `.gitignore` — 已正确忽略 `.env / *.db / *.log / media/` 等

---

## 1. 凭据和配置

### 1.1 必备环境变量（`.env`）

模板见 [`.env.example`](.env.example)。核心变量：

```bash
OPENTWITTER_TOKEN=          # 必填，6551.io 注册申请
OPENTWITTER_BASE_URL=https://ai.6551.io   # 一般不改
ANTHROPIC_API_KEY=          # 必填
ANTHROPIC_BASE_URL=         # 走代理时填，走官方留空
# ANTHROPIC_MODEL=          # 可选覆盖；默认从 settings.yaml.ai.model 读
ANTHROPIC_FALLBACK_API_KEY= # 可选备用 Claude key
ANTHROPIC_FALLBACK_BASE_URL= # 可选备用 Claude base URL；为空则复用 ANTHROPIC_BASE_URL
ANTHROPIC_THIRD_API_KEY=    # 可选第三层 Claude 兼容后端 key
ANTHROPIC_THIRD_BASE_URL=   # 可选第三层 Claude 兼容后端 base URL
ANTHROPIC_THIRD_MODEL=      # 可选第三层模型名；默认同 settings.yaml.ai.model
# KOL_MONITOR_DB=           # 可选覆盖 SQLite 路径
# KOL_MONITOR_MEDIA_DIR=    # 可选覆盖媒体目录
```

### 1.2 凭据安全

- `.env` 必须在 `.gitignore` 里。如果不小心 commit 了，**立即** rotate token。
- `kol_monitor.log` 也要在 .gitignore，因为 rich 日志可能在 stack trace 里 echo 请求 header。
- 任何对外发的报告都不能包含 token；anthropic SDK 出错时它会在 traceback 里打印 base_url，base_url 里如果带了鉴权也敏感。

---

## 2. 6551.io API 关键事项

### 2.1 速率与计费

- 文档没有公开的速率限制数字，**实测前先小心**：53 个 KOL 一轮抓取期间 KOL 之间 sleep 2-5 秒，整个 batch 约 5-10 分钟。
- 计费按调用量，跑批前看一眼 [6551.io 控制台](https://6551.io/mcp) 余额。
- token 用尽时 API 一般返回 4xx，**千万不要重试 4xx**（tenacity 装饰器只对 ConnectError / ReadTimeout 重试，不要扩到 HTTPStatusError）。

### 2.2 没有 cursor，靠 maxResults 翻页

`/open/twitter_user_tweets` **不支持 cursor**，每次都从最新拿。要"翻深一点"靠扩大 `maxResults`（上限 100）。这就是 fetcher.py 里 `page_size = min(page_size*2, 100)` 的原因。如果某天某 KOL 发了超过 100 条还要全部拿到，必须用 `/open/twitter_search` 兜底（`fromUser` + `sinceDate`）。

### 2.3 媒体字段不全

6551 返回的 `media[]` 里只承诺 3 个字段：`type` / `url` / `thumbUrl`。视频的码率、时长、多版本 variants 都**不暴露**。我们的设计是视频只存 URL（不分析），所以够用；如果未来要喂 AI 视频，必须换底层（twscrape 或自抓）。

### 2.4 字段名注意

6551 用的是驼峰：`createdAt`, `userScreenName`, `retweetCount`，不是 X 原生 API 的 `created_at`。client.py 里要做一次字段名转换到内部 snake_case，避免散在各处。

---

## 3. 防漏拉边界条件（务必读）

### 3.1 tweet_id 比较用数值键不是字符串

X 的 tweet_id 是 64-bit snowflake，单调递增。比较时**一定要转成数值排序键**。SQLite 列是 TEXT 没关系（因为长度可能超 int8），但比较时务必：

```python
last_id_int = tweet_id_sort_value(last_id_str) if last_id_str else 0
new_tweets = [t for t in batch if tweet_id_sort_value(t["tweet_id"]) > last_id_int]
```

注意：`realDonaldTrump` 经 6551 返回的 ID 可能是 `truth_1780116388200996844` 这种带前缀形式。比较时取数字后缀做排序键，但数据库里的 `tweet_id` 和 `last_seen_tweet_id` 要保留原始完整字符串。

### 3.2 last_seen_tweet_id 更新原则

**只在本轮真有新推时更新**。如果某次拉取一条新都没有（或全部重复），保持原值不动。错误的实现会把 last_id 一路往前推到"最新无新推时的最大值"，下次拉漏掉的概率反而升高。

### 3.3 incomplete 标记的语义

`incomplete = True` 含义是"上次拉取**没在 MAX_ROUNDS 内找到与锚点的重叠**"，可能漏推。补救任务（每次主任务跑完后追加）要用 `/open/twitter_search` `fromUser=handle, sinceDate=last_fetched_at-1d` 强制扫一遍，扫完清标记。**别用 user_tweets 重试，因为没 cursor 翻不到更深**。

### 3.4 首次接入 vs 增量

```python
if last_id is None:           # 首次
    pull(50)                  # 不翻页，按用户要求只拉当天
else:                         # 增量
    while round <= 5: ...     # 翻页直到重叠
```

注意"首次"和"`last_id == 0`"是两回事，**不要把首次当成 last_id=0 用**（会无限翻页直到 MAX_ROUNDS）。

### 3.5 KOL handle 改名 / 注销

- 改名：6551 返回 `userIdStr` 不变，依赖 `screen_name` 做 join 会丢数据。**用 `twitter_user_id` 做长期标识更稳**，但 schema 已经用 `screen_name UNIQUE`，将来若要切换需迁移。当前先按 screen_name 处理，加监控（`fetch_runs.error_log` 里出现 user_info 失败时报警）。
- 注销 / 拉黑 / 私密：`twitter_user_info` 返回空或 4xx → `mark_kol_inactive(handle, reason=...)`，跑批不影响其他人。

---

## 4. Claude API 注入

### 4.1 base_url 优先级

```python
from anthropic import Anthropic

# 优先用 .env 里的 base_url；为空则用官方
client = Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    base_url=os.environ.get("ANTHROPIC_BASE_URL") or None,
)
```

不要写死 base_url。代理地址的协议头要带（`https://...`），SDK 不会自动补。

### 4.2 模型 ID

`claude-sonnet-4-6` 是 2026 当前的有效 ID。如果代理服务用别的 ID（比如 `claude-3-sonnet-..`），需要在 `settings.yaml.ai.model` 字段覆盖。

### 4.3 多模态消息构造

图片走 base64 inline：
```python
{
  "role": "user",
  "content": [
    {"type": "image", "source": {
      "type": "base64",
      "media_type": "image/jpeg",
      "data": base64_str
    }},
    {"type": "text", "text": "..."},
  ]
}
```

单条 message 总图数没有硬上限，但建议每个 KOL ≤ 8 张避免 token 爆炸。**JPEG 质量保留原图**，PNG 转 JPEG 时要处理透明通道（贴白底），不然 PIL 报错。

### 4.4 JSON 输出 fallback

Layer 2 要求 JSON 输出，模型偶尔会包一层 markdown ```json``` 代码块。Parse 顺序：

```python
def parse_layer2(text):
    # 1. 直接 json.loads
    try: return json.loads(text)
    except: pass
    # 2. 剥 markdown code fence
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except: pass
    # 3. 找第一个 { 到最后一个 }
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e > s:
        try: return json.loads(text[s:e+1])
        except: pass
    return None  # 这条 KOL 标 summary_failed，不影响其他
```

---

## 5. 媒体下载

### 5.1 文件名格式

`media/YYYY-MM-DD/<handle>/<tweet_id>_<idx>.<ext>`，其中：
- 日期用**北京时间**（推文 `created_at` 是 UTC，要 `.astimezone(Asia/Shanghai).date()`）
- idx 是同一推文里的第几张图（0 起）
- ext 从 URL 末尾或 Content-Type 推断（jpg / png / webp / mp4 / gif）

### 5.2 去重

媒体表 `UNIQUE(tweet_id, orig_url)`。下载前先 SELECT；同一 URL 已 `download_status='done'` 跳过。但要**校验本地文件还在**，不在则重下。

### 5.3 失败不影响主流程

- 下载失败：标 `download_status='failed'`，不抛异常
- AI 总结时：跳过 failed 的图，**告诉 AI"原推有图但下载失败"**，避免 AI 凭空想象
- 下载用 `asyncio.Semaphore(8)` 限并发，否则 X CDN 偶尔 429

---

## 6. Markdown 渲染

### 6.1 README 是覆写不是追加

每天生成新 README 完全覆盖旧的。**不要 append 模式**，否则会越来越长。历史 digest 在 `digests/` 目录里独立存在。

### 6.2 折叠区写法

GitHub 主页 README 支持 `<details>`：
```markdown
<details>
<summary>📌 各 KOL 详细总结（点击展开）</summary>

#### @qinbafrank · 12 条
...

</details>
```

注意 `<details>` 内部的 markdown **必须前后空一行**（最常见的渲染坑）。

### 6.3 推文链接

```python
url = f"https://x.com/{handle}/status/{tweet_id}"
```

不要用 twitter.com（已 redirect），不要用 nitter（不稳定）。

### 6.4 emoji 在 commit message

commit message 里加 emoji 不影响 GitHub，但终端日志可能乱码。建议：

- README / digest 文件内：emoji ok
- commit message：纯 ASCII 安全，例如 `digest: 2026-05-29 (28 KOLs, 184 tweets)`

---

## 7. Git 操作

### 7.1 push 失败兜底

`publisher.py` 里 push 失败重试 3 次（指数退避）。仍失败：
1. 本地 commit 已经成功（不要 reset）
2. 日志记 ERROR
3. 下次跑批前先 `git status` 检查未推送 commit，先 push 旧的再生成新的

### 7.2 不要 force push

任何情况下都不 `git push -f`。哪怕历史顺序不对，宁可补一个 fix commit。

### 7.3 媒体不进 git

`.gitignore` 里 `media/` 必须在。哪怕用户问"为什么 git status 没看到 media"，也别提示加进去。仓库膨胀是不可逆的。

---

## 8. 调度

### 8.1 时区

固定 `Asia/Shanghai`，cron `30 20 * * *`。不要因为"看起来美股开盘前 1h 应该跟 ET"就改成动态时区，**用户明确否决了 DST 调整**。

### 8.2 misfire 处理

机器宕机错过 20:30，一小时内（21:30 前）重新启动会自动补跑（`misfire_grace_time=3600`）。超过一小时不补跑，第二天正常跑。

### 8.3 daemon 部署

推荐 systemd unit（避免 nohup 随终端退出问题）。模板：

```ini
[Unit]
Description=KOL Monitor Daemon
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/trading/us-stock/kol-monitor
EnvironmentFile=/root/trading/us-stock/kol-monitor/.env
ExecStart=/path/to/venv/bin/python -m kol_monitor daemon
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

---

## 9. 调试 / 运维命令

```bash
# 立即跑一次完整流程（不动调度）
python -m kol_monitor run-once

# 只抓不总结不发布
python -m kol_monitor fetch-only

# 重新生成某天 digest（不改 DB 数据，只改 markdown 和 push）
python -m kol_monitor regen-digest --date 2026-05-29

# 回填某 KOL 最近 7 天
python -m kol_monitor backfill --kol qinbafrank --days 7

# 校验所有 KOL handle
python -m kol_monitor validate-handles

# 看日志（rich 彩色输出 + 文件副本）
tail -f kol_monitor.log

# 查 DB
sqlite3 kol_monitor.db "SELECT screen_name, last_seen_tweet_id, incomplete FROM kols ORDER BY last_fetched_at DESC LIMIT 10"
sqlite3 kol_monitor.db "SELECT date, kol_count, tweet_count, status FROM digests ORDER BY date DESC LIMIT 7"
```

---

## 10. 已知问题与教训

> 此区域用于踩坑后回写。每条注明日期 + 问题 + 解决。

- 2026-05-30：当前工作目录的 `.git` 是只读 tmpfs 挂载点，不能作为普通 git repo 初始化。已改用 `.git-data/` 作为备用 `GIT_DIR`，`publisher.py` 检测到 `.git-data/` 时会设置 `GIT_DIR` / `GIT_WORK_TREE` 后再执行 git 命令。`.git-data/` 已加入 `.gitignore`。
- 2026-05-30：`realDonaldTrump` 的 6551 返回 ID 可能是 `truth_数字`，不能直接 `int(tweet_id)`。已在 fetcher 里改为用数字后缀比较，仍保存完整原始 ID，避免 Trump 账号首拉和增量都失败。

---

## 11. 不要做的事（容易翻车）

- ❌ 把媒体目录加进 git（仓库膨胀，不可逆）
- ❌ 给 4xx 加 retry（会快速烧光 6551 token）
- ❌ 改 cron 为动态时区（用户明确要求固定北京时间）
- ❌ 在 commit message / README 里 echo token 任何片段
- ❌ 同步调用 anthropic / 6551 API（项目是 async-first，混用会卡 event loop）
- ❌ 抓取后立刻总结而不持久化推文（任何阶段崩溃都得能从 DB 恢复）
- ❌ KOL 列表硬编码到代码里（必须走 `config/kols.yaml`）
- ❌ 把 raw_json 字段进 git（在 DB 里就够了，仓库不需要）

---

## 12. 扩展点（未来想加的功能）

按可能优先级：

1. **WSS 实时推送** — `wss://ai.6551.io/open/twitter_wss`，把当天发的关键推（含 $符号股票代码 / 大额异动关键词）即时落库 + 微信 / TG 推送
2. **多模型对比 digest** — 同一天同时用 Sonnet + Opus + GPT-5.5 生成 3 份 digest，对比质量
3. **个股聚合视图** — 按 `tickers` 把所有提到 NVDA 的推文聚到一处
4. **情绪时序** — 把每位 KOL 每日 sentiment 存进 `kol_sentiment_daily`，画图
5. **Telegram 机器人** — `/today` 推送当日 digest 到 channel

不要在初版就尝试以上任何一项 —— 先把 53 个 KOL 每天总结这件事跑稳一个月。
