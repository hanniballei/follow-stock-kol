# AGENTS.md · 给后续协作开发的注意事项

最后更新：2026-05-30
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

- `config/kols.yaml` — 63 位 KOL，按字母序，handle 大小写如 X 实际显示
- `config/settings.yaml` — 全部可调参数（调度、抓取、媒体、AI、发布、保留、日志）
- `.env.example` — 环境变量模板，复制为 `.env` 填值；本机覆盖可放 `.env.local`
- `.gitignore` — 已正确忽略 `.env / .env.local / *.db / *.log / media/` 等

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
ANTHROPIC_FOURTH_API_KEY=   # 可选第四层 Claude 兼容后端 key
ANTHROPIC_FOURTH_BASE_URL=  # 可选第四层 Claude 兼容后端 base URL
ANTHROPIC_FOURTH_MODEL=     # 可选第四层模型名；默认同 settings.yaml.ai.model
# KOL_MONITOR_DB=           # 可选覆盖 SQLite 路径
# KOL_MONITOR_MEDIA_DIR=    # 可选覆盖媒体目录
KOL_MONITOR_ALLOW_PUSH=false # 可选；默认不执行远端 git push
```

### 1.2 凭据安全

- `.env` 和 `.env.local` 必须在 `.gitignore` 里。如果不小心 commit 了，**立即** rotate token。
- `kol_monitor.log` 也要在 .gitignore，因为 rich 日志可能在 stack trace 里 echo 请求 header。
- 任何对外发的报告都不能包含 token；anthropic SDK 出错时它会在 traceback 里打印 base_url，base_url 里如果带了鉴权也敏感。

---

## 2. 6551.io API 关键事项

### 2.1 速率与计费

- 文档没有公开的速率限制数字，**实测前先小心**：61 个 KOL 一轮抓取期间 KOL 之间 sleep 2-5 秒，整个 batch 约 5-10 分钟。
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

### 3.1 tweet_id 比较用数值键，跨 ID 域用时间兜底

X 的 tweet_id 是 64-bit snowflake，单调递增。比较时**一定要转成数值排序键**。SQLite 列是 TEXT 没关系（因为长度可能超 int8），但比较时务必：

```python
last_id_int = tweet_id_sort_value(last_id_str) if last_id_str else 0
new_tweets = [t for t in batch if tweet_id_sort_value(t["tweet_id"]) > last_id_int]
```

注意：`realDonaldTrump` 经 6551 返回的 ID 可能是 `truth_1780116388200996844` 这种带前缀形式。比较时同一 ID family 内取数字后缀做排序键，但数据库里的 `tweet_id` 和 `last_seen_tweet_id` 要保留原始完整字符串。

还要注意：6551 偶尔会把 `realDonaldTrump` 的普通 X 数字 ID（例如 `2057968277062582378`）和 `truth_数字` 混在一起。两者数字后缀不是同一个单调序列，不能直接比较大小。fetcher 已改为：同一 family 用数字后缀比较，跨 family 时用锚点推文和当前推文的 `created_at` 比较；`created_at` 要同时支持 ISO 和 Twitter 原生格式（如 `Mon Jun 8 18:34:10 +0800 2026`）。

### 3.2 last_seen_tweet_id 更新原则

**只在本轮真有新推时更新**。如果某次拉取一条新都没有（或全部重复），保持原值不动。错误的实现会把 last_id 一路往前推到"最新无新推时的最大值"，下次拉漏掉的概率反而升高。

### 3.3 incomplete 标记的语义

`incomplete = True` 含义是"上次拉取**没在 MAX_ROUNDS 内找到与锚点的重叠**"，可能漏推。补救任务（每次主任务跑完后追加）要用 `/open/twitter_search` `fromUser=handle, sinceDate=last_fetched_at-1d` 强制扫一遍，扫完清标记。**别用 user_tweets 重试，因为没 cursor 翻不到更深**。

### 3.4 首次接入 vs 增量

```python
if last_id is None:           # 首次
    pull(20)                  # 不翻页，按用户要求只拉当天
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

### 7.1 远端 push 双开关

`publisher.py` 只有在 `config/settings.yaml` 的 `publish.git_push=true` 且环境变量 `KOL_MONITOR_ALLOW_PUSH=true` 时才会执行 `git push origin main`。公开 clone 默认没有这个环境变量，即使运行 `kol-monitor run-once` 也不会自动推送到原仓库。

