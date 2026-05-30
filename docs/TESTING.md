# 测试策略与示例

最后更新：2026-05-29

> 本项目所有测试**严禁依赖网络**。6551 / Anthropic / Git 远端调用一律 mock。
> 运行方式：`pytest tests/ -v`

---

## 1. 测试依赖

```toml
# pyproject.toml [project.optional-dependencies] dev
pytest>=8.0
pytest-asyncio>=0.23
respx>=0.21          # mock httpx
freezegun>=1.4       # 冻结时间，让 created_at / today() 可控
```

`pytest.ini` 或 `pyproject.toml [tool.pytest.ini_options]`：

```ini
asyncio_mode = auto
testpaths = ["tests"]
```

---

## 2. 共享 fixture（`tests/conftest.py`）

```python
import asyncio, json, os, tempfile
from pathlib import Path
import pytest
from kol_monitor.db import init_db, upsert_kol

@pytest.fixture
def tmp_db(monkeypatch):
    """每个测试一个干净的临时 SQLite。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("KOL_MONITOR_DB", path)
    init_db(path)
    yield path
    os.unlink(path)

@pytest.fixture
def sample_tweet():
    return {
        "id": "1800000000000000001",
        "text": "$NVDA earnings tonight, watching for guidance",
        "createdAt": "2026-05-29T18:00:00Z",
        "language": "en",
        "userScreenName": "qinbafrank",
        "userIdStr": "12345",
        "retweetCount": 5, "favoriteCount": 50,
        "replyCount": 3, "quoteCount": 1, "viewCount": 2000,
        "isReply": False, "isQuote": False,
        "media": [{"type": "photo",
                   "url": "https://pbs.twimg.com/media/abc.jpg",
                   "thumbUrl": "https://pbs.twimg.com/media/abc.jpg:thumb"}],
        "urls": [],
        "mentions": [],
    }

@pytest.fixture
def make_tweet(sample_tweet):
    """生成连续 tweet_id 的工厂。"""
    base_id = 1800000000000000000
    counter = {"i": 0}
    def _make(handle="qinbafrank", text="hello", offset=None, **overrides):
        counter["i"] += 1
        tid = base_id + (offset if offset is not None else counter["i"])
        t = {**sample_tweet,
             "id": str(tid),
             "userScreenName": handle,
             "text": text,
             **overrides}
        return t
    return _make
```

---

## 3. `tests/test_db.py` — schema + DAO round-trip

```python
from datetime import datetime
from kol_monitor.db import (upsert_kol, get_kol, insert_tweet,
                             update_kol_anchor, list_active_kols,
                             tweets_on_date)

def test_upsert_and_get_kol(tmp_db):
    kid = upsert_kol("qinbafrank")
    assert kid > 0
    again = upsert_kol("qinbafrank", display_name="秦伯")
    assert again == kid                       # 幂等
    row = get_kol("qinbafrank")
    assert row["display_name"] == "秦伯"

def test_insert_tweet_idempotent(tmp_db, sample_tweet):
    kid = upsert_kol("qinbafrank")
    inserted1 = insert_tweet({**sample_tweet, "kol_id": kid})
    inserted2 = insert_tweet({**sample_tweet, "kol_id": kid})
    assert inserted1 is True
    assert inserted2 is False                  # INSERT OR IGNORE 第二次返回 False

def test_anchor_update(tmp_db):
    kid = upsert_kol("qinbafrank")
    update_kol_anchor(kid, "1800000000000000050",
                       datetime.utcnow(), incomplete=False)
    row = get_kol("qinbafrank")
    assert row["last_seen_tweet_id"] == "1800000000000000050"
    assert row["incomplete"] == 0
```

---

## 4. `tests/test_client_mock.py` — 用 respx mock 6551

