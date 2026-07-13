from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from kol_monitor import db
from kol_monitor.summarizer import (
    INTERNAL_ARTIFACT_MARKERS,
    MARKET_RELEVANT_CLAIM_TYPES,
    NON_CHINESE_RETRY_CHAR_LIMIT,
    REQUIRED_LAYER1_SECTIONS,
    SOURCE_REQUIRED_LAYER1_SECTIONS,
    TWEET_URL_RE,
    UNLINKED_SOURCE_LABEL_RE,
    ANONYMOUS_KOL_RE,
    _fallback_layer1_markdown,
    _is_empty_market_core_view,
    _is_layer1_placeholder,
    _is_markdown_table_data_row,
    _layer1_body_has_content,
    _layer1_headings,
    _layer1_section_requires_source,
    _line_has_suspicious_model_company_conflict,
    _non_chinese_letter_count,
    _normalize_layer1_heading,
    _normalize_layer2_result,
    _prepare_layer1_markdown,
)

DEFAULT_QUALITY_DRAFT_DIR = Path("/tmp/kol-monitor-quality-drafts")

# Raw layer2 JSON fields that should never survive into rendered markdown. A leak looks
# like a bare `"claim_type": "news",` / `"confidence": "medium)` line in the body.
_JSON_RESIDUE_RE = re.compile(r'"\s*(?:claim_type|confidence|tickers|tweet_url|core_view|sentiment)\s*"\s*:')
# A markdown link whose URL is corrupted by a stray quote or trailing JSON, e.g.
# `[原推](https://x.com/foo/status/123",` — the close paren never arrives on the URL.
_BROKEN_SOURCE_LINK_RE = re.compile(r'\]\(https?://[^)\s]*["\\][^)\s]*(?:,|$)')
_RAW_TCO_RE = re.compile(r"https?://t\.co/[A-Za-z0-9]+")
_MALFORMED_HORIZONTAL_RULE_RE = re.compile(r"^\s*[-*]\s+---\s*$")
_BOE_TICKER_CONFLATION_RE = re.compile(r"\$BOE\b.*京东方|京东方.*\$BOE\b", re.IGNORECASE)

# SpaceX's recurring ticker confusion. The project's canonical SpaceX ticker is $SPCX;
# $SPCE is Virgin Galactic and $SPACEX/$SPACE are invented. Flag (not auto-rewrite) when
# one of the wrong forms appears in SpaceX context, EXCEPT a legitimate disambiguation
# line that explicitly warns about the confusion (mentions $SPCX alongside a 误/混淆 word).
_WRONG_SPACEX_TICKER_RE = re.compile(r"\$(?:SPCE|SPACEX|SPACE)\b")
_SPACEX_CONTEXT_RE = re.compile(r"SpaceX|马斯克|星舰|星链|猎鹰|Starship|Starlink|Falcon", re.IGNORECASE)
_SPACEX_DISAMBIGUATION_RE = re.compile(r"误|混淆|当作|错把|搞混|区分|不是\s*\$SPCX")


def _line_has_suspicious_spacex_ticker_conflation(line: str) -> bool:
    if not _WRONG_SPACEX_TICKER_RE.search(line):
        return False
    # Legitimate when the line is explicitly disambiguating against $SPCX.
    if "$SPCX" in line and _SPACEX_DISAMBIGUATION_RE.search(line):
        return False
    return bool(_SPACEX_CONTEXT_RE.search(line) or "$SPCX" in line)