当前机器为了保持每日 GitHub 首页更新，在被 `.gitignore` 忽略的 `.env.local` 里设置了 `KOL_MONITOR_ALLOW_PUSH=true`。后续换机器部署时也用这个方式开启；用户 fork 后想发布到自己的仓库，必须先把 `origin` 指向自己的 fork，再开启该变量。

### 7.2 push 失败兜底

`publisher.py` 里 push 失败重试 3 次（指数退避）。仍失败：
1. 本地 commit 已经成功（不要 reset）
2. 日志记 ERROR
3. 下次跑批前先 `git status` 检查未推送 commit，先 push 旧的再生成新的

### 7.3 不要 force push

任何情况下都不 `git push -f`。哪怕历史顺序不对，宁可补一个 fix commit。

### 7.4 媒体不进 git

`.gitignore` 里 `media/` 必须在。哪怕用户问"为什么 git status 没看到 media"，也别提示加进去。仓库膨胀是不可逆的。

---

## 8. 调度

### 8.1 时区

固定 `Asia/Shanghai`，cron `0 21 * * *`。不要因为"看起来美股开盘前应该跟 ET"就改成动态时区，**用户明确否决了 DST 调整**。

### 8.2 misfire 处理

机器宕机错过 21:00，一小时内（22:00 前）重新启动会自动补跑（`misfire_grace_time=3600`）。超过一小时不补跑，第二天正常跑。

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
ExecStart=/root/trading/us-stock/kol-monitor/.venv/bin/kol-monitor daemon
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

当前机器已安装并启用 `kol-monitor.service`。改 `.env` / `.env.local` / `config/*.yaml` / 代码后，使用 `systemctl restart kol-monitor.service` 让新配置或新代码生效。

---

## 9. 调试 / 运维命令