```python
import httpx, respx
import pytest
from kol_monitor.client import OpenTwitterClient

@pytest.mark.asyncio
@respx.mock
async def test_user_tweets_parses_camelcase_to_snake():
    respx.post("https://ai.6551.io/open/twitter_user_tweets").mock(
        return_value=httpx.Response(200, json={"data": [{
            "id": "1800000000000000123",
            "text": "hi",
            "createdAt": "2026-05-29T10:00:00Z",
            "userScreenName": "qinbafrank",
            "userIdStr": "12345",
            "retweetCount": 1, "favoriteCount": 2,
            "replyCount": 0, "quoteCount": 0, "viewCount": 100,
            "isReply": False, "isQuote": False,
            "media": [], "urls": [], "mentions": [],
        }]}))

    c = OpenTwitterClient(token="test", base_url="https://ai.6551.io")
    tweets = await c.user_tweets("qinbafrank", max_results=10)
    await c.close()

    assert len(tweets) == 1
    assert tweets[0]["tweet_id"] == "1800000000000000123"      # 标准化字段
    assert tweets[0]["favorite_count"] == 2
    assert tweets[0]["screen_name"] == "qinbafrank"

@pytest.mark.asyncio
@respx.mock
async def test_4xx_does_not_retry():
    route = respx.post("https://ai.6551.io/open/twitter_user_info").mock(
        return_value=httpx.Response(401, json={"error": "invalid token"}))

    c = OpenTwitterClient(token="bad", base_url="https://ai.6551.io")
    with pytest.raises(httpx.HTTPStatusError):
        await c.user_info("qinbafrank")
    await c.close()
    assert route.call_count == 1                                # 只调一次，不重试

@pytest.mark.asyncio
@respx.mock
async def test_network_error_retries():
    route = respx.post("https://ai.6551.io/open/twitter_user_info").mock(
        side_effect=[httpx.ConnectError("boom"),
                     httpx.ConnectError("boom"),
                     httpx.Response(200, json={"data": {
                         "userId": "1", "screenName": "qinbafrank",
                         "name": "qb", "followersCount": 100}})])

    c = OpenTwitterClient(token="test", base_url="https://ai.6551.io")
    res = await c.user_info("qinbafrank")
    await c.close()
    assert route.call_count == 3
    assert res["screen_name"] == "qinbafrank"
```

---

## 5. `tests/test_fetcher_gap.py` — 防漏拉 4 种场景

用一个 `FakeClient` 替代真客户端（不走 respx，因为 fetcher 调的是 `OpenTwitterClient` 实例方法）：

```python
from datetime import datetime, timezone
import pytest
from kol_monitor.db import upsert_kol, get_kol, tweets_on_date
from kol_monitor.fetcher import fetch_one_kol

class FakeClient:
    def __init__(self, pages):
        # pages: list[list[tweet]]，每次 user_tweets 返回 pages[call_idx]
        self.pages = list(pages)
        self.calls = 0
        self.search_calls = 0
        self.search_result = []

    async def user_tweets(self, username, max_results=50, **kw):
        idx = min(self.calls, len(self.pages) - 1)
        self.calls += 1
        return self.pages[idx]

    async def search(self, **kw):
        self.search_calls += 1
        return self.search_result


@pytest.mark.asyncio
async def test_first_time_fetch_inserts_all(tmp_db, make_tweet):
    upsert_kol("qinbafrank")
    kol = get_kol("qinbafrank")
    client = FakeClient(pages=[[make_tweet(offset=10),
                                 make_tweet(offset=11),
                                 make_tweet(offset=12)]])
    res = await fetch_one_kol(client, kol)

    assert res.inserted == 3
    assert res.incomplete is False
    refreshed = get_kol("qinbafrank")
    assert refreshed["last_seen_tweet_id"] == str(1800000000000000012)


@pytest.mark.asyncio
async def test_incremental_with_overlap(tmp_db, make_tweet):
    upsert_kol("qinbafrank")
    # 模拟首次已抓到 id 100
    from kol_monitor.db import update_kol_anchor
    update_kol_anchor(get_kol("qinbafrank")["id"],
                      str(1800000000000000100),
                      datetime.now(timezone.utc), incomplete=False)
    kol = get_kol("qinbafrank")

    # 这次返回有 id=99(<anchor),100(=anchor),101,102 — 应只插 101 和 102
    client = FakeClient(pages=[[
        make_tweet(offset=102), make_tweet(offset=101),
        make_tweet(offset=100), make_tweet(offset=99)]])
    res = await fetch_one_kol(client, kol)
    assert res.inserted == 2
    assert res.incomplete is False


@pytest.mark.asyncio
async def test_no_overlap_marks_incomplete(tmp_db, make_tweet):
    upsert_kol("qinbafrank")
    from kol_monitor.db import update_kol_anchor
    update_kol_anchor(get_kol("qinbafrank")["id"],
                      str(1800000000000000050),
                      datetime.now(timezone.utc), incomplete=False)
    kol = get_kol("qinbafrank")

    # 5 轮翻页都没遇到 id=50 — 全是新推（id 远 > 锚点），翻不到旧的
    pages = [[make_tweet(offset=200 + r * 10 + i) for i in range(10)]
             for r in range(5)]
    client = FakeClient(pages=pages)
    res = await fetch_one_kol(client, kol)
    assert res.incomplete is True


@pytest.mark.asyncio
async def test_search_backfill_clears_incomplete(tmp_db, make_tweet):
    """主任务标了 incomplete，backfill 阶段用 search 补全后清标记。"""
    from kol_monitor.fetcher import backfill_incomplete
    from kol_monitor.db import update_kol_anchor

    upsert_kol("qinbafrank")
    kid = get_kol("qinbafrank")["id"]
    update_kol_anchor(kid, str(1800000000000000050),
                      datetime.now(timezone.utc), incomplete=True)

    client = FakeClient(pages=[])
    client.search_result = [make_tweet(offset=51), make_tweet(offset=52)]
    await backfill_incomplete(client)

    after = get_kol("qinbafrank")
    assert after["incomplete"] == 0
    assert client.search_calls == 1
```

