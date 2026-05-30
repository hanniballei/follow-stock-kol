# 实施计划（按文件粒度的 todo）

最后更新：2026-05-29
配套文档：
- 设计：[DESIGN.md](DESIGN.md)
- 注意事项：[../AGENTS.md](../AGENTS.md)
- 测试策略：[TESTING.md](TESTING.md)
- 运维说明：[OPERATIONS.md](OPERATIONS.md)

整体顺序按依赖关系：**骨架 → 配置 → DB → 6551 客户端 → 抓取 → 媒体 → 总结 → 发布 → CLI / 调度 → 测试 → 首跑**。每步标 `输入 / 输出 / 验证`，绝不跳步。

> ⚠️ 配置文件 `config/kols.yaml`、`config/settings.yaml`、`.env.example`、`.gitignore` 已预先创建好，步骤 2 直接复用。

---

## 步骤 0 · 启动前置（用户提供）

需用户准备：
- [x] 6551.io Bearer token（`.env` 写入 `OPENTWITTER_TOKEN`）
- [ ] Claude API base URL + key（`.env` 写入 `ANTHROPIC_BASE_URL` 和 `ANTHROPIC_API_KEY`）
- [x] GitHub remote 配好（`git remote -v` 能看到 `origin`）

代码可以在 token 全部到位前先写好，最后一步首跑时再注入。

---

## 步骤 1 · 项目骨架

文件：
- [x] `pyproject.toml` — 包元信息 + 入口 `kol-monitor = "kol_monitor.cli:main"`
- [x] `requirements.txt` — 锁定依赖（见 DESIGN §2 + 测试依赖见 TESTING §1）
- [x] `.env.example` — 已存在
- [x] `.gitignore` — 已存在
- [x] `src/kol_monitor/__init__.py` — 版本号 `__version__ = "0.1.0"`
- [x] `src/kol_monitor/logging_setup.py` — `RichHandler` + 文件 handler

**输入**：无
**输出**：能 `pip install -e .` 成功，`python -c "import kol_monitor"` 不报错
**验证**：`pip install -e . && python -c "from kol_monitor.logging_setup import setup; setup()"`

---

## 步骤 2 · 配置文件（已预先创建，仅需写加载器）

文件：
- [x] `config/kols.yaml` — 55 个 handle，已存在
- [x] `config/settings.yaml` — 全部参数，已存在
- [x] `src/kol_monitor/config.py` — 加载 yaml + dotenv，提供单例 `settings`

`config.py` 实现要点：
- 用 `pyyaml` 加载 settings.yaml 和 kols.yaml
- 用 `python-dotenv` 加载 `.env`
- 暴露 `settings` 对象，属性访问（`settings.fetcher.max_rounds`），用 dataclass 或 SimpleNamespace
- 环境变量优先级 > yaml（如 `KOL_MONITOR_DB` 覆盖默认 SQLite 路径）

**验证**：
```bash
python -c "from kol_monitor.config import settings; print(len(settings.kols), settings.schedule.hour)"
# 期望输出：55 20
```

---

## 步骤 3 · 数据库层

文件：
- [x] `src/kol_monitor/db.py`

Schema（`schema.sql` 嵌在 db.py 里，启动时 `CREATE IF NOT EXISTS`）：