```bash
# 立即跑一次完整流程（不动调度）
kol-monitor run-once

# 真实跑完整流程但不 push GitHub；会在本地生成 README.md 和 digests/
kol-monitor run-once --no-publish

# 只抓不总结不发布
kol-monitor fetch-only

# 重新生成某天 digest
kol-monitor regen-digest --date 2026-05-29

# 只生成某天质量草稿和扫描报告，不写 DB / README / digests / git
kol-monitor quality-draft --date 2026-06-16

# 回填 incomplete KOL
kol-monitor backfill

# 校验所有 KOL handle
kol-monitor validate-handles

# systemd 持久化运行控制
systemctl status kol-monitor.service --no-pager
systemctl restart kol-monitor.service
systemctl stop kol-monitor.service
systemctl start kol-monitor.service
journalctl -u kol-monitor.service -f

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
- 2026-05-30：`SV_Nomad` 是真实 X 用户，但 6551 的 `twitter_user_tweets` 可能返回 400 `no tweet`；`twitter_search fromUser=SV_Nomad` 可正常返回内容。已保留该账号，并在 fetcher 中对 `user_tweets` 400 增加 search 兜底。
- 2026-05-30：日报展示里所有具体股票代码统一用 `$代码`，例如 `$NVDA`。Layer 2 JSON 的 `tickers` 字段可继续存 `NVDA`，发布渲染时会补 `$`。
- 2026-05-30：仓库已经落地 systemd 持久化运行，服务名 `kol-monitor.service`，`ExecStart` 指向 `.venv/bin/kol-monitor daemon`。查看/重启/停止都用 `systemctl`，不要再依赖 `nohup` 作为主方案。
- 2026-06-02：第三层 `anthropic/claude-sonnet-4.6` 后端拒绝 `temperature=0.3`，报错要求 thinking/adaptive 模式下 temperature 只能为 1。已改为主/备继续用 `settings.ai.temperature`，第三层固定 `temperature=1`。
- 2026-06-02：Layer 1 总摘要可能因主/备 504、第三层 429 等外部 LLM 问题全失败。已增加本地兜底摘要：Layer 1 全失败时仍发布日报；单个 KOL Layer 2 全失败时从原始推文生成最小明细。
- 2026-06-04：LLM 备用链路已扩展为四层，第四层使用 `ANTHROPIC_FOURTH_*` 环境变量，当前模型名为 `claude-sonnet-4-6`，base URL 填服务根地址即可。
- 2026-06-07：06-05 日报曾出现一条非 KOL 来源的内部工作原则污染（`investigate_before_answering`）。已清理历史 digest 和本地 DB，并在 Layer 1 发布前增加清理：移除明显内部工件或无 URL 的伪来源 bullet。
- 2026-06-08：`realDonaldTrump` 的 6551 数据混用了普通 X 数字 ID 和 `truth_数字` ID。旧逻辑直接比较数字后缀，导致 5/22 的普通 X ID 比 6/8 的 `truth_` 后缀更大，后续 Trump 新帖被误判为旧帖。已增加 ID family 判断：同 family 才比数字，跨 family 用已入库锚点推文的 `created_at` 兜底；同时支持 Twitter 原生时间格式解析。已手动补抓 6/5-6/8 Trump 新帖并重新生成 2026-06-08 digest。
- 2026-06-09：Layer 1 综合摘要曾在“宏观判断”中途截断，但第四层后端返回 200，旧代码直接接受，导致 `产业/个股焦点`、`交易信号`、`投资理念` 缺失仍发布。已增加 Layer 1 完整性校验：必须包含七个固定章节、各节有内容、不能以 `max_tokens` 停止或半句话结尾；校验失败会继续尝试下一层，全部失败才用本地兜底模板。
- 2026-06-10：第三层 `llm.onerouter.pro` 大请求曾先 429，再返回 Bedrock `temperature` / `thinking` 校验错误；固定 `temperature=1` + `thinking=disabled` 仍可能触发。已增加第三层专属兼容重试：遇到该错误时同一后端再试一次，不传 `temperature` 和 `thinking`，让 provider 走默认普通模式。不要改成 adaptive thinking 兜底，实测低 `max_tokens` 时可能先输出 thinking block，正文为空；代码已改为从所有 text blocks 提取正文，避免 thinking block 排在前面时读不到文本。
- 2026-06-10：用户要求调换第三/第四层顺序。当前实际调用顺序是：主凭据 → 第二层备用 → `ANTHROPIC_FOURTH_*`（Packy，第三顺位）→ `ANTHROPIC_THIRD_*`（Infron，第四顺位）。注意环境变量名保留历史命名，不等同于当前调用顺位。
- 2026-06-16：最近日报质量问题主要集中在 Layer 1/Layer 2 的可发布性：6/13 出现内部方法论污染（如“失败两次应诊断根因而非增量修补”），6/16 出现韩文残留和“OpenAI 计划发布 claude-sonnet-4-6”这类模型归属冲突。已增强提示词、Layer 2 结构化字段、确定性清理和质量扫描；新增 `kol-monitor quality-draft --date YYYY-MM-DD`，只在 `/tmp/kol-monitor-quality-drafts/<date>/` 生成 `draft.md`、`cleaned_existing.md`、`repaired_fallback.md`、`layer2_normalized.json`、`quality_report.json`，不写 DB/README/digests，也不 git publish。修旧日报前先跑这个命令看 `quality_report.json`，确认候选稿通过后再决定是否覆写历史文件。
- 2026-06-17：评估上周日报发现**质量门控只扫 DB（summary_md / layer2_json），但读者看到的是磁盘 `.md`，两者已脱节**，导致已被检测器识别的缺陷照样进了发布文件。根因与修复：
  - **渲染前未清洗**：`publisher.write_outputs` 之前直接把原始 `summary_md` 和原始 `layer2_json` 喂给渲染器，Layer-1 的清洗（`_prepare_layer1_markdown`）和 Layer-2 的归一化（`_normalize_layer2_result`，含韩文/残留/模型冲突过滤）都没作用到最终 `.md`。这就是 6/16 模型归属错误、6/14-6/16 整段 @blazingbees 韩文进入发布文件的原因。已改为在 `write_outputs` 里先清洗 Layer-1、先归一化 Layer-2，再交给三个渲染器（md / readme / html）。
  - **tweet_url JSON 泄漏（6/17，最严重）**：LLM 偶尔输出缺少右引号的 `tweet_url`，relaxed JSON 解析时 `(.*?)` 贪婪吞掉后续 `","claim_type":...` 字段，导致 31 个 `[原推]` 链接损坏 + 31 处裸 JSON 进正文。已新增 `summarizer.sanitize_tweet_url`：只抽取规范的 `…/status/<数字 或 truth_数字>` URL，丢弃尾部污染；接入 `_normalize_layer2_result`、`_source_link`、`_first_bullet_source` 以及 `publisher` 三个渲染点。无法抽出合法 URL 的 bullet 会被丢弃。
  - **发布后扫描**：`write_outputs` 写盘后会对**渲染后的 `.md`** 跑 `scan_summary_quality` 并把 error/warning 记日志（不 raise，遵守 publish-must-not-fail）。
  - **扫描器新增检测**：`json_residue`、`broken_source_link`（catch 上面这类泄漏）、`spacex_ticker_conflation`（warning，标记把 SpaceX 写成 `$SPCE`(维珍银河)/`$SPACEX`，但放过 charliebilello 那种“误将 $SPCE 当作 $SPCX”的合法辨析行）。
  - **artifact marker 收窄**：从 `INTERNAL_ARTIFACT_MARKERS` 移除 `Codex` 和 `工作流`——它们是 KOL 常用公共词（OpenAI Codex / “工作流”=workflow），bare 子串匹配会误删真实内容（如 6/16“与 Claude Code 和 Codex 竞争”那条），也会让渲染后扫描误报。保留 `失败两次/诊断根因/增量修补/工作原则` 等真正的内部短语。
  - **已重生 6/11–6/17 的 `.md`/`.html`**（纯从 DB 数据走修复后的 `write_outputs` 重渲染，**没有**重新调用 LLM，没有 push），7 天 error 全部归零。
  - **已知遗留（非阻断，需重跑 LLM 才能修）**：Layer-1 `summary_md` 内部的内容级错误仍可能存在，例如 6/16“拉赫曼防务”实为 Rheinmetall(莱茵金属)、6/16 把 $SNDK 的“月线 RSI 99”安到 $MU。这类张冠李戴/误译靠确定性清洗修不了（需要交叉核对原推文本），只能靠提示词约束或 `regen-digest`（会重新 summarize）解决。
