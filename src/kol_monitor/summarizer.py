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
# Canonical status URL: handle + status + numeric id (optionally a `truth_` prefix for
# Truth Social-sourced realDonaldTrump posts). Used to sanitize tweet_url values that a
# malformed-JSON relaxed parse may have polluted with trailing fields (e.g. a missing
# closing quote causing the URL string to swallow `","claim_type":...`).
CANONICAL_TWEET_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:x|twitter)\.com/[A-Za-z0-9_]+/status/(?:truth_)?\d+"
)


def sanitize_tweet_url(raw: object) -> str:
    """Return the canonical X status URL embedded in `raw`, or "" if none is present.

    Guards the render boundary: a relaxed/garbled parse can leave trailing JSON or
    quotes glued onto a tweet_url; emitting that verbatim corrupts the markdown link and
    leaks internal fields. We extract only the well-formed status URL and drop the rest.
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    match = CANONICAL_TWEET_URL_RE.search(text)
    return match.group(0) if match else ""
UNLINKED_SOURCE_LABEL_RE = re.compile(r"\[@[^\]]+\](?!\()")
SUSPICIOUS_MODEL_COMPANY_RE = re.compile(
    r"OpenAI[^。！？\n]{0,40}(?:计划|将|将于|发布|推出|release|launch)"
    r"[^。！？\n]{0,40}(?:Claude|claude[-_.a-z0-9]*|Anthropic)",
    re.IGNORECASE,
)
INTERNAL_ARTIFACT_MARKERS = (
    "investigate_before_answering",
    "AGENTS.md",
    "工作原则",
    "失败两次",
    "诊断根因",
    "增量修补",
    "放弃需求",
    "系统原则",
)
# NOTE: markers are deliberately limited to UNAMBIGUOUS internal-workflow phrases. Bare
# subject-matter words were removed because US-tech-stock KOLs legitimately discuss AI
# tooling:
#   - "Codex" / "工作流" — OpenAI Codex / Claude Code product talk; "工作流"=workflow
#     (dropped 2026-06-17; e.g. 6/16 "与 Claude Code 和 Codex 竞争").
#   - "提示词" / "读代码" / "系统行为" — a KOL transcribing an All-In podcast about
#     Anthropic's prompt-retention policy legitimately says "用户提示词…重写提示词"
#     (6/14 @ArtofSpecuycky). As bare substrings these dropped real Layer-1 content and
#     failed the rendered-md scan on genuine market commentary.
# The remaining phrases (失败两次/诊断根因/增量修补/工作原则/系统原则/放弃需求/
# investigate_before_answering) are the ones that actually caught real pollution (6/05, 6/13)
# and have no legitimate KOL meaning.
SOURCE_REQUIRED_LAYER1_SECTIONS = (
    "重要新闻",
    "宏观判断",
    "产业/个股焦点",
    "交易信号",
    "投资理念",
)
MARKET_RELEVANT_CLAIM_TYPES = {
    "news",
    "opinion",
    "trade_signal",
    "market_data",
    "policy",
    "earnings",
}
NON_CHINESE_RETRY_CHAR_LIMIT = 8
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
    current_section = ""
    for line in markdown.splitlines():
        stripped = line.strip()
        heading = re.match(r"^\s{0,3}#{2,4}\s+(.+?)\s*$", line)
        if heading:
            current_section = _normalize_layer1_heading(heading.group(1))
            cleaned.append(line)
            continue
        is_bullet = stripped.startswith(("- ", "* "))
        is_table_data_row = _is_markdown_table_data_row(stripped)
        is_content_line = bool(stripped)
        if is_content_line and any(marker in line for marker in INTERNAL_ARTIFACT_MARKERS):
            continue
        if is_content_line and UNLINKED_SOURCE_LABEL_RE.search(line):
            continue
        if is_content_line and _line_has_suspicious_model_company_conflict(line):
            continue
        if is_content_line and _non_chinese_letter_count(line) > NON_CHINESE_RETRY_CHAR_LIMIT:
            continue
        if (
            (is_bullet or is_table_data_row)
            and _layer1_section_requires_source(current_section)
            and not _is_layer1_placeholder(stripped)
            and not TWEET_URL_RE.search(line)
        ):
            continue
        cleaned.append(line)
    return _fill_empty_layer1_sections("\n".join(cleaned))


def _layer1_section_requires_source(normalized_heading: str) -> bool:
    return any(
        _normalize_layer1_heading(section) in normalized_heading
        for section in SOURCE_REQUIRED_LAYER1_SECTIONS
    )


def _line_has_suspicious_model_company_conflict(line: str) -> bool:
    return bool(SUSPICIOUS_MODEL_COMPANY_RE.search(line))


def _is_markdown_table_data_row(stripped: str) -> bool:
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return False
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if not cells:
        return False
    if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells if cell):
        return False
    normalized_cells = {re.sub(r"\s+", "", cell) for cell in cells}
    header_cells = {"标的", "线索", "来源", "主题", "判断", "证据", "账号"}
    return not bool(normalized_cells & header_cells)


def _is_layer1_placeholder(stripped: str) -> bool:
    text = stripped.lstrip("-* ").strip().rstrip("。")
    return text in {
        "暂无高质量信号",
        "暂无有来源的高质量信号",
        "暂无明确要点",
        "暂无明确宏观判断",
        "暂无明确个股焦点",
        "暂无明确交易信号",
        "暂无明确投资理念",
    }


def _fill_empty_layer1_sections(markdown: str) -> str:
    lines = markdown.splitlines()
    headings = _layer1_headings(markdown)
    required = {
        _normalize_layer1_heading(section)
        for section in REQUIRED_LAYER1_SECTIONS
        if section not in SOURCE_REQUIRED_LAYER1_SECTIONS
    }
    source_required = {
        _normalize_layer1_heading(section) for section in SOURCE_REQUIRED_LAYER1_SECTIONS
    }
    for index in range(len(headings) - 1, -1, -1):
        line_no, heading = headings[index]
        normalized = _normalize_layer1_heading(heading)
        if not any(section in normalized for section in required | source_required):
            continue
        next_line = headings[index + 1][0] if index + 1 < len(headings) else len(lines)
        if _layer1_body_has_content(lines[line_no + 1 : next_line]):
            continue
        placeholder = (
            "- 暂无有来源的高质量信号。"
            if any(section in normalized for section in source_required)
            else "- 暂无高质量信号。"
        )
        lines[line_no + 1 : line_no + 1] = ["", placeholder, ""]
    return "\n".join(lines)


def _layer1_body_has_content(lines: list[str]) -> bool:
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue
        if _is_markdown_table_header_or_separator(stripped):
            continue
        return True
    return False


def _is_markdown_table_header_or_separator(stripped: str) -> bool:
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return False
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells if cell):
        return True
    normalized_cells = {re.sub(r"\s+", "", cell) for cell in cells}
    header_cells = {"标的", "线索", "来源", "主题", "判断", "证据", "账号"}
    return bool(normalized_cells & header_cells)


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
    texts = [str(getattr(block, "text", "") or "") for block in content]
    return "\n".join(text for text in texts if text)


async def _call_claude_backend(
    backend: ClaudeBackend,
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> Any:
    client = AsyncAnthropic(
        api_key=backend.api_key,
        base_url=_anthropic_sdk_base_url(backend.base_url),
    )
    try:
        return await client.messages.create(
            **_claude_request(
                backend=backend,
                messages=messages,
                max_tokens=max_tokens,
                temperature=backend.temperature,
                thinking=backend.thinking,
            )
        )
    except Exception as exc:
        if not _should_retry_third_temperature_thinking_error(backend, exc):
            raise
        logger.warning("Retrying third Claude backend with provider default temperature/thinking")
        return await client.messages.create(
            **_claude_request(
                backend=backend,
                messages=messages,
                max_tokens=max_tokens,
                temperature=None,
                thinking=None,
            )
        )


def _claude_request(
    backend: ClaudeBackend,
    messages: list[dict[str, Any]],
    max_tokens: int,
    temperature: float | None,
    thinking: dict[str, Any] | None,
) -> dict[str, Any]:
    request = {
        "model": backend.model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if temperature is not None:
        request["temperature"] = temperature
    if thinking is not None:
        request["thinking"] = thinking
    return request


def _should_retry_third_temperature_thinking_error(backend: ClaudeBackend, exc: Exception) -> bool:
    if backend.label != "third":
        return False
    message = str(exc).lower()
    return (
        "temperature" in message
        and "thinking" in message
        and ("adaptive" in message or "may only be set to 1" in message)
    )


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
    if parsed is not None and _layer2_needs_chinese_retry(parsed):
        chinese_retry = (
            "上次输出仍包含较多非中文内容。请把所有 core_view 和 bullets.point 翻译成简体中文，"
            "专有名词和股票代码可保留原文；仍然严格输出 JSON。\n\n"
            + _layer2_prompt(kol, tweets, bool(media_files))
        )
        parsed_retry, response_retry = await _call_layer2_until_parsed(
            [{"role": "user", "content": [{"type": "text", "text": chinese_retry}]}],
            [{"role": "user", "content": [{"type": "text", "text": chinese_retry}]}],
        )
        if parsed_retry is not None:
            parsed, response = parsed_retry, response_retry
    if parsed is None:
        parsed = {"core_view": "summary_failed", "bullets": [], "sentiment": "unclear"}
    # Targeted translation of any residual non-Chinese point/core_view BEFORE normalize.
    # normalize() drops residual-foreign bullets outright; translating them first keeps the
    # information (this is what was silently lost when whole Korean @blazingbees blocks
    # disappeared). A failed translation simply leaves the bullet for normalize to drop, so
    # the worst case is no worse than before.
    parsed = await _translate_residual_layer2(parsed)
    parsed = _normalize_layer2_result(parsed)

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


def _text_has_foreign_residue(text: str) -> bool:
    return _non_chinese_letter_count(str(text or "")) > NON_CHINESE_RETRY_CHAR_LIMIT


async def _translate_residual_layer2(parsed: dict[str, Any]) -> dict[str, Any]:
    """Translate only the residual non-Chinese strings in a parsed layer2 result.

    Collects core_view + each bullet.point that still carries Korean/Japanese residue,
    sends them as one batched JSON translation request, and writes back any item that
    comes back clean. Items that fail (LLM error, still-residual, or count mismatch) are
    left untouched so the downstream normalize() can drop them as before — no regression.
    """
    if not isinstance(parsed, dict):
        return parsed

    targets: list[tuple[str, int]] = []  # (kind, index): kind in {"core","bullet"}
    texts: list[str] = []
    core_view = str(parsed.get("core_view") or "")
    if _text_has_foreign_residue(core_view):
        targets.append(("core", -1))
        texts.append(core_view)
    bullets = parsed.get("bullets") or []
    for idx, bullet in enumerate(bullets):
        if not isinstance(bullet, dict):
            continue
        point = str(bullet.get("point") or "")
        if _text_has_foreign_residue(point):
            targets.append(("bullet", idx))
            texts.append(point)

    if not texts:
        return parsed

    translations = await _translate_texts_to_chinese(texts)
    if translations is None or len(translations) != len(texts):
        logger.warning(
            "residual translation skipped for @%s (got %s items for %d targets)",
            parsed.get("screen_name", "?"),
            None if translations is None else len(translations),
            len(texts),
        )
        return parsed

    for (kind, idx), original, translated in zip(targets, texts, translations):
        candidate = str(translated or "").strip()
        # Only accept a translation that actually removed the residue and is non-empty.
        if not candidate or _text_has_foreign_residue(candidate):
            continue
        if kind == "core":
            parsed["core_view"] = candidate
        else:
            bullets[idx]["point"] = candidate
    return parsed


async def _translate_texts_to_chinese(texts: list[str]) -> list[str] | None:
    payload = json.dumps(texts, ensure_ascii=False)
    prompt = (
        "把下面 JSON 数组里的每个字符串翻译成简体中文，专有名词和 $股票代码 保留原文，"
        "公司名用中文常用译名（如 Rheinmetall→莱茵金属）。"
        "保持数组长度和顺序完全一致，只输出 JSON 字符串数组，不要解释、不要 markdown。\n\n"
        f"{payload}"
    )
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    try:
        response = await call_claude_with_retry(
            messages=messages, max_tokens=settings.ai.max_tokens_layer2
        )
    except Exception as exc:
        logger.warning("residual translation request failed: %s", exc)
        return None
    raw = _response_text(response)
    parsed = _parse_string_array(raw)
    if parsed is None:
        logger.warning("residual translation returned non-array output")
    return parsed


def _parse_string_array(text: str) -> list[str] | None:
    candidates = [text]
    match = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if match:
        candidates.append(match.group(1))
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except Exception:
            continue
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return value
    return None


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
        parsed = parse_layer2(_response_text(response))
        if parsed is not None:
            return parsed, response
        response = await _client.messages.create(
            model=settings.ai.model,
            max_tokens=settings.ai.max_tokens_layer2,
            temperature=settings.ai.temperature,
            messages=retry_messages,
        )
        return parse_layer2(_response_text(response)), response

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
            parsed = parse_layer2(_response_text(response))
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
        f"请总结美股 KOL @{kol['screen_name']} 当日推文。你是在做“社媒观点摘要”，不是事实核验新闻稿。",
        "所有 core_view 和 bullets.point 必须使用简体中文；非中文推文要翻译，专有名词和股票代码可保留原文。",
        "只基于给定推文，不得补充外部背景、不得把传言或观点改写成已确认事实。",
        "如果推文是在猜测、传言、喊单或表达观点，point 必须包含“作者认为/称/转述/推测”等归因词。",
        "归因纪律：某条 bullet 里写的每个数字/指标/事件（如价格、RSI、财报数据、目标价）只能来自该条 point 真正引用的那一条推文；"
        "tickers 字段只填该 point 文本里确实出现、且推文确有提及的股票代码，不要把推文里没提到的股票塞进 tickers；"
        "尤其禁止把 A 股票的数据安到 B 股票上（例如某推说 $SNDK 的 RSI，就不能写成 $MU 的 RSI）。",
        "专有名词翻译要准确：公司名先用中文常用译名再视情况附原文，例如 Rheinmetall→莱茵金属、Virgin Galactic→维珍银河（$SPCE）；不确定就保留原文，不要音译生造。",
        "SpaceX 的展示代码统一写 $SPCX；不要写成 $SPACEX/$SPACE，也不要和维珍银河 $SPCE 混淆。",
        "无市场相关内容时，bullets 输出 []，core_view 写“无市场相关内容”，sentiment 写 unclear。",
        "涉及具体股票代码时，展示文本统一使用 $股票代码 格式，例如 $NVDA；tickers 字段仍只填不带 $ 的代码。",
        "每条 bullet 必须保留对应 tweet_url；无法关联原推的内容不要写入 bullets。",
        "claim_type 只能填 news|opinion|trade_signal|market_data|policy|earnings|personal|irrelevant；confidence 只能填 high|medium|low。",
        "输出严格 JSON，格式：",
        '{"core_view":"≤30字一句话","bullets":[{"point":"作者认为 $NVDA ...","tickers":["NVDA"],"tweet_url":"https://x.com/...","claim_type":"opinion","confidence":"medium"}],"sentiment":"bullish|bearish|neutral|unclear"}',
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
        "这是社媒观点摘要，不是事实核验新闻稿；不要把 KOL 观点、传言或交易喊单改写成已确认事实。"
        "必须按顺序完整输出且只输出以下七个二级标题："
        "## 特朗普相关、## 今日关键词、## 重要新闻、## 宏观判断、"
        "## 产业/个股焦点、## 交易信号、## 投资理念。"
        "不要遗漏任何标题；如果某节信息不足，写一条“暂无高质量信号。”，也必须保留该标题。"
        "先合并重复信息，再写结论，避免逐条复述同一账号的相似推文。"
        "除非输入明确来自官方公告或客观市场数据，否则使用“某 KOL 称/认为/转述/推测”等归因表达。"
        "如果信息互相冲突，保留“分歧”表述，不要强行合并成单一事实。"
        "归因纪律（重要）：合并多个 KOL 的要点时，每个数字/指标/事件只能挂到它在源 JSON 里真正对应的那个股票代码上；"
        "不要把某条要点里 A 股票的数据（价格、RSI、目标价、财报数字等）写成 B 股票的数据。"
        "如果不确定某个数字属于哪个 ticker，宁可不写该数字，也不要张冠李戴。"
        "把 SpaceX 统一写 $SPCX，不要写 $SPACEX/$SPACE，也不要与维珍银河 $SPCE 混淆；公司名沿用源 JSON 里的中文译名，不要另行音译生造。"
        "总长度控制在 1800-2600 汉字，每条 bullet 尽量不超过 70 汉字，"
        "交易信号表格的“线索”列尽量不超过 30 汉字；严禁扩写背景知识。"
        "篇幅控制：特朗普相关 2-4 条；今日关键词用 6-8 个普通 bullet，不要表格；"
        "重要新闻 4-6 条；宏观判断 3-5 条；产业/个股焦点 5-8 条；"
        "交易信号最多 6 行 markdown 表格；投资理念 3-5 条。"
        "重要新闻、宏观判断、产业/个股焦点、交易信号、投资理念中的每条 bullet 或表格行必须至少包含一个 X 来源链接；没有来源的内容不要写。"
        "投资理念只能来自 KOL 明确表达的投资原则，禁止写总结过程、工程方法、提示词规则、系统原则。"
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


def build_premarket_prompt(date: str, layer1_md: str) -> list[dict[str, Any]]:
    intro = (
        "你是美股盘前简报编辑。基于下面这份『今日美股 KOL 综合摘要』，"
        "写一篇可直接复制发布到 X(推特)的中文长推文《美股盘前快报》。要求：\n"
        "1) 开头一句高信息密度的钩子，点明今日最重要的主线或市场情绪。\n"
        "2) 随后用 4-7 条要点，覆盖：宏观/政策、热门板块与个股、值得注意的交易信号或多空分歧；"
        "每条简洁有力，一到两句话。\n"
        "3) 提及具体股票统一用 $代码 格式(如 $NVDA)；可点名关键 KOL(如 @handle)以增加可信度，但不要堆链接。\n"
        "4) 口语化、有节奏感，像一条高质量财经博主的盘前推文；不要用 markdown 标题(#)、不要表格、不要分隔线、不要代码块。\n"
        "5) 只能基于给定摘要，不补充外部事实、不编造数字；KOL 观点用『某某认为/称/预计』等归因表述。\n"
        "6) 不要把 A 股/港股/加密等非美股代码写成美股；保持摘要里原有的代码与公司名，不要臆造或音译生造。\n"
        "7) 结尾单独一行轻量风险提示，例如：以上为 KOL 观点汇总，非投资建议。\n"
        "8) 总长度 500-1000 汉字，适合 X 长推文。直接输出推文正文，不要任何前后说明或标题行。\n"
        f"日期：{date}\n今日综合摘要：\n"
    )
    text = intro + (layer1_md or "")
    return [{"role": "user", "content": [{"type": "text", "text": text}]}]


async def generate_premarket_tweet(date: str) -> str:
    """Generate a ready-to-post Chinese pre-market long tweet from the day's digest.

    Reads the stored layer1 summary (cleaned), asks the model to condense it into a
    single copy-paste-ready X post. Returns the post text; raises on total LLM failure
    so the caller can treat premarket as best-effort and skip it without breaking the
    digest publish."""
    digest = db.get_digest(date)
    if digest is None:
        raise RuntimeError(f"missing digest for {date}")
    layer1_md = _prepare_layer1_markdown(digest.get("summary_md") or "")
    if not layer1_md.strip():
        raise RuntimeError(f"empty layer1 summary for {date}; cannot build premarket tweet")
    response = await call_claude_with_retry(
        messages=build_premarket_prompt(date, layer1_md),
        max_tokens=settings.ai.max_tokens_layer1,
    )
    text = _response_text(response).strip()
    if not text:
        raise RuntimeError(f"premarket generation returned empty text for {date}")
    return text


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
            claim_type = str(bullet.get("claim_type") or "opinion").strip().lower()
            if claim_type not in MARKET_RELEVANT_CLAIM_TYPES:
                continue
            if not bullet.get("tweet_url"):
                continue
            point = str(bullet.get("point") or "").strip()
            if not point:
                continue
            if _non_chinese_letter_count(point) > NON_CHINESE_RETRY_CHAR_LIMIT:
                continue
            if _line_has_suspicious_model_company_conflict(point):
                continue
            rows.append(
                {
                    "handle": handle,
                    "point": point,
                    "tickers": [_format_markdown_ticker(t) for t in bullet.get("tickers") or []],
                    "tweet_url": bullet.get("tweet_url"),
                    "claim_type": claim_type,
                    "confidence": str(bullet.get("confidence") or "medium").strip().lower(),
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
        if not bullet.get("tweet_url"):
            continue
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
        if not core_view or _is_empty_market_core_view(core_view):
            continue
        if _non_chinese_letter_count(core_view) > NON_CHINESE_RETRY_CHAR_LIMIT:
            continue
        if _line_has_suspicious_model_company_conflict(core_view):
            continue
        source = _first_bullet_source(item)
        if not source:
            continue
        lines.append(f"- @{item.get('screen_name')}：{core_view} {source}")
        if len(lines) >= 8:
            break
    return "\n".join(lines) if lines else "- 暂无明确投资理念。"


def _first_bullet_source(item: dict[str, Any]) -> str:
    for bullet in item.get("bullets") or []:
        url = sanitize_tweet_url(bullet.get("tweet_url"))
        if url:
            handle = item.get("screen_name")
            return f"[@{handle}]({url})"
    return ""


def _is_empty_market_core_view(core_view: str) -> bool:
    normalized = core_view.strip().lower()
    return normalized in {"无市场相关内容", "暂无要点", "summary_failed", "no market relevant content"}


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
    url = sanitize_tweet_url(bullet.get("tweet_url"))
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
                "claim_type": "opinion",
                "confidence": "low",
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


def _normalize_layer2_result(parsed: dict[str, Any]) -> dict[str, Any]:
    parsed["core_view"] = str(parsed.get("core_view") or "").strip()
    parsed["sentiment"] = str(parsed.get("sentiment") or "unclear").strip().lower()
    if parsed["sentiment"] not in {"bullish", "bearish", "neutral", "unclear"}:
        parsed["sentiment"] = "unclear"
    normalized_bullets = []
    for bullet in parsed.get("bullets") or []:
        if not isinstance(bullet, dict):
            continue
        point = str(bullet.get("point") or "").strip()
        tweet_url = sanitize_tweet_url(bullet.get("tweet_url"))
        if not point or not tweet_url:
            continue
        if _non_chinese_letter_count(point) > NON_CHINESE_RETRY_CHAR_LIMIT:
            continue
        if _line_has_suspicious_model_company_conflict(point):
            continue
        claim_type = str(bullet.get("claim_type") or "opinion").strip().lower()
        if claim_type not in MARKET_RELEVANT_CLAIM_TYPES | {"personal", "irrelevant"}:
            claim_type = "opinion"
        confidence = str(bullet.get("confidence") or "medium").strip().lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"
        normalized_bullets.append(
            {
                "point": point,
                "tickers": [
                    str(ticker).strip().lstrip("$").upper()
                    for ticker in bullet.get("tickers") or []
                    if str(ticker).strip()
                ],
                "tweet_url": tweet_url,
                "claim_type": claim_type,
                "confidence": confidence,
            }
        )
    parsed["bullets"] = normalized_bullets
    if (
        _non_chinese_letter_count(parsed["core_view"]) > NON_CHINESE_RETRY_CHAR_LIMIT
        or _line_has_suspicious_model_company_conflict(parsed["core_view"])
    ):
        parsed["core_view"] = (
            _truncate_text(normalized_bullets[0]["point"], 30)
            if normalized_bullets
            else "无市场相关内容"
        )
    return parsed


def _layer2_needs_chinese_retry(parsed: dict[str, Any]) -> bool:
    text = " ".join(
        [str(parsed.get("core_view") or "")]
        + [
            str(bullet.get("point") or "")
            for bullet in parsed.get("bullets") or []
            if isinstance(bullet, dict)
        ]
    )
    return _non_chinese_letter_count(text) > NON_CHINESE_RETRY_CHAR_LIMIT


def _non_chinese_letter_count(text: str) -> int:
    count = 0
    for char in text:
        if "\uac00" <= char <= "\ud7a3":
            count += 1
        elif "\u3040" <= char <= "\u30ff":
            count += 1
    return count


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
