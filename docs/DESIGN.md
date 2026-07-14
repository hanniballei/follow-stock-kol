# 美股 KOL 推特监控系统 · 设计文档

最后更新：2026-06-30

## 1. 项目目标

每天**北京时间 20:30**（固定不随夏令时调整），自动抓取 64 位美股相关 Twitter / X KOL 的最新推文（含图片），其中包含 `realDonaldTrump`，用 Claude Sonnet 4.6 兼容后端做 AI 总结，把当日总结推送到 GitHub 仓库主页（README.md），并按月归档历史 digest，方便公开访问。

## 2. 技术栈

| 层 | 选型 | 备注 |
|---|---|---|
| 抓取 | 6551.io REST API（`https://ai.6551.io`） | 直接 httpx 调，不走 MCP 协议 |
| 数据库 | SQLite（项目根 `kol_monitor.db`） | 单文件零维护 |
| AI 总结 | Claude Sonnet 4.6（用户提供 base URL + key） | 走 anthropic SDK |
| 调度 | apscheduler `BlockingScheduler`，timezone `Asia/Shanghai` | 固定 cron `30 20 * * *` |
| 发布 | git commit + push 到 GitHub 主仓库 | 仅 markdown，媒体不进 git |
| 日志 | rich + Python logging | 控制台彩色 + 文件落盘 |
| 语言 | Python 3.10+ | 项目机器已是 3.10.12 |

### 关键依赖
```
httpx>=0.27           # 6551 REST + 图片下载
anthropic>=0.40       # Claude SDK，支持 base_url 注入
apscheduler>=3.10
pyyaml>=6.0
python-dotenv>=1.0
pillow>=10.0          # 图片格式校验
tenacity>=8.2         # 重试装饰器
rich>=13.0            # 日志着色
```

## 3. 抓取方案选型理由

调研过 4 种方案，最终选 **6551.io REST 直连**：

| 方案 | 是否需要 X 账号 | 反爬维护 | 媒体字段 | 成本 | 评估 |
|---|---|---|---|---|---|
| 6551.io REST（选用） | ❌ 不需要 | ✅ 商业方代维 | 图片 ✅、视频 url+thumb | 付费 token | **稳定省心，业务首选** |
| opentwitter-mcp | ❌ 不需要 | ✅ 同上 | 同上 | 付费 token | MCP 协议层冗余，不如直调 REST |
| vladkens/twscrape | ✅ 需小号 | ⚠️ 自维护 | 视频多码率 + 时长 + 封面，最全 | 免费 | 风控风险大，国内还要住宅代理 |
| d60/twikit | ✅ 需小号 | ❌ 已 2025-04 停更 | 同 twscrape | 免费 | 大概率已坏 |