- 2026-06-17（内容质量层，配合上一条）：为从源头降低内容级错误，做了两件事：
  - **提示词强约束归因**：Layer-2 和 Layer-1 prompt 都加了“归因纪律”——某条要点里的每个数字/指标/事件只能挂到它真正对应的那个 ticker 上，禁止把 A 股票的数据安到 B 股票（针对 $MU/$SNDK 这类张冠李戴）；`tickers` 只填 point 里确实出现且推文确有提及的代码；公司名用中文常用译名（Rheinmetall→莱茵金属、Virgin Galactic→维珍银河 $SPCE）不要音译生造；SpaceX 统一 $SPCX，不与 $SPCE/$SPACEX 混淆。注意这是**软约束**（靠模型遵守），不是确定性保证；真正确定性的 ticker 交叉校验（roll-up ticker 必须出现在其引用推文的 ticker 集合内）尚未做，是下一个杠杆点。
  - **外文 bullet 改“翻译”而非“丢弃”**：新增 `summarizer._translate_residual_layer2`，在 `_normalize_layer2_result` **之前**对仍带韩文/日文残留的 `core_view`/`point` 做一次**逐条批量翻译**（一次 LLM 调用翻多条），翻成功就回填保留信息，翻失败或仍残留才退回交给 normalize 丢弃（保底行为不变，无回归）。这解决了之前整段 @blazingbees 韩文被静默删除、信息丢失的问题。原有的整段中文重试（`_layer2_needs_chinese_retry`）保留为第一道便宜尝试，新函数是精准兜底。注意 `NON_CHINESE_RETRY_CHAR_LIMIT=8` 阈值未改：≤8 个韩/日字符的短残留既不会触发翻译也不会被丢弃，属已知阈值边界（如 06/15 “买入熔断（사이드카）” 这种带中文译名+原文括注的 gloss，3 个韩字，正常保留不算残留）。
