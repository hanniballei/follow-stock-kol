from __future__ import annotations

import base64
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic

from kol_monitor import db
from kol_monitor.config import settings

_client: Any = None
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClaudeBackend:
    label: str
    api_key: str
    base_url: str | None
    model: str


def parse_layer2(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass
    return _parse_layer2_relaxed(text)


def _parse_layer2_relaxed(text: str) -> dict[str, Any] | None:
    body = _json_like_body(text)
    core_view = _extract_jsonish_string(body, "core_view")
    sentiment = _extract_jsonish_string(body, "sentiment") or "unclear"
    bullets = _extract_jsonish_bullets(body)
    if core_view is None and not bullets:
        return None
    return {"core_view": core_view or "", "bullets": bullets, "sentiment": sentiment}


def _json_like_body(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if match:
        return match.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def _extract_jsonish_string(body: str, key: str) -> str | None:
    match = re.search(
        rf'"{re.escape(key)}"\s*:\s*"(.*?)"\s*(?:,|\n\s*[\}}\]])',
        body,
        re.DOTALL,
    )
    if not match:
        return None
    return match.group(1).strip()


def _extract_jsonish_bullets(body: str) -> list[dict[str, Any]]:
    match = re.search(r'"bullets"\s*:\s*\[(.*?)]\s*,\s*"sentiment"', body, re.DOTALL)
    if not match:
        return []
    bullets_text = match.group(1)
    bullets = []
    for item in re.finditer(
        r'\{\s*"point"\s*:\s*"(.*?)"\s*,\s*"tickers"\s*:\s*(\[.*?])\s*,\s*"tweet_url"\s*:\s*"(.*?)"\s*\}',
        bullets_text,
        re.DOTALL,
    ):
        tickers = _parse_jsonish_tickers(item.group(2))
        bullets.append(
            {
                "point": item.group(1).strip(),
                "tickers": tickers,
                "tweet_url": item.group(3).strip(),
            }
        )
    return bullets


def _parse_jsonish_tickers(text: str) -> list[str]:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except Exception:
        pass
    return re.findall(r'"([^"]+)"', text)


def _get_client() -> Any:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required")
        _client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
        )
    return _client


async def call_claude_with_retry(messages: list[dict[str, Any]], max_tokens: int) -> Any:
    if _client is not None:
        return await _client.messages.create(
            model=settings.ai.model,
            max_tokens=max_tokens,
            temperature=settings.ai.temperature,
            messages=messages,
        )

    last_error: Exception | None = None
    for backend in _anthropic_backends():
        client = AsyncAnthropic(
            api_key=backend.api_key,
            base_url=_anthropic_sdk_base_url(backend.base_url),
        )
        try:
            return await client.messages.create(
                model=backend.model,
                max_tokens=max_tokens,
                temperature=settings.ai.temperature,
                messages=messages,
            )
        except Exception as exc:
            last_error = exc
            logger.warning("Claude request failed via %s credentials: %s", backend.label, exc)
    if last_error:
        raise last_error
    raise RuntimeError("ANTHROPIC_API_KEY is required")


def _anthropic_backends() -> list[ClaudeBackend]:
    backends: list[ClaudeBackend] = []
    if settings.anthropic_api_key:
        backends.append(
            ClaudeBackend(
                label="primary",
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_base_url,
                model=settings.ai.model,
            )
        )
    if getattr(settings, "anthropic_fallback_api_key", None):
        backends.append(
            ClaudeBackend(
                label="fallback",
                api_key=settings.anthropic_fallback_api_key,
                base_url=getattr(settings, "anthropic_fallback_base_url", None)
                or settings.anthropic_base_url,
                model=settings.ai.model,
            )
        )
    if getattr(settings, "anthropic_third_api_key", None):
        backends.append(
            ClaudeBackend(
                label="third",
                api_key=settings.anthropic_third_api_key,
                base_url=getattr(settings, "anthropic_third_base_url", None),
                model=getattr(settings, "anthropic_third_model", None) or settings.ai.model,
            )
        )
    return backends


def _anthropic_sdk_base_url(base_url: str | None) -> str | None:
    if base_url is None:
        return None
    stripped = base_url.rstrip("/")
    if stripped.endswith("/v1"):
        return stripped[:-3]
    return stripped


async def summarize_one_kol(
    kol: dict[str, Any],
    tweets: list[dict[str, Any]],
    media_files: list[Path],
) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    for path in media_files[: settings.media.max_photos_per_kol_for_ai]:
        if path.exists():
            content.append(_image_block(path))
    content.append({"type": "text", "text": _layer2_prompt(kol, tweets, bool(media_files))})
    response = await call_claude_with_retry(
        messages=[{"role": "user", "content": content}],
        max_tokens=settings.ai.max_tokens_layer2,
    )
    text = response.content[0].text
    parsed = parse_layer2(text)
    if parsed is None:
        retry_text = "请严格输出 JSON，不要包含 markdown 或解释。\n\n" + _layer2_prompt(kol, tweets, bool(media_files))
        response = await call_claude_with_retry(
            messages=[{"role": "user", "content": [{"type": "text", "text": retry_text}]}],
            max_tokens=settings.ai.max_tokens_layer2,
        )
        parsed = parse_layer2(response.content[0].text)
    if parsed is None:
        parsed = {"core_view": "summary_failed", "bullets": [], "sentiment": "unclear"}

    usage = getattr(response, "usage", None)
    parsed.update(
        {
            "screen_name": kol["screen_name"],
            "tweet_count": len(tweets),
            "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
            "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
        }
    )
    return parsed


def _image_block(path: Path) -> dict[str, Any]:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(path.suffix.lower(), "image/jpeg")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def _layer2_prompt(kol: dict[str, Any], tweets: list[dict[str, Any]], had_media: bool) -> str:
    lines = [
        f"请总结美股 KOL @{kol['screen_name']} 当日推文。",
        "涉及具体股票代码时，展示文本统一使用 $股票代码 格式，例如 $NVDA；tickers 字段仍只填不带 $ 的代码。",
        "输出严格 JSON，格式：",
        '{"core_view":"≤30字一句话","bullets":[{"point":"$NVDA ...","tickers":["NVDA"],"tweet_url":"https://x.com/..."}],"sentiment":"bullish|bearish|neutral|unclear"}',
        "推文：",
    ]
    for tweet in tweets:
        lines.append(
            "- "
            f"{tweet.get('text', '')} "
            f"(likes={tweet.get('favorite_count', 0)}, retweets={tweet.get('retweet_count', 0)}, "
            f"url={tweet.get('url')})"
        )
    if had_media:
        lines.append("部分推文包含配图；若图片缺失或无法解读，不要臆测。")
    return "\n".join(lines)


def build_layer1_prompt(
    layer2_results: list[dict[str, Any]],
    trump_summary: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    intro = (
        "请基于以下 KOL JSON 总结生成中文 markdown。"
        "请按七个维度输出，并将“特朗普相关”单独作为一级小节放在最前面："
        "特朗普相关、今日关键词、重要新闻、宏观判断、产业/个股焦点、交易信号、投资理念。"
        "“特朗普相关”小节必须总结 realDonaldTrump 当天发言可能影响的美股标的、行业、事件线索，"
        "若只是推测也要明确写出推测依据。每条要点尽量附原推链接。"
        "所有涉及具体股票代码的 markdown 文本必须使用 $代码 格式，例如 $TSLA，不要只写 TSLA。"
    )
    parts = [intro]
    if trump_summary is not None:
        parts.append("### 特朗普相关数据")
        parts.append(json.dumps(trump_summary, ensure_ascii=False))
    parts.append("### 其他 KOL 数据")
    parts.append(json.dumps(layer2_results, ensure_ascii=False))
    text = "\n\n".join(parts)
    return [{"role": "user", "content": [{"type": "text", "text": text}]}]


async def summarize_day(date: str) -> dict[str, Any]:
    tweets = db.tweets_on_date(date)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tweet in tweets:
        grouped[tweet["screen_name"]].append(tweet)

    layer2_results = []
    for screen_name, kol_tweets in grouped.items():
        kol = {"screen_name": screen_name, "id": kol_tweets[0]["kol_id"]}
        layer2_results.append(await summarize_one_kol(kol, kol_tweets, media_files=[]))

    trump_summary = next(
        (item for item in layer2_results if item["screen_name"].lower() == "realdonaldtrump"),
        None,
    )

    layer1_response = await call_claude_with_retry(
        messages=build_layer1_prompt(layer2_results, trump_summary=trump_summary),
        max_tokens=settings.ai.max_tokens_layer1,
    )
    summary_md = layer1_response.content[0].text
    input_tokens = sum(item.get("input_tokens", 0) for item in layer2_results)
    output_tokens = sum(item.get("output_tokens", 0) for item in layer2_results)
    usage = getattr(layer1_response, "usage", None)
    if usage:
        input_tokens += getattr(usage, "input_tokens", 0)
        output_tokens += getattr(usage, "output_tokens", 0)
    db.save_digest(
        date=date,
        summary_md=summary_md,
        layer2_json=json.dumps(layer2_results, ensure_ascii=False),
        kol_count=len(layer2_results),
        tweet_count=len(tweets),
        model=settings.ai.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    return {"summary_md": summary_md, "layer2": layer2_results}