**6551 REST 调用范式**（源码逆向自 [6551Team/opentwitter-mcp](https://github.com/6551Team/opentwitter-mcp) 的 `api_client.py`）：

```python
POST https://ai.6551.io/open/twitter_user_tweets
Headers: Authorization: Bearer <TOKEN>, Content-Type: application/json
Body: {"username": "elonmusk", "maxResults": 50, "product": "Latest",
       "includeReplies": false, "includeRetweets": true}
Response: {"data": [<Tweet>...], "total": N}
```

我们用得上的 endpoint：

| Path | 用途 |
|---|---|
| `/open/twitter_user_info` | 校验 handle 拼写、获取 display_name 和 user_id |
| `/open/twitter_user_tweets` | 主拉取入口，product=Latest，maxResults≤100 |
| `/open/twitter_search` | 防漏拉兜底（`fromUser` + `sinceDate`） |
| `/open/twitter_tweet_by_id` | 单推详查（debug 用） |

WSS 实时事件（`wss://ai.6551.io/open/twitter_wss?token=...`）暂不接，留扩展位。

## 4. AI 模型选型

- **主选 Claude Sonnet 4.6**（用户指定）
- 价格：$3/M 输入、$15/M 输出（Anthropic 官方标准价，截至 2026-07-14；兼容后端以实际扣费为准）
- 多模态：模型支持图片输入，但当前为控制 token 成本默认关闭（`media.max_photos_per_kol_for_ai=0`）；需要时可设为正整数恢复
- 视频：不支持原生输入，本系统也只存 URL 不喂 AI

走 anthropic SDK，构造时支持注入 `base_url`：

```python
from anthropic import Anthropic
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"),
                   api_key=os.getenv("ANTHROPIC_API_KEY"))
```

## 5. 模块划分

```
src/kol_monitor/
├── client.py        # 6551 REST 客户端（async httpx）
├── db.py            # SQLite 连接池 + DAO
├── fetcher.py       # 抓取主流程：增量 + 防漏拉 + 回填
├── media.py         # 图片下载（去重、重试、按日期分目录）
├── summarizer.py    # Claude 调用：Layer 2 各 KOL + Layer 1 综合；保留遗留 Layer 3 helper
├── quality.py       # 日报草稿修复 + 质量扫描（不写发布文件）
├── publisher.py     # Markdown 渲染 + README 更新 + git ops
├── scheduler.py     # apscheduler 入口
├── cli.py           # kol-monitor [run-once|daemon|fetch-only|backfill|regen-digest|quality-draft|validate-handles|add-kol]
└── logging_setup.py # rich + file handler 双输出
```

## 6. 数据流

```
                 ┌─── config/kols.yaml ────┐
                 │                          │
[scheduler 20:30]┼─► fetcher ─► 6551 REST ──┴──► tweets[]
                 │                          ┌──► media[]
                 │      ▼                   │
                 │   db (SQLite)  ◄─────────┘
                 │      ▼
                 ├─► media.download_photos ──► media/YYYY-MM-DD/<handle>/
                 │      ▼
                 ├─► summarizer
                 │      ├─ Layer 2: 每个 KOL 一句话+bullets+情绪+claim_type
                 │      └─ Layer 1: 7 个章节综合（基于 Layer 2）
                 │      ▼
                 ├─► quality（手工草稿/回查用）
                 │      ├─ clean existing Layer 1
                 │      ├─ normalize Layer 2
                 │      └─ write /tmp/kol-monitor-quality-drafts/<date>/
                 │      ▼
                 ├─► publisher
                 │      ├─ render README.md（KOL 名单 + 当日总结 + 历史索引）
                 │      ├─ write digests/YYYY/MM/DD.md（不再生成 .html）
                 │      └─ git add/commit/push
                 ▼
              kol_monitor.log（rich）
```

日报日期代表截至该日调度时刻的滚动 24 小时窗口。当前调度为北京时间 20:30，因此 `2026-07-12` 日报覆盖 `(2026-07-11 20:30, 2026-07-12 20:30]`。推文汇总、按 KOL 汇总和媒体下载必须复用同一窗口；不能直接截取 `created_at` 的日期字符串，因为 6551 数据会混合 `+00:00` 与 `+08:00` 时区。

## 7. 数据库 Schema

详见 `docs/IMPLEMENTATION.md` 第 4 节，简述：

- **kols** — KOL 主表，含 `last_seen_tweet_id` 增量锚点和 `incomplete` 断档标记
- **tweets** — 推文表，主键 `tweet_id`（X snowflake，单调递增）；保留 `raw_json`
- **media** — 媒体表，photo/gif 落本地，video 只存 URL 和 thumb
- **digests** — 每日总结表，存 markdown 全文 + token 计数
- **fetch_runs** — 跑批审计日志

不存 KOL 分类，按用户要求"对推文内容做内容维度分组，不对 KOL 分组"。

## 8. 防漏拉算法（核心）

### 8.1 思路修正

用户原话："**如果数据库为空就检查最新推文是否和数据库最后记录有重复**"。逻辑反转修正为："**数据库非空时**比对最新一批与数据库锚点是否重叠"。

### 8.2 算法

```
对每个 active KOL（串行，间隔 sleep 2~5s）：
  last_id = SELECT last_seen_tweet_id FROM kols WHERE id = ?

  情况 A：last_id IS NULL（首次接入）
    pull 20 条 → INSERT OR IGNORE → 更新 last_seen_tweet_id

  情况 B：last_id 存在（增量）
    page_size = 20；overlap = False
    for round in 1..5：
      batch = pull(maxResults=page_size)
      if 任意 t.id == last_id 或 min(batch.id) < last_id：
        overlap = True
        keep = [t for t in batch if t.id > last_id]
        break
      else：
        keep_all_temporarily(batch)
        page_size = min(page_size*2, 100)

    if not overlap：
      kols.incomplete = True
      log.warning(f"gap suspected for @{handle}")

    INSERT OR IGNORE all kept tweets
    UPDATE last_seen_tweet_id = max(kept.id) if kept else last_id

主任务结束后追加补救：
  for kol where incomplete = True：
    res = /open/twitter_search {fromUser=handle,
                                 sinceDate=last_fetched_at-1d,
                                 maxResults=100}
    INSERT OR IGNORE
    清 incomplete 标记
```

### 8.3 边界条件

- 6551 REST 没有 `cursor` 参数，"翻页"靠扩大 maxResults，最大 100
- KOL 一天发超过 100 条（罕见，meme 账号偶发）— search 兜底
- KOL handle 错（拼写、改名、注销）— `twitter_user_info` 校验失败时 active=False，写入 `fetch_runs.error_log`
- 连接错误 / 读取超时 — tenacity 指数退避重试 3 次；HTTP 4xx/5xx 不对同一请求重试
- 真实账号的 400 `no tweet` —— 走 `/open/twitter_search fromUser=<handle>` 兜底一次，不把账号直接判坏

## 9. AI 总结策略（两层生成 + 遗留 Layer 3）

### 9.1 Layer 2 — 每 KOL 单独总结（折叠展示）

按 KOL 维度循环调用，每个 KOL 一次 Claude 请求：

**输入**：当日所有该 KOL 的推文（text + 互动数 + 配图 base64，单 KOL 最多 8 张图，按互动量截断）。

**输出**（要求 JSON）：
```json
{
  "core_view": "≤30 字一句话",
  "bullets": [
    {
      "point": "...",
      "tickers": ["NVDA"],
      "tweet_url": "https://x.com/.../status/...",
      "claim_type": "news | opinion | trade_signal | market_data | policy | earnings | personal | irrelevant",
      "confidence": "high | medium | low"
    }
  ],
  "sentiment": "bullish | bearish | neutral | unclear"
}
```

Layer 2 输出必须使用简体中文；非中文推文要翻译。每条 bullet 必须有原推链接，不能把传言、观点或交易喊单改写成已确认事实。无市场相关内容时输出空 bullets，并把 `core_view` 设为“无市场相关内容”。

### 9.2 Layer 1 — 综合总结（置顶展示）

**不再传图**，把所有 Layer 2 的 JSON 拼成 prompt 投喂：

**输出**（markdown）按 7 个内容维度分组：
1. 🇺🇸 特朗普相关（特朗普发言可能影响的美股标的、行业、事件线索）
2. 🔑 今日关键词（3-5 个高频主题）
3. 📰 重要新闻（政策 / 突发 / 财报 / 监管）
4. 📊 宏观判断（共识 + 分歧）
5. 🏭 产业 / 个股焦点（热议标的，含正反观点）
6. 💹 交易信号（期权异动、技术位、操作建议）
7. 💡 投资理念（值得收藏的长期视角）

关键章节（重要新闻、宏观判断、产业/个股焦点、交易信号、投资理念）的每条 bullet 或表格行必须带 X 来源链接，链接文字显示来源账号。Layer 1 发布前会清理明显内部工作流污染、未链接来源、关键章节无来源要点、OpenAI/Claude 归属冲突，以及韩文/日文残留过多的行。

### 9.3 Layer 3 — 盘前快报长推文（已停用）

Layer 3 曾用于把已清洗的 Layer 1 综合摘要浓缩成可复制到 X 的中文长推文，落盘到 `premarket/YYYY/MM/DD.md`。该功能后来按用户要求停用：日常 `run-once` / `regen-digest` 不再调用，也不再写入、提交或发布 `premarket/` 文件。

当前代码中仍保留 `summarizer.build_layer3_prompt` / `generate_layer3_tweet` 和 `publisher.write_premarket` 作为遗留 helper，便于未来恢复或手工实验；`config/settings.yaml.ai.max_tokens_layer3` 也仅是遗留参数。不要把它当成当前发布链路的一部分。

### 9.4 质量草稿与门禁

`kol-monitor quality-draft --date YYYY-MM-DD` 用于回查或修复某天日报，不写 DB、README、历史 digest，也不触发 git。它读取 DB 中已有 digest，输出到 `/tmp/kol-monitor-quality-drafts/<date>/`：

- `draft.md` — 推荐候选稿，优先使用通过门禁的清洗版旧摘要，否则使用规范化 Layer 2 生成的本地兜底稿
- `cleaned_existing.md` — 对旧 Layer 1 摘要做确定性清理后的版本
- `repaired_fallback.md` — 用规范化 Layer 2 重新拼出的本地兜底稿
- `layer2_normalized.json` — 过滤缺来源、外文残留、明显归属冲突后的 Layer 2 JSON
- `quality_report.json` — 质量扫描报告，记录 error/warning、行号、章节和原始片段

门禁关注：内部提示词/工作流污染、关键章节无来源内容、韩文/日文残留、OpenAI 与 Claude/Anthropic 的明显模型归属冲突、重复来源、重复要点、破损来源链接、SpaceX ticker 混淆，以及影响可读性的长普通段落。

### 9.5 失败处理

- 单 KOL 总结失败 → 该 KOL 标 `summary_failed`，不影响其他
- Layer 1 失败 → 尝试多层 Claude 后端；全部失败时使用本地兜底模板，避免当天日报完全缺失
- 发布前清洗后的 Layer 1 如果仍触发质量扫描 error，`publisher.write_outputs()` 会改用本地有来源兜底模板；如果兜底也失败，只记录错误并使用清洗版 Layer 1，遵守发布流程不因扫描异常中断

## 10. 媒体存储策略

| 类型 | 处理 |
|---|---|
| photo | 下载到 `media/YYYY-MM-DD/<handle>/<tweet_id>_<idx>.jpg`；喂给 AI；不进 git |
| video | 仅存 URL 和 thumb_url 到 DB；不下载、不喂 AI |
| gif | 同 photo，X 的 gif 实际是 mp4 但当图静态处理 |

去重：相同 `orig_url` 已下载则跳过。下载失败重试 2 次，仍失败标 `download_status='failed'`，AI 总结时跳过该图。

README / digest 里展示的图片直接用 X 原 URL，**不引用本地路径**（避免仓库膨胀，且 X CDN 长期可用）。

## 11. 发布策略

### 11.1 README.md（每天覆写）

布局：
1. 项目简介（固定）
2. 当日完整报告入口（当天 digest 链接）
3. 当日总结（Layer 1 全文，含“特朗普相关”独立分类）
4. 最近 7 天入口
5. 监控的 64 位 KOL 列表（一行一行 handle，链接到 X 主页；新增 KOL 时自动同步）
6. Layer 2 各 KOL 明细折叠区
7. 历史归档索引（最近 12 个月的链接）

日报正文里凡是涉及具体股票代码，统一展示为 `$代码` 格式，例如 `$NVDA`、`$TSLA`。

### 11.2 digests/

```
digests/
  2026/
    05/
      29.md    # 当日完整总结
      30.md
      ...
```

每月最后一天自动生成 `digests/2026/05/README.md`（月度回顾索引），方便 GitHub 目录页直接看。

> 注：自 2026-06-18 起不再生成每日 `.html`（旧 `.html` 已删除）；只产出 `README.md` + `digests/YYYY/MM/DD.md`。

### 11.3 premarket/（已停用）

```
premarket/
  2026/
    06/
      18.md    # 历史遗留示例；当前日常流程不再生成
```

当前日常流程不再生成、提交或发布 `premarket/` 文件。历史文件已删除；如果未来恢复该功能，需要重新把生成步骤接回 CLI 编排和 publish 文件列表。

### 11.4 Git 操作

```bash
git add README.md digests/2026/05/29.md
git commit -m "digest: 2026-05-29 (28 KOLs · 184 tweets)"
git push origin main
```

实际执行远端 push 还需要环境变量 `KOL_MONITOR_ALLOW_PUSH=true`。公开 clone 默认没有该变量，所以只会本地生成/提交，不会自动推送到原仓库；当前部署通过被 git 忽略的 `.env.local` 显式开启。

push 失败时：重试 3 次（指数退避），仍失败仅本地落盘，下一次 daemon 唤醒时检测未推送的 commit 重新 push。

## 12. 调度

```python
# scheduler.py
sched = BlockingScheduler(timezone=ZoneInfo("Asia/Shanghai"))
sched.add_job(daily_job, CronTrigger(hour=20, minute=30),
              misfire_grace_time=3600,  # 错过 1h 内仍补跑
              coalesce=True)
sched.start()
```

按用户要求**固定北京时间 20:30**，不随美股 DST 调整。

## 13. CLI

```
kol-monitor run-once                          # 立即跑完整流程（开发用）
kol-monitor run-once --no-publish             # 只验证到本地输出，不 push GitHub
kol-monitor daemon                            # 启动定时守护
kol-monitor fetch-only                        # 只抓取，不总结不发布
kol-monitor backfill                          # 回填 incomplete KOL
kol-monitor regen-digest --date YYYY-MM-DD    # 重新生成某天 digest
kol-monitor quality-draft --date YYYY-MM-DD   # 生成 /tmp 草稿和质量报告，不写发布文件
kol-monitor validate-handles                  # 逐个校验所有 handle
kol-monitor add-kol <handle> --validate       # 增加 KOL（去重 + 校验）
```

## 14. 风险与应对

| 风险 | 应对 |
|---|---|
| 6551 token 限流 / 欠费 | 监控 4xx；token 用尽时跳过 push，本地保留 digest |
| KOL handle 失效 | 首次拉取失败置 `active=False`，跑批不影响他人 |
| 首日 digest 内容稀疏 | 文档说明：第一天为冷启动，第二天起完整 |
| AI 输出不符合 JSON 格式 | tenacity 重试 + JSON parse fallback；保底用纯文本切片 |
| Git push 失败 | 重试 3 次后仅本地落盘，下次跑批一起 push |
| 推文含违规 / 敏感内容 | 依赖 Claude 自身安全护栏；额外按 `possibly_sensitive` 字段标注 |
| SQLite 大小膨胀 | 90 天后 `raw_json` 字段置空（保留结构化字段）|

## 15. 不做的事

明确不做以避免范围蔓延：

- ❌ KOL 分类标签（用户明确否决）
- ❌ 视频内容理解（GPT 无原生支持，Sonnet 4.6 也不支持）
- ❌ 实时 WSS 推送（一天一次够用，留扩展位）
- ❌ GitHub Pages（用户要求只 README）
- ❌ 推送图片到 GitHub（仓库膨胀风险，X CDN 直链可用）
- ❌ Web UI / API 服务（命令行和 README 已满足）

## 16. 运维说明

持久化运行、单 KOL 拉取条数、防漏拉机制和归档策略的详细说明见 [OPERATIONS.md](OPERATIONS.md)。