- 2026-06-17（全 6 月回灌）：用上述修复对 6/01–6/17 全部 17 天做了分层修复，结果全部 0 errors：
  - **Tier A（纯渲染，免费）**：6/01–6/13 + 6/17 直接走修复后的 `write_outputs` 重渲染（**不调 LLM**）。这批早期日报的 `empty_required_section` 报错其实是**旧编号标题格式**（`## 三、重要新闻`）+ 旧渲染产物的假阳性，新渲染清洗 Layer-1、归一化 Layer-2 后即归零，内容不丢（如 6/04 的污染 bullet 被去掉但 @nbblock “半导体回调健康” 观点经明细段保留）。注意：纯渲染不改写 DB 里的旧编号标题，所以这些天的 `##` 标题仍是 `一、二、三…` 编号体，与 6/14 之后的无编号体不一致，但不算错误。
  - **Tier B（重跑 LLM）**：仅 6/14、6/15——它们的 `layer2_json` 仍有韩文残留（4 / 8 处），只有重新 summarize 才能经新翻译兜底把 @blazingbees 整段韩文转成中文保留（而非丢弃）。重跑后 0 韩文（6/15 仅剩 1 处带中文译名的括注 gloss，正常）。
  - **marker 再收窄**：6/14 重跑后命中一条假阳性——@ArtofSpecuycky 转述 All-In 播客讲 Anthropic 的“提示词保留 30 天”政策，正文里“用户提示词/重写提示词”是**真实题材**，却被 `提示词` marker 误判。已把 `提示词`/`读代码`/`系统行为` 从 `INTERNAL_ARTIFACT_MARKERS` 移除（理由同 `Codex`：美股科技 KOL 经常正当讨论 AI 工具），只保留 `失败两次/诊断根因/增量修补/工作原则/系统原则/放弃需求/investigate_before_answering/AGENTS.md` 这些无歧义的内部短语。
  - **残留 warning（非阻断）**：6/03/06/13/06/15 各有 1 条 `spacex_ticker_conflation`——是正文文字里 `$SPACE`/明细 ticker 标 `$SPCE` 的软提示，确定性不自动改写 $SPCE（怕误伤真维珍银河），保留为人工复核线索。
- 2026-06-18（输出形态与排程调整）：
  - **调度提前到 20:30**：`config/settings.yaml` 的 `schedule.hour/minute` 改为 `20:30`（北京时间，较原 21:00 提前半小时）。README 文案改为从 `settings.schedule` 动态读取，不再硬编码时间。改后需 `systemctl restart kol-monitor.service` 生效。
  - **停止生成 HTML**：`write_outputs` 不再渲染/写 `digests/**/*.html`，只产出 `README.md` + 当天 `DD.md`；返回值从三元组改为 `list[Path]`。已 `git rm` 全部历史 `.html`。`render_daily_html()` 函数保留但不再被调用（如需恢复 HTML 可重新接上），其单元测试仍在。
  - **新增盘前长推文**：每天在 digest 之后生成一篇可直接复制发到 X 的中文《美股盘前快报》，存到 `premarket/YYYY/MM/DD.md`（纯推文正文、无 front matter，便于复制）。实现：`summarizer.generate_premarket_tweet(date)` 读取已入库的 cleaned Layer-1 摘要 → LLM 成稿；`publisher.write_premarket(date, text)` 落盘；CLI `_run_once`/`_regen_digest` 里作为**尽力而为**步骤（失败只 warning，不阻断 digest 发布），并把该文件加入 git_publish 列表一起提交。新增 `kol-monitor premarket --date YYYY-MM-DD` 可单独重生（不发布）。盘前稿默认会随 digest 一起 commit/push 到 GitHub（与日报同源信息）；如需只留本地，把 `premarket/` 加入 `.gitignore` 或不加入 publish 列表即可。**目前不自动发到任何平台**（用户明确"先只存文件"）。
  - **#2 联网/本地事实核查：已评估后暂不做**。本地 `/root/trading/data/us-stock/reference/ticker_details.parquet` 只有美股（~1.28 万），但 KOL 常发 A 股（数字码 $002384）、港股、韩股（$005930）、加密（$BTC/$ETH）等非美股代码；任何"代码不在美股库即报错"的确定性校验都会对这些合法非美股代码大量误报。故 ticker 事实性继续靠提示词归因约束 + `spacex_ticker_conflation` 软检查。若将来要做，需先有覆盖多市场的代码库。（pyarrow 已装进 venv 但当前未使用、未写入 requirements。）

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

不要在初版就尝试以上任何一项 —— 先把 61 个 KOL 每天总结这件事跑稳一个月。