```sql
CREATE TABLE IF NOT EXISTS kols (
  id INTEGER PRIMARY KEY,
  screen_name TEXT UNIQUE NOT NULL,
  display_name TEXT,
  twitter_user_id TEXT,
  last_seen_tweet_id TEXT,
  last_fetched_at TIMESTAMP,
  incomplete BOOLEAN DEFAULT 0,
  active BOOLEAN DEFAULT 1,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tweets (
  tweet_id TEXT PRIMARY KEY,
  kol_id INTEGER REFERENCES kols(id),
  text TEXT,
  created_at TIMESTAMP,
  language TEXT,
  is_retweet BOOLEAN DEFAULT 0,
  is_quote BOOLEAN DEFAULT 0,
  is_reply BOOLEAN DEFAULT 0,
  conversation_id TEXT,
  reply_count INTEGER, retweet_count INTEGER,
  favorite_count INTEGER, view_count INTEGER, quote_count INTEGER,
  url TEXT,
  raw_json TEXT,
  fetched_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tweets_kol_created ON tweets(kol_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tweets_created ON tweets(created_at DESC);

CREATE TABLE IF NOT EXISTS media (
  id INTEGER PRIMARY KEY,
  tweet_id TEXT REFERENCES tweets(tweet_id),
  type TEXT,
  orig_url TEXT,
  thumb_url TEXT,
  local_path TEXT,
  download_status TEXT DEFAULT 'pending',
  downloaded_at TIMESTAMP,
  UNIQUE(tweet_id, orig_url)
);

CREATE TABLE IF NOT EXISTS digests (
  date DATE PRIMARY KEY,
  kol_count INTEGER,
  tweet_count INTEGER,
  summary_md TEXT,
  layer2_json TEXT,
  model TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  status TEXT DEFAULT 'ok',
  generated_at TIMESTAMP,
  published_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fetch_runs (
  id INTEGER PRIMARY KEY,
  started_at TIMESTAMP, finished_at TIMESTAMP,
  trigger TEXT,
  kols_total INTEGER, kols_ok INTEGER, kols_failed INTEGER,
  tweets_new INTEGER,
  error_log TEXT
);
```

DAO 函数清单（最低必需）：
- `init_db(path) -> None`
- `upsert_kol(screen_name, display_name=None, twitter_user_id=None) -> kol_id`
- `get_kol(screen_name) -> dict | None`
- `list_active_kols() -> list[dict]`
- `update_kol_anchor(kol_id, last_seen_tweet_id, last_fetched_at, incomplete) -> None`
- `mark_kol_inactive(screen_name, reason) -> None`
- `insert_tweet(tweet_dict) -> bool`（INSERT OR IGNORE，返回是否真实插入）
- `tweets_by_kol_on_date(kol_id, date) -> list[dict]`
- `tweets_on_date(date) -> list[dict]`
- `insert_media(...)`
- `pending_media_for_date(date) -> list[dict]`
- `mark_media_downloaded(media_id, local_path) -> None`
- `save_digest(date, summary_md, layer2_json, ...) -> None`
- `start_run(trigger) -> run_id`
- `finish_run(run_id, kols_ok, kols_failed, tweets_new, error_log)`

**输入**：步骤 2 的 settings
**输出**：可创建 SQLite 文件并跑通 CRUD
**验证**：写 `tests/test_db.py` 跑一遍 init + upsert_kol + insert_tweet round-trip

---

## 步骤 4 · 6551 REST 客户端

文件：
- [x] `src/kol_monitor/client.py`

封装：
```python
class OpenTwitterClient:
    def __init__(self, token, base_url="https://ai.6551.io", timeout=30): ...
    async def user_info(self, username: str) -> dict | None: ...
    async def user_tweets(self, username, max_results=50,
                          product="Latest",
                          include_replies=False,
                          include_retweets=True) -> list[dict]: ...
    async def search(self, from_user=None, since_date=None, until_date=None,
                     keywords=None, max_results=100,
                     product="Latest") -> list[dict]: ...
    async def tweet_by_id(self, tw_id) -> dict | None: ...
```

注意：
- 鉴权：`Authorization: Bearer {token}`
- 所有方法 POST，body application/json
- 响应统一壳 `{"data": ...}`，4xx/5xx 直接 `raise_for_status()`
- 用 tenacity 装饰器：`@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))`，仅对 ConnectError、ReadTimeout 重试，4xx 不重试
- 把响应字段标准化到内部 dict（`tweet_id`, `created_at` 转 datetime，等等）

**输入**：步骤 3 的 DB；token 来自 .env
**输出**：异步客户端能调通 4 个 endpoint
**验证**：`tests/test_client_mock.py` 用 respx 模拟 httpx 返回，测试解析

---

## 步骤 5 · 抓取主流程（含防漏拉）

文件：
- [x] `src/kol_monitor/fetcher.py`