---

## 6. `tests/test_summarizer_mock.py` — JSON 解析 fallback

```python
import json, pytest
from kol_monitor.summarizer import parse_layer2

def test_parse_clean_json():
    res = parse_layer2('{"core_view":"x","bullets":[],"sentiment":"neutral"}')
    assert res["sentiment"] == "neutral"

def test_parse_markdown_fenced():
    raw = '```json\n{"core_view":"x","bullets":[],"sentiment":"bullish"}\n```'
    assert parse_layer2(raw)["sentiment"] == "bullish"

def test_parse_text_with_prelude():
    raw = ('好的，我来分析：\n\n'
           '{"core_view":"x","bullets":[],"sentiment":"bearish"}\n\n剩余说明')
    assert parse_layer2(raw)["sentiment"] == "bearish"

def test_parse_invalid_returns_none():
    assert parse_layer2("totally not json") is None
```

总结调用本身用 mock anthropic client：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_summarize_one_kol_builds_correct_message(monkeypatch):
    fake = AsyncMock()
    fake.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text='{"core_view":"v","bullets":[],"sentiment":"neutral"}')],
        usage=MagicMock(input_tokens=100, output_tokens=20),
    ))
    monkeypatch.setattr("kol_monitor.summarizer._client", fake)

    from kol_monitor.summarizer import summarize_one_kol
    res = await summarize_one_kol(
        kol={"screen_name": "qinbafrank", "id": 1},
        tweets=[{"tweet_id": "1", "text": "hi", "url": "https://x.com/.../1",
                 "favorite_count": 1, "retweet_count": 0}],
        media_files=[])
    assert res["sentiment"] == "neutral"
    fake.messages.create.assert_called_once()
```

---

## 7. `tests/test_publisher.py` — markdown snapshot

```python
import re
from kol_monitor.publisher import render_readme, render_digest_md

def test_render_readme_contains_required_sections():
    md = render_readme(
        date="2026-05-29",
        layer1_md="### 🔑 今日关键词\n通胀降温",
        layer2_kols=[
            {"screen_name": "qinbafrank", "tweet_count": 3,
             "core_view": "英伟达财报后科技股估值进入消化期",
             "bullets": [{"point": "看好半导体设备", "tickers": ["AMAT"],
                          "tweet_url": "https://x.com/qinbafrank/status/1"}],
             "sentiment": "bullish"}
        ],
        kol_list=["qinbafrank", "NickTimiraos"],
        history_dirs=[("2026-05", "digests/2026/05/"),
                       ("2026-04", "digests/2026/04/")],
    )
    assert "## 监控的 KOL" in md
    assert "[@qinbafrank](https://x.com/qinbafrank)" in md
    assert "<details>" in md
    assert "## 历史归档" in md
    assert "https://x.com/qinbafrank/status/1" in md
    assert "2026-05-29" in md

def test_digest_md_no_collapse():
    md = render_digest_md(
        date="2026-05-29",
        layer1_md="### 🔑 今日关键词\n...",
        layer2_kols=[],
    )
    assert "<details>" not in md             # 独立 digest 文件不折叠
```

---

## 8. 不写的测试

明确不在测试覆盖范围内（避免范围蔓延 + 网络依赖）：

- ❌ 真调 6551 API 的集成测试
- ❌ 真调 Claude 的端到端测试
- ❌ git push 到真远端
- ❌ 真下载 X CDN 图片
- ❌ apscheduler 触发时机测试（信任 apscheduler 自身）

这些靠 `kol-monitor run-once --dry-run`（步骤 9 的 CLI）做手工冒烟。

---

## 9. CI（可选，未来）

如果接 GitHub Actions：
```yaml
- run: pip install -e ".[dev]"
- run: pytest tests/ -v --tb=short
```

不接也不影响主流程。