def write_quality_draft(
    date: str,
    output_dir: str | Path = DEFAULT_QUALITY_DRAFT_DIR,
) -> dict[str, Any]:
    digest = db.get_digest(date)
    if digest is None:
        raise RuntimeError(f"missing digest for {date}")

    raw_layer2 = _load_layer2_json(digest.get("layer2_json") or "[]")
    normalized_layer2 = [
        _normalize_layer2_result(dict(item)) for item in raw_layer2 if isinstance(item, dict)
    ]
    trump_summary = next(
        (
            item
            for item in normalized_layer2
            if str(item.get("screen_name") or "").lower() == "realdonaldtrump"
        ),
        None,
    )

    cleaned_existing = _prepare_layer1_markdown(digest.get("summary_md") or "")
    repaired_fallback = _prepare_layer1_markdown(
        _fallback_layer1_markdown(normalized_layer2, trump_summary=trump_summary)
    )

    reports = {
        "cleaned_existing": scan_summary_quality(cleaned_existing),
        "repaired_fallback": scan_summary_quality(repaired_fallback),
        "input_layer2": scan_layer2_quality(raw_layer2),
        "normalized_layer2": scan_layer2_quality(normalized_layer2),
    }
    draft_name, draft_markdown = _select_draft(
        cleaned_existing=cleaned_existing,
        repaired_fallback=repaired_fallback,
        reports=reports,
    )
    report = {
        "date": date,
        "status": "pass" if draft_name else "fail",
        "selected_draft": draft_name,
        "source_digest": {
            "kol_count": digest.get("kol_count"),
            "tweet_count": digest.get("tweet_count"),
            "model": digest.get("model"),
            "generated_at": digest.get("generated_at"),
        },
        "metrics": {
            "input_layer2_kols": len(raw_layer2),
            "normalized_layer2_kols": len(normalized_layer2),
            "input_layer2_bullets": _count_layer2_bullets(raw_layer2),
            "normalized_layer2_bullets": _count_layer2_bullets(normalized_layer2),
        },
        "reports": reports,
    }

    out_path = Path(output_dir) / date
    out_path.mkdir(parents=True, exist_ok=True)
    files = {
        "draft": out_path / "draft.md",
        "cleaned_existing": out_path / "cleaned_existing.md",
        "repaired_fallback": out_path / "repaired_fallback.md",
        "layer2_normalized": out_path / "layer2_normalized.json",
        "quality_report": out_path / "quality_report.json",
    }
    files["draft"].write_text(draft_markdown + "\n", encoding="utf-8")
    files["cleaned_existing"].write_text(cleaned_existing + "\n", encoding="utf-8")
    files["repaired_fallback"].write_text(repaired_fallback + "\n", encoding="utf-8")
    files["layer2_normalized"].write_text(
        json.dumps(normalized_layer2, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    files["quality_report"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "date": date,
        "output_dir": str(out_path),
        "files": {name: str(path) for name, path in files.items()},
        "report": report,
    }


def _select_draft(
    cleaned_existing: str,
    repaired_fallback: str,
    reports: dict[str, dict[str, Any]],
) -> tuple[str | None, str]:
    if _report_passed(reports["cleaned_existing"]):
        return "cleaned_existing", cleaned_existing
    if _report_passed(reports["repaired_fallback"]):
        return "repaired_fallback", repaired_fallback
    return None, cleaned_existing or repaired_fallback


def scan_summary_quality(markdown: str) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    current_section = ""
    source_urls: dict[str, list[int]] = {}
    content_fingerprints: dict[str, list[int]] = {}

    lines = markdown.splitlines()
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        heading = re.match(r"^\s{0,3}#{2,4}\s+(.+?)\s*$", line)
        if heading:
            current_section = _normalize_layer1_heading(heading.group(1))
            continue
        if not stripped:
            continue

        if _JSON_RESIDUE_RE.search(line):
            issues.append(
                _issue(
                    code="json_residue",
                    severity="error",
                    message="包含未渲染的原始 JSON 字段（疑似 layer2 序列化泄漏）",
                    line=line_no,
                    section=current_section,
                    text=line,
                )
            )

        if _BROKEN_SOURCE_LINK_RE.search(line):
            issues.append(
                _issue(
                    code="broken_source_link",
                    severity="error",
                    message="X 来源链接被破坏（URL 含引号/JSON 残留，无法点击）",
                    line=line_no,
                    section=current_section,
                    text=line,
                )
            )

        if _RAW_TCO_RE.search(line):
            issues.append(
                _issue(
                    code="raw_tco_url",
                    severity="warning",
                    message="包含未展开的 t.co 短链，可能遮蔽公司或文章名称",
                    line=line_no,
                    section=current_section,
                    text=line,
                )
            )

        if _MALFORMED_HORIZONTAL_RULE_RE.fullmatch(line):
            issues.append(
                _issue(
                    code="malformed_horizontal_rule",
                    severity="warning",
                    message="水平分隔线被渲染成空列表项",
                    line=line_no,
                    section=current_section,
                    text=line,
                )
            )

        if _BOE_TICKER_CONFLATION_RE.search(line):
            issues.append(
                _issue(
                    code="boe_ticker_conflation",
                    severity="warning",
                    message="疑似把京东方 A 写成美股 $BOE；京东方代码应为 $000725",
                    line=line_no,
                    section=current_section,
                    text=line,
                )
            )

        for marker in INTERNAL_ARTIFACT_MARKERS:
            if marker in line:
                issues.append(
                    _issue(
                        code="internal_artifact",
                        severity="error",
                        message=f"包含内部工作流/提示词痕迹：{marker}",
                        line=line_no,
                        section=current_section,
                        text=line,
                    )
                )
                break

        if UNLINKED_SOURCE_LABEL_RE.search(line):
            issues.append(
                _issue(
                    code="unlinked_source_label",
                    severity="error",
                    message="包含未链接的来源账号标签",
                    line=line_no,
                    section=current_section,
                    text=line,
                )
            )

        if ANONYMOUS_KOL_RE.search(line):
            issues.append(
                _issue(
                    code="anonymous_kol_reference",
                    severity="error",
                    message="包含匿名 KOL 表述，应使用可追溯的 @handle",
                    line=line_no,
                    section=current_section,
                    text=line,
                )
            )

        if _line_has_suspicious_spacex_ticker_conflation(line):
            issues.append(
                _issue(
                    code="spacex_ticker_conflation",
                    severity="warning",
                    message="疑似把 SpaceX 写成 $SPCE(维珍银河)/$SPACEX 等错误代码（SpaceX 应为 $SPCX）",
                    line=line_no,
                    section=current_section,
                    text=line,
                )
            )

        if _line_has_suspicious_model_company_conflict(line):
            issues.append(
                _issue(
                    code="suspicious_model_company_conflict",
                    severity="error",
                    message="疑似把 OpenAI 与 Claude/Anthropic 模型归属混写",
                    line=line_no,
                    section=current_section,
                    text=line,
                )
            )

        non_chinese_count = _non_chinese_letter_count(line)
        if non_chinese_count > NON_CHINESE_RETRY_CHAR_LIMIT:
            issues.append(
                _issue(
                    code="non_chinese_residue",
                    severity="error",
                    message=f"韩文/日文残留过多：{non_chinese_count} 个字符",
                    line=line_no,
                    section=current_section,
                    text=line,
                )
            )

        if (
            (stripped.startswith(("- ", "* ")) or _is_markdown_table_data_row(stripped))
            and _layer1_section_requires_source(current_section)
            and not _is_layer1_placeholder(stripped)
            and not TWEET_URL_RE.search(line)
        ):
            issues.append(
                _issue(
                    code="missing_source_link",
                    severity="error",
                    message="关键章节的 bullet/表格行缺少 X 来源链接",
                    line=line_no,
                    section=current_section,
                    text=line,
                )
            )

        if (
            current_section
            and not current_section.startswith("@")
            and not stripped.startswith(("- ", "* ", "|"))
            and _normalize_layer1_heading("交易信号") not in current_section
            and len(stripped) > 180
        ):
            issues.append(
                _issue(
                    code="long_plain_paragraph",
                    severity="warning",
                    message="Layer 1 章节包含过长普通段落，影响 Markdown 可读性",
                    line=line_no,
                    section=current_section,
                    text=line,
                )
            )

        urls = [match.group(0) for match in TWEET_URL_RE.finditer(line)]
        for url in urls:
            source_urls.setdefault(url, []).append(line_no)
        if urls:
            fingerprint = _content_fingerprint(line)
            if fingerprint:
                content_fingerprints.setdefault(fingerprint, []).append(line_no)

    _add_section_issues(markdown, issues)
    _add_duplicate_issues(source_urls, content_fingerprints, issues)
    return _quality_report(issues)


def scan_layer2_quality(layer2_results: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for item_index, item in enumerate(layer2_results):
        if not isinstance(item, dict):
            issues.append(
                _issue(
                    code="invalid_layer2_item",
                    severity="error",
                    message="Layer2 条目不是对象",
                    line=item_index + 1,
                    text=repr(item),
                )
            )
            continue
        handle = str(item.get("screen_name") or "")
        core_view = str(item.get("core_view") or "")
        if core_view and not _is_empty_market_core_view(core_view):
            _add_text_quality_issues(
                issues,
                text=core_view,
                code_prefix="layer2_core",
                label=f"@{handle} core_view",
                line=item_index + 1,
            )

        bullets = item.get("bullets") or []
        if bullets and not isinstance(bullets, list):
            issues.append(
                _issue(
                    code="invalid_layer2_bullets",
                    severity="error",
                    message=f"@{handle} bullets 不是数组",
                    line=item_index + 1,
                    text=repr(bullets),
                )
            )
            continue
        for bullet_index, bullet in enumerate(bullets):
            if not isinstance(bullet, dict):
                issues.append(
                    _issue(
                        code="invalid_layer2_bullet",
                        severity="error",
                        message=f"@{handle} bullet 不是对象",
                        line=item_index + 1,
                        text=repr(bullet),
                    )
                )
                continue
            point = str(bullet.get("point") or "")
            tweet_url = str(bullet.get("tweet_url") or "")
            if not point.strip():
                issues.append(
                    _issue(
                        code="layer2_empty_point",
                        severity="error",
                        message=f"@{handle} 第 {bullet_index + 1} 条 bullet 缺少 point",
                        line=item_index + 1,
                        text=repr(bullet),
                    )
                )
            else:
                _add_text_quality_issues(
                    issues,
                    text=point,
                    code_prefix="layer2_point",
                    label=f"@{handle} bullet {bullet_index + 1}",
                    line=item_index + 1,
                )
            if not TWEET_URL_RE.search(tweet_url):
                issues.append(
                    _issue(
                        code="layer2_missing_source",
                        severity="error",
                        message=f"@{handle} 第 {bullet_index + 1} 条 bullet 缺少有效 X 来源链接",
                        line=item_index + 1,
                        text=repr(bullet),
                    )
                )
            claim_type = str(bullet.get("claim_type") or "opinion").strip().lower()
            if claim_type not in MARKET_RELEVANT_CLAIM_TYPES | {"personal", "irrelevant"}:
                issues.append(
                    _issue(
                        code="layer2_invalid_claim_type",
                        severity="warning",
                        message=f"@{handle} 第 {bullet_index + 1} 条 claim_type 无效",
                        line=item_index + 1,
                        text=repr(bullet),
                    )
                )
    return _quality_report(issues)


def _load_layer2_json(text: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid layer2_json: {exc}") from exc
    if not isinstance(parsed, list):
        raise RuntimeError("layer2_json must be a list")
    return parsed


def _add_text_quality_issues(
    issues: list[dict[str, Any]],
    text: str,
    code_prefix: str,
    label: str,
    line: int,
) -> None:
    non_chinese_count = _non_chinese_letter_count(text)
    if non_chinese_count > NON_CHINESE_RETRY_CHAR_LIMIT:
        issues.append(
            _issue(
                code=f"{code_prefix}_non_chinese_residue",
                severity="error",
                message=f"{label} 韩文/日文残留过多：{non_chinese_count} 个字符",
                line=line,
                text=text,
            )
        )
    if _line_has_suspicious_model_company_conflict(text):
        issues.append(
            _issue(
                code=f"{code_prefix}_suspicious_model_company_conflict",
                severity="error",
                message=f"{label} 疑似把 OpenAI 与 Claude/Anthropic 模型归属混写",
                line=line,
                text=text,
            )
        )


def _add_section_issues(markdown: str, issues: list[dict[str, Any]]) -> None:
    headings = _layer1_headings(markdown)
    lines = markdown.splitlines()
    for section in REQUIRED_LAYER1_SECTIONS:
        normalized_section = _normalize_layer1_heading(section)
        matched = [
            (index, line_no, heading)
            for index, (line_no, heading) in enumerate(headings)
            if normalized_section in _normalize_layer1_heading(heading)
        ]
        if not matched:
            issues.append(
                _issue(
                    code="missing_required_section",
                    severity="error",
                    message=f"缺少必需章节：{section}",
                    section=normalized_section,
                )
            )
            continue
        index, line_no, _heading = matched[0]
        next_line = headings[index + 1][0] if index + 1 < len(headings) else len(lines)
        if not _layer1_body_has_content(lines[line_no + 1 : next_line]):
            issues.append(
                _issue(
                    code="empty_required_section",
                    severity="error",
                    message=f"必需章节为空：{section}",
                    line=line_no + 1,
                    section=normalized_section,
                )
            )


def _add_duplicate_issues(
    source_urls: dict[str, list[int]],
    content_fingerprints: dict[str, list[int]],
    issues: list[dict[str, Any]],
) -> None:
    for url, line_numbers in sorted(source_urls.items()):
        if len(line_numbers) < 3:
            continue
        issues.append(
            _issue(
                code="repeated_source_url",
                severity="warning",
                message=f"同一来源链接在摘要中重复 {len(line_numbers)} 次",
                line=line_numbers[0],
                text=url,
            )
        )
    for fingerprint, line_numbers in sorted(content_fingerprints.items()):
        if len(line_numbers) < 2:
            continue
        issues.append(
            _issue(
                code="duplicate_sourced_point",
                severity="warning",
                message=f"相同或高度相似的有来源要点重复 {len(line_numbers)} 次",
                line=line_numbers[0],
                text=fingerprint,
            )
        )


def _content_fingerprint(line: str) -> str:
    text = re.sub(r"\[[^\]]+\]\(https?://[^)\s]+\)", "", line)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"^[\-*]\s*", "", text.strip())
    text = re.sub(r"\s+", "", text)
    text = text.strip("|")
    if len(text) < 18:
        return ""
    return text[:120]


def _quality_report(issues: list[dict[str, Any]]) -> dict[str, Any]:
    severity_counts = Counter(issue["severity"] for issue in issues)
    code_counts = Counter(issue["code"] for issue in issues)
    return {
        "status": "pass" if not severity_counts.get("error", 0) else "fail",
        "issue_count": len(issues),
        "error_count": severity_counts.get("error", 0),
        "warning_count": severity_counts.get("warning", 0),
        "issue_counts_by_code": dict(sorted(code_counts.items())),
        "issues": issues,
    }


def _report_passed(report: dict[str, Any]) -> bool:
    return report.get("status") == "pass"


def _issue(
    code: str,
    severity: str,
    message: str,
    line: int | None = None,
    section: str | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "message": message,
    }
    if line is not None:
        row["line"] = line
    if section:
        row["section"] = section
    if text:
        row["text"] = _truncate_issue_text(text)
    return row


def _truncate_issue_text(text: str, max_chars: int = 180) -> str:
    compact = " ".join(str(text).split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "..."


def _count_layer2_bullets(layer2_results: list[dict[str, Any]]) -> int:
    total = 0
    for item in layer2_results:
        if isinstance(item, dict) and isinstance(item.get("bullets"), list):
            total += len(item["bullets"])
    return total