核心函数：

```python
async def daily_fetch(trigger="scheduled") -> RunStats: ...
async def fetch_one_kol(client, kol: dict) -> KolFetchResult: ...
async def backfill_incomplete(client) -> None: ...
async def validate_handle(client, handle: str) -> dict | None: ...
```

`fetch_one_kol` 实现 DESIGN §8 的算法（首次 vs 增量分支）。

约束：
- 每个 KOL 之间 `await asyncio.sleep(uniform(2, 5))`
- 单个 KOL 内的 round 之间不再额外 sleep
- INSERT OR IGNORE，不靠程序去重，靠 DB 主键
- last_seen_tweet_id 比较用字符串还是 int？— **用 int**，因为 X tweet_id 是 64-bit 数字，字符串比较在长度不同时会错（虽然同时间段长度一样，但跨年可能不同）

**输入**：client + db + settings
**输出**：当日新推数 + 各 KOL 状态
**验证**：`tests/test_fetcher_gap.py` 用 mock client 模拟以下场景：
- 首次接入 → 全量入库
- 增量重叠 → 只插新增
- 增量无重叠 → 标 incomplete
- search 兜底 → 补全后清 incomplete

---

## 步骤 6 · 媒体下载

文件：
- [x] `src/kol_monitor/media.py`

```python
async def download_pending_media(date) -> tuple[int, int]: ...
async def download_one(media_id, url, dest_dir) -> Path | None: ...
def media_path(date, handle, tweet_id, idx, ext) -> Path: ...
def detect_ext(url, content_type) -> str: ...
def validate_image(path: Path) -> bool: ...  # PIL Image.verify
```

约束：
- 只下载 type in ('photo', 'gif')；type='video' 跳过（DESIGN §10）
- 同 URL 已下载（local_path 非空且文件存在）跳过
- 下载到临时文件 `.part`，校验通过后 rename，避免半截图
- 失败不抛异常，标 `download_status='failed'`
- 限并发（asyncio.Semaphore(8)）

**输入**：当日 pending media 列表
**输出**：`media/2026-05-29/<handle>/<tweet_id>_<idx>.jpg`
**验证**：可以用一组真实 X 图片 URL 跑一遍（保留 1-2 个测试用 URL）

---

## 步骤 7 · AI 总结

文件：
- [x] `src/kol_monitor/summarizer.py`

```python
async def summarize_day(date) -> DigestResult: ...
async def summarize_one_kol(kol, tweets, media_files) -> Layer2Result: ...
def build_layer1_prompt(layer2_results) -> list[Message]: ...
async def call_claude_with_retry(messages, max_tokens) -> ClaudeResponse: ...
```

实现要点：
- anthropic SDK 实例化时注入 `base_url`、`api_key`
- 图片走 `{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": ...}}`
- Layer 2 prompt 要求输出 JSON，用 `response.content[0].text` 后 json.loads，失败重试一次（带"请严格按此 JSON 输出"prompt 强化）
- Layer 1 prompt 是 markdown 输出，按 6 维度（DESIGN §9.2）
- Layer 1 / Layer 2 展示文本里涉及具体股票代码时统一用 `$代码`，例如 `$NVDA`
- token 计数累加到 `digests.input_tokens / output_tokens`

**输入**：当日 tweets + media
**输出**：`digests` 表一条记录（summary_md + layer2_json）
**验证**：`tests/test_summarizer_mock.py` 用 mock anthropic client 验证 prompt 构造和 JSON parse fallback

---

## 步骤 8 · 发布 / 渲染

文件：
- [x] `src/kol_monitor/publisher.py`

```python
def render_readme(date, layer1_md, layer2_kols, kol_list, history_dirs) -> str: ...
def render_digest_md(date, layer1_md, layer2_kols) -> str: ...
def render_monthly_index(year, month) -> str: ...
def write_outputs(date) -> tuple[Path, Path]: ...
def git_publish(date, files: list[Path]) -> bool: ...
```

