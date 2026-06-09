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
GENERIC_SOURCE_LABEL_RE = re.compile(r"^(来源|链接|原文|原推)\s*(\d*)$")
TWEET_URL_RE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/([^/]+)/status/[^)\s]+")
UNLINKED_SOURCE_LABEL_RE = re.compile(r"\[@[^\]]+\](?!\()")
INTERNAL_ARTIFACT_MARKERS = (
    "investigate_before_answering",
    "读代码",
    "系统行为",
    "AGENTS.md",
    "Codex",
    "提示词",
    "工作原则",
)
REQUIRED_LAYER1_SECTIONS = (
    "特朗普相关",
    "今日关键词",
    "重要新闻",
    "宏观判断",
    "产业/个股焦点",
    "交易信号",
    "投资理念",
)
LAYER1_VALID_END_CHARS = set("。！？.!?)]）】」』”’…|")


@dataclass(frozen=True)
class ClaudeBackend:
    label: str
    api_key: str
    base_url: str | None
    model: str
    temperature: float
    thinking: dict[str, Any] | None = None


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


def normalize_layer1_source_links(markdown: str) -> str:
    def replace(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        generic = GENERIC_SOURCE_LABEL_RE.match(label.strip())
        tweet = TWEET_URL_RE.match(url)
        if generic is None or tweet is None:
            return match.group(0)
        kind, suffix = generic.groups()
        handle = tweet.group(1)
        if kind == "原文" and handle.lower() == "realdonaldtrump":
            new_label = f"@{handle} 原文{suffix}".rstrip()
        elif suffix:
            new_label = f"@{handle} · {suffix}"
        else:
            new_label = f"@{handle}"
        return f"[{new_label}]({url})"

    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", replace, markdown)


def _clean_layer1_markdown(markdown: str) -> str:
    cleaned = []
    for line in markdown.splitlines():
        stripped = line.strip()
        is_bullet = stripped.startswith(("- ", "* "))
        if is_bullet and any(marker in line for marker in INTERNAL_ARTIFACT_MARKERS):
            continue
        if is_bullet and UNLINKED_SOURCE_LABEL_RE.search(line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _prepare_layer1_markdown(markdown: str) -> str:
    return _clean_layer1_markdown(normalize_layer1_source_links(markdown)).strip()


def _is_valid_layer1_markdown(markdown: str, stop_reason: str | None = None) -> bool:
    return _layer1_validation_error(markdown, stop_reason=stop_reason) is None


def _layer1_validation_error(markdown: str, stop_reason: str | None = None) -> str | None:
    if stop_reason == "max_tokens":
        return "response stopped at max_tokens"

    top_summary = _layer1_top_summary(markdown)
    headings = _layer1_headings(top_summary)
    if not headings:
        return "missing layer1 markdown headings"

    required_positions: list[int] = []
    for section in REQUIRED_LAYER1_SECTIONS:
        position = next(
            (
                line_no
                for line_no, heading in headings
                if _normalize_layer1_heading(section) in _normalize_layer1_heading(heading)
            ),
            None,
        )
        if position is None:
            return f"missing layer1 section: {section}"
        required_positions.append(position)

    if required_positions != sorted(required_positions):
        return "layer1 sections are out of order"

    lines = top_summary.splitlines()
    for index, section in enumerate(REQUIRED_LAYER1_SECTIONS):
        start = required_positions[index] + 1
        end = required_positions[index + 1] if index + 1 < len(required_positions) else len(lines)
        body = [line.strip() for line in lines[start:end] if line.strip() and line.strip() != "---"]
        if not body:
            return f"empty layer1 section: {section}"

    if _layer1_looks_truncated(top_summary):
        return "layer1 summary appears truncated"
    return None


def _layer1_top_summary(markdown: str) -> str:
    return re.split(r"(?m)^\s{0,3}#{2,4}\s*各\s*KOL\b", markdown, maxsplit=1)[0].strip()


def _layer1_headings(markdown: str) -> list[tuple[int, str]]:
    headings = []
    for line_no, line in enumerate(markdown.splitlines()):
        match = re.match(r"^\s{0,3}#{2,4}\s+(.+?)\s*$", line)
        if match:
            headings.append((line_no, match.group(1).strip()))
    return headings


def _normalize_layer1_heading(heading: str) -> str:
    text = re.sub(r"[*_`#]", "", heading)
    text = re.sub(r"^\s*(?:[一二三四五六七八九十]+|\d+)[、.．]\s*", "", text)
    text = re.sub(r"\s*/\s*", "/", text)
    return re.sub(r"\s+", "", text)


def _layer1_looks_truncated(markdown: str) -> bool:
    lines = [line.strip() for line in markdown.splitlines() if line.strip() and line.strip() != "---"]
    if not lines:
        return True
    last = lines[-1]
    if _has_unbalanced_quotes(last):
        return True
    if last[-1] in {",", "，", ":", "：", ";", "；", "、", "(", "（", "[", "【", '"', "“"}:
        return True
    if last[-1] in LAYER1_VALID_END_CHARS:
        return False
    return last.startswith(("- ", "* ")) and len(last) >= 24


def _has_unbalanced_quotes(text: str) -> bool:
    return (
        text.count('"') % 2 == 1
        or text.count("“") != text.count("”")
        or text.count("‘") != text.count("’")
    )


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
        try:
            return await _call_claude_backend(backend, messages, max_tokens)
        except Exception as exc:
            last_error = exc
            logger.warning("Claude request failed via %s credentials: %s", backend.label, exc)
    if last_error:
        raise last_error
    raise RuntimeError("ANTHROPIC_API_KEY is required")


async def call_layer1_with_validation(messages: list[dict[str, Any]], max_tokens: int) -> Any:
    if _client is not None:
        response = await _client.messages.create(
            model=settings.ai.model,
            max_tokens=max_tokens,
            temperature=settings.ai.temperature,
            messages=messages,
        )
        _raise_for_invalid_layer1(response)
        return response

    last_error: Exception | None = None
    for backend in _anthropic_backends():
        try:
            response = await _call_claude_backend(backend, messages, max_tokens)
            _raise_for_invalid_layer1(response)
            return response
        except Exception as exc:
            last_error = exc
            logger.warning("Claude layer1 request failed via %s credentials: %s", backend.label, exc)
    if last_error:
        raise last_error
    raise RuntimeError("ANTHROPIC_API_KEY is required")


def _raise_for_invalid_layer1(response: Any) -> None:
    markdown = _prepare_layer1_markdown(_response_text(response))
    reason = _layer1_validation_error(markdown, stop_reason=getattr(response, "stop_reason", None))
    if reason:
        raise ValueError(reason)


def _response_text(response: Any) -> str:
    content = getattr(response, "content", [])
    if not content:
        return ""
    return str(getattr(content[0], "text", "") or "")


async def _call_claude_backend(
    backend: ClaudeBackend,
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> Any:
    client = AsyncAnthropic(
        api_key=backend.api_key,
        base_url=_anthropic_sdk_base_url(backend.base_url),
    )
    request = {
        "model": backend.model,
        "max_tokens": max_tokens,
        "temperature": backend.temperature,
        "messages": messages,
    }
    if backend.thinking is not None:
        request["thinking"] = backend.thinking
    return await client.messages.create(**request)


def _anthropic_backends() -> list[ClaudeBackend]:
    backends: list[ClaudeBackend] = []
    if settings.anthropic_api_key:
        backends.append(
            ClaudeBackend(
                label="primary",
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_base_url,
                model=settings.ai.model,
                temperature=settings.ai.temperature,
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
                temperature=settings.ai.temperature,
            )
        )
    if getattr(settings, "anthropic_third_api_key", None):
        backends.append(
            ClaudeBackend(
                label="third",
                api_key=settings.anthropic_third_api_key,
                base_url=getattr(settings, "anthropic_third_base_url", None),
                model=getattr(settings, "anthropic_third_model", None) or settings.ai.model,
                temperature=1,
                thinking={"type": "disabled"},
            )
        )
    if getattr(settings, "anthropic_fourth_api_key", None):
        backends.append(
            ClaudeBackend(
                label="fourth",
                api_key=settings.anthropic_fourth_api_key,
                base_url=getattr(settings, "anthropic_fourth_base_url", None),
                model=getattr(settings, "anthropic_fourth_model", None) or settings.ai.model,
                temperature=settings.ai.temperature,
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
    messages = [{"role": "user", "content": content}]
    retry_text = "请严格输出 JSON，不要包含 markdown 或解释。\n\n" + _layer2_prompt(
        kol, tweets, bool(media_files)
    )
    retry_messages = [{"role": "user", "content": [{"type": "text", "text": retry_text}]}]
    parsed, response = await _call_layer2_until_parsed(messages, retry_messages)
    if parsed is None:
        parsed = {"core_view": "summary_failed", "bullets": [], "sentiment": "unclear"}

    usage = getattr(response, "usage", None) if response else None
    parsed.update(
        {
            "screen_name": kol["screen_name"],
            "tweet_count": len(tweets),
            "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
            "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
        }
    )
    return parsed


async def _call_layer2_until_parsed(
    messages: list[dict[str, Any]],
    retry_messages: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, Any | None]:
    if _client is not None:
        response = await _client.messages.create(
            model=settings.ai.model,
            max_tokens=settings.ai.max_tokens_layer2,
            temperature=settings.ai.temperature,
            messages=messages,
        )
        parsed = parse_layer2(response.content[0].text)
        if parsed is not None:
            return parsed, response
        response = await _client.messages.create(
            model=settings.ai.model,
            max_tokens=settings.ai.max_tokens_layer2,
            temperature=settings.ai.temperature,
            messages=retry_messages,
        )
        return parse_layer2(response.content[0].text), response

    last_error: Exception | None = None
    last_response: Any | None = None
    saw_response = False
    for backend in _anthropic_backends():
        for attempt_messages in (messages, retry_messages):
            try:
                response = await _call_claude_backend(
                    backend,
                    attempt_messages,
                    settings.ai.max_tokens_layer2,
                )
            except Exception as exc:
                last_error = exc
                logger.warning("Claude request failed via %s credentials: %s", backend.label, exc)
                break
            saw_response = True
            last_response = response
            parsed = parse_layer2(response.content[0].text)
            if parsed is not None:
                return parsed, response
        logger.warning(
            "Claude response via %s credentials was not valid layer2 JSON; trying next backend",
            backend.label,
        )
    if not saw_response and last_error:
        raise last_error
    return None, last_response


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
        "请基于以下 KOL JSON 总结生成中文 markdown，只输出正文，不要输出日报标题、分隔线或 emoji。"
        "必须按顺序完整输出且只输出以下七个二级标题："
        "## 特朗普相关、## 今日关键词、## 重要新闻、## 宏观判断、"
        "## 产业/个股焦点、## 交易信号、## 投资理念。"
        "不要遗漏任何标题；如果某节信息不足，写一条“暂无高质量信号。”，也必须保留该标题。"
        "先合并重复信息，再写结论，避免逐条复述同一账号的相似推文。"
        "篇幅控制：特朗普相关 3-6 条；今日关键词用 8-12 个普通 bullet，不要表格；"
        "重要新闻 6-10 条；宏观判断 4-8 条；产业/个股焦点 8-12 条；"
        "交易信号最多 8 行 markdown 表格；投资理念 4-8 条。"
        "“特朗普相关”小节必须总结 realDonaldTrump 当天发言可能影响的美股标的、行业、事件线索，"
        "若只是推测也要明确写出推测依据。每条要点尽量附原推链接。"
        "所有涉及具体股票代码的 markdown 文本必须使用 $代码 格式，例如 $TSLA，不要只写 TSLA。"
        "来源链接不要使用 [来源]、[链接]、[原文] 这类泛称；综合正文和交易信号表格中，"
        "链接文字必须显示来源账号，例如 [@screen_name](tweet_url)。"
        "同一账号多条来源可写 [@screen_name · 1](tweet_url)、[@screen_name · 2](tweet_url)。"
        "特朗普本人发言使用 [@realDonaldTrump 原文](tweet_url)；其他账号对特朗普事件的解读使用 [@screen_name](tweet_url)。"
        "最后必须写完 ## 投资理念 后自然结束，不要在前几节耗尽篇幅。"
    )
    parts = [intro]
    if trump_summary is not None:
        parts.append("### 特朗普相关数据")
        parts.append(json.dumps(trump_summary, ensure_ascii=False))
    parts.append("### 其他 KOL 数据")
    parts.append(json.dumps(layer2_results, ensure_ascii=False))
    text = "\n\n".join(parts)
    return [{"role": "user", "content": [{"type": "text", "text": text}]}]


def _fallback_layer1_markdown(
    layer2_results: list[dict[str, Any]],
    trump_summary: dict[str, Any] | None = None,
) -> str:
    bullets = _layer2_bullets_with_sources(layer2_results)
    tickers = sorted({ticker for bullet in bullets for ticker in bullet["tickers"]})
    active_kols = sorted(layer2_results, key=lambda item: item.get("tweet_count", 0), reverse=True)

    parts = [
        "> 提示：今日总摘要由本地兜底模板根据各 KOL 结构化摘要生成。",
        "",
        "## 特朗普相关",
        "",
        _render_trump_fallback(trump_summary),
        "",
        "## 今日关键词",
        "",
        f"- 重点标的：{', '.join(tickers[:20]) if tickers else '暂无明确股票代码。'}",
        "- 活跃账号："
        + "、".join(
            f"@{item.get('screen_name')}（{item.get('tweet_count', 0)} 条）"
            for item in active_kols[:8]
        ),
        "",
        "## 重要新闻",
        "",
        _render_fallback_bullets(bullets[:8]),
        "",
        "## 宏观判断",
        "",
        _render_fallback_bullets(_filter_macro_bullets(bullets)[:8], empty="暂无明确宏观判断。"),
        "",
        "## 产业/个股焦点",
        "",
        _render_ticker_focus(bullets),
        "",
        "## 交易信号",
        "",
        _render_trade_table(bullets),
        "",
        "## 投资理念",
        "",
        _render_core_views(layer2_results),
    ]
    return "\n".join(parts)


def _layer2_bullets_with_sources(layer2_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in layer2_results:
        handle = str(item.get("screen_name") or "")
        for bullet in item.get("bullets") or []:
            rows.append(
                {
                    "handle": handle,
                    "point": str(bullet.get("point") or "").strip(),
                    "tickers": [_format_markdown_ticker(t) for t in bullet.get("tickers") or []],
                    "tweet_url": bullet.get("tweet_url"),
                }
            )
    return rows


def _render_trump_fallback(trump_summary: dict[str, Any] | None) -> str:
    if trump_summary is None:
        return "- 今日未抓到 @realDonaldTrump 的可用摘要。"
    lines = [
        f"- @realDonaldTrump 今日 {trump_summary.get('tweet_count', 0)} 条：{trump_summary.get('core_view', '')}"
    ]
    for bullet in trump_summary.get("bullets") or []:
        lines.append(
            "- "
            + _bullet_text(
                {
                    "handle": "realDonaldTrump",
                    "point": str(bullet.get("point") or "").strip(),
                    "tickers": [_format_markdown_ticker(t) for t in bullet.get("tickers") or []],
                    "tweet_url": bullet.get("tweet_url"),
                },
                trump=True,
            )
        )
    return "\n".join(lines)


def _render_fallback_bullets(bullets: list[dict[str, Any]], empty: str = "暂无明确要点。") -> str:
    if not bullets:
        return f"- {empty}"
    return "\n".join(f"- {_bullet_text(bullet)}" for bullet in bullets)


def _render_ticker_focus(bullets: list[dict[str, Any]]) -> str:
    lines = []
    seen: set[tuple[str, str]] = set()
    for bullet in bullets:
        for ticker in bullet["tickers"]:
            key = (ticker, bullet["point"])
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- {ticker}：{_bullet_text(bullet, include_tickers=False)}")
            if len(lines) >= 12:
                return "\n".join(lines)
    return "\n".join(lines) if lines else "- 暂无明确个股焦点。"


def _render_trade_table(bullets: list[dict[str, Any]]) -> str:
    rows = ["| 标的 | 线索 | 来源 |", "|---|---|---|"]
    for bullet in bullets:
        if not bullet["tickers"]:
            continue
        rows.append(
            "| "
            + ", ".join(bullet["tickers"])
            + " | "
            + _escape_table_cell(bullet["point"])
            + " | "
            + _source_link(bullet)
            + " |"
        )
        if len(rows) >= 12:
            break
    if len(rows) == 2:
        return "暂无明确交易信号。"
    return "\n".join(rows)


def _render_core_views(layer2_results: list[dict[str, Any]]) -> str:
    lines = []
    for item in sorted(layer2_results, key=lambda row: row.get("tweet_count", 0), reverse=True):
        core_view = str(item.get("core_view") or "").strip()
        if not core_view or core_view == "summary_failed":
            continue
        lines.append(f"- @{item.get('screen_name')}：{core_view}")
        if len(lines) >= 8:
            break
    return "\n".join(lines) if lines else "- 暂无明确投资理念。"


def _filter_macro_bullets(bullets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"利率|通胀|CPI|PCE|非农|就业|失业|GDP|PMI|FOMC|Fed|美联储|收益率|美元|国债|宏观|关税|tariff|inflation|rates|yield",
        re.IGNORECASE,
    )
    return [bullet for bullet in bullets if pattern.search(bullet["point"])]


def _bullet_text(
    bullet: dict[str, Any],
    include_tickers: bool = True,
    trump: bool = False,
) -> str:
    tickers = [ticker for ticker in bullet["tickers"] if ticker]
    ticker_text = f"（{', '.join(tickers)}）" if include_tickers and tickers else ""
    return f"{bullet['point']}{ticker_text} {_source_link(bullet, trump=trump)}".strip()


def _source_link(bullet: dict[str, Any], trump: bool = False) -> str:
    handle = str(bullet.get("handle") or "").strip()
    url = bullet.get("tweet_url")
    if not handle:
        return ""
    label = f"@{handle} 原文" if trump or handle.lower() == "realdonaldtrump" else f"@{handle}"
    return f"[{label}]({url})" if url else label


def _format_markdown_ticker(ticker: object) -> str:
    code = str(ticker).strip().lstrip("$").upper()
    return f"${code}" if code else ""


def _escape_table_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _fallback_layer2_summary(kol: dict[str, Any], tweets: list[dict[str, Any]]) -> dict[str, Any]:
    bullets = []
    for tweet in tweets[:5]:
        text = _compact_tweet_text(tweet.get("text", ""))
        bullets.append(
            {
                "point": _truncate_text(text, 120) or "原推文本为空。",
                "tickers": _extract_tickers_from_text(text),
                "tweet_url": tweet.get("url"),
            }
        )
    core_view = _truncate_text(bullets[0]["point"], 30) if bullets else "summary_failed"
    return {
        "screen_name": kol["screen_name"],
        "tweet_count": len(tweets),
        "core_view": core_view,
        "bullets": bullets,
        "sentiment": "unclear",
        "input_tokens": 0,
        "output_tokens": 0,
    }


def _extract_tickers_from_text(text: str) -> list[str]:
    matches = re.findall(r"(?<![A-Za-z0-9_$])\$?([A-Z]{1,6})(?![A-Za-z0-9_])", text)
    return sorted({match.upper() for match in matches})


def _compact_tweet_text(text: object) -> str:
    return " ".join(str(text or "").split())


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


async def summarize_day(date: str) -> dict[str, Any]:
    tweets = db.tweets_on_date(date)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tweet in tweets:
        grouped[tweet["screen_name"]].append(tweet)

    layer2_results = []
    for screen_name, kol_tweets in grouped.items():
        kol = {"screen_name": screen_name, "id": kol_tweets[0]["kol_id"]}
        try:
            layer2_results.append(await summarize_one_kol(kol, kol_tweets, media_files=[]))
        except Exception as exc:
            logger.warning(
                "Layer2 Claude summary failed for @%s; using raw tweet fallback: %s",
                screen_name,
                exc,
            )
            layer2_results.append(_fallback_layer2_summary(kol, kol_tweets))

    trump_summary = next(
        (item for item in layer2_results if item["screen_name"].lower() == "realdonaldtrump"),
        None,
    )

    layer1_response = None
    try:
        layer1_response = await call_layer1_with_validation(
            messages=build_layer1_prompt(layer2_results, trump_summary=trump_summary),
            max_tokens=settings.ai.max_tokens_layer1,
        )
        summary_md = _prepare_layer1_markdown(_response_text(layer1_response))
        validation_error = _layer1_validation_error(
            summary_md,
            stop_reason=getattr(layer1_response, "stop_reason", None),
        )
        if validation_error:
            raise ValueError(validation_error)
    except Exception as exc:
        logger.warning("Layer1 Claude summary failed; using local fallback: %s", exc)
        summary_md = _fallback_layer1_markdown(layer2_results, trump_summary=trump_summary)
    input_tokens = sum(item.get("input_tokens", 0) for item in layer2_results)
    output_tokens = sum(item.get("output_tokens", 0) for item in layer2_results)
    usage = getattr(layer1_response, "usage", None) if layer1_response else None
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