约束：
- README 模板用 jinja2 不必要，直接 f-string + 拼接就够
- KOL 列表渲染：每位用 `[@{handle}](https://x.com/{handle})` 格式
- Layer 2 折叠用 `<details><summary>...</summary>...</details>`，按当日发推数倒序
- Layer 2 的 `tickers` 渲染为 `$代码`，即使模型返回不带 `$` 的 `NVDA` 也要显示为 `$NVDA`
- 推文链接：`https://x.com/{handle}/status/{tweet_id}`
- 历史归档区：列出 `digests/` 下最近 12 个月的目录链接

**输入**：当日 digest 数据
**输出**：`README.md` 覆写 + `digests/2026/05/29.md` 新增；git commit + push
**验证**：`tests/test_publisher.py` 检查渲染结果（snapshot test）

---

## 步骤 9 · CLI 和调度

文件：
- [x] `src/kol_monitor/cli.py`
- [x] `src/kol_monitor/scheduler.py`

CLI 入口：
```
kol-monitor run-once
kol-monitor daemon
kol-monitor fetch-only
kol-monitor backfill --days 7 [--kol handle]
kol-monitor regen-digest --date 2026-05-29
kol-monitor add-kol <handle>
kol-monitor list-kols
```

用 `argparse`（不引 click，少依赖）。

scheduler.py：
```python
def main():
    sched = BlockingScheduler(timezone=ZoneInfo("Asia/Shanghai"))
    sched.add_job(daily_job_sync_wrapper,
                  CronTrigger(hour=20, minute=30),
                  misfire_grace_time=3600,
                  coalesce=True)
    sched.start()
```

**输入**：之前所有模块
**输出**：可运行的 CLI 和 daemon
**验证**：`kol-monitor run-once --dry-run` 走通整个流程（不真调 API，靠环境变量切到 mock 模式）

---

## 步骤 10 · 测试

详细测试策略、fixture、mock 示例代码见 [TESTING.md](TESTING.md)。

`tests/` 目录：
- [x] `conftest.py` — 共享 fixture（tmp_db、sample_tweet、make_tweet）
- [x] `test_db.py` — schema + DAO round-trip
- [x] `test_client_mock.py` — respx 模拟 6551 响应（含 4xx 不重试、网络错误重试）
- [x] `test_fetcher_gap.py` — 防漏拉 4 种场景（首次 / 重叠 / 无重叠 / search 兜底）
- [x] `test_summarizer_mock.py` — JSON parse fallback + mock anthropic
- [x] `test_publisher.py` — markdown snapshot

**测试不依赖网络**。运行：`pytest tests/ -v`

依赖（写进 pyproject.toml `[project.optional-dependencies] dev`）：
```
pytest>=8.0
pytest-asyncio>=0.23
respx>=0.21
freezegun>=1.4
```

---

## 步骤 11 · 首跑（用户介入）

按顺序：

1. 用户填好 `.env`（3 个变量）
2. 用户配好 git remote（`git remote add origin git@github.com:...`）
3. `kol-monitor list-kols` 校验 55 个 handle 都被加载
4. `kol-monitor add-kol --validate-all` 用 `twitter_user_info` 逐个校验拼写，失败的标 inactive 并报告
5. `kol-monitor run-once` 跑一次完整流程（冷启动只拉当天）
6. 检查 `digests/2026/05/29.md` 和 `README.md` 输出
7. 检查 git commit 和 push
8. 启动守护：`nohup kol-monitor daemon > kol_monitor.log 2>&1 &`，或写 systemd unit

---

## 进度跟踪

每完成一步，把方框 `[ ]` 改成 `[x]` 并 commit。

---

## 时间估算

| 步骤 | 预估 |
|---|---|
| 0-1 骨架 | 30 min |
| 2-3 配置 + DB | 1 h |
| 4-5 client + fetcher | 2 h |
| 6 media | 1 h |
| 7 summarizer | 2 h |
| 8 publisher | 1.5 h |
| 9 CLI + scheduler | 1 h |
| 10 测试 | 1.5 h |
| 11 首跑调试 | 视用户准备进度而定 |
| **代码部分** | **~10.5 h** |
