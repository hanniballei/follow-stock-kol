from __future__ import annotations

from pathlib import Path
import subprocess

from kol_monitor import publisher
from kol_monitor.publisher import render_digest_md, render_readme


def test_render_readme_contains_required_sections():
    md = render_readme(
        date="2026-05-29",
        layer1_md="### 今日关键词\n通胀降温",
        layer2_kols=[
            {
                "screen_name": "qinbafrank",
                "tweet_count": 3,
                "core_view": "科技股估值进入消化期",
                "bullets": [
                    {
                        "point": "看好半导体设备",
                        "tickers": ["AMAT"],
                        "tweet_url": "https://x.com/qinbafrank/status/1",
                    }
                ],
                "sentiment": "bullish",
            }
        ],
        kol_list=["qinbafrank", "NickTimiraos"],
        recent_digests=[("2026-05-29", "digests/2026/05/29.md")],
        history_dirs=[("2026-05", "digests/2026/05/"), ("2026-04", "digests/2026/04/")],
    )

    assert md.startswith("# 美股KOL每日摘要")
    assert "X 上 2 位美股相关 KOL 的发言" in md
    assert "美股 X/KOL 每日摘要" not in md
    assert "## 你会看到什么" in md
    assert "## 自己运行" in md
    assert "KOL_MONITOR_ALLOW_PUSH=true" in md
    assert "## 监控的 KOL" in md
    assert "[阅读今日完整报告](digests/2026/05/29.md)" in md
    assert "## 最近 7 天" in md
    assert "这个仓库每天北京时间 20:00 自动抓取" in md
    assert md.index("### 今日关键词") < md.index("## 监控的 KOL")
    assert "[@qinbafrank](https://x.com/qinbafrank)" in md
    assert "<details>" in md
    assert "## 历史归档" in md
    assert "https://x.com/qinbafrank/status/1" in md
    assert "2026-05-29" in md
    assert "$AMAT" in md


def test_digest_md_no_collapse():
    md = render_digest_md(
        date="2026-05-29",
        layer1_md="### 今日关键词\n...",
        layer2_kols=[],
    )

    assert "<details>" not in md
    assert "2026-05-29" in md


def test_git_publish_does_not_push_without_explicit_allow(monkeypatch, tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# test\n", encoding="utf-8")
    calls = []
    published = []

    monkeypatch.setattr(publisher.settings, "project_root", tmp_path)
    monkeypatch.setattr(publisher.settings.publish, "git_push", True)
    monkeypatch.setattr(publisher.settings, "allow_git_push", False, raising=False)
    monkeypatch.setattr(
        publisher.subprocess,
        "run",
        lambda cmd, **_kwargs: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0),
    )
    monkeypatch.setattr(publisher.db, "mark_digest_published", published.append)

    assert publisher.git_publish("2026-05-30", [readme]) is True

    assert ["git", "add", "README.md"] in calls
    assert ["git", "commit", "-m", "digest: 2026-05-30"] in calls
    assert ["git", "push", "origin", "main"] not in calls
    assert published == ["2026-05-30"]


def test_git_publish_pushes_when_explicitly_allowed(monkeypatch, tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# test\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(publisher.settings, "project_root", tmp_path)
    monkeypatch.setattr(publisher.settings.publish, "git_push", True)
    monkeypatch.setattr(publisher.settings, "allow_git_push", True, raising=False)
    monkeypatch.setattr(
        publisher.subprocess,
        "run",
        lambda cmd, **_kwargs: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0),
    )
    monkeypatch.setattr(publisher.db, "mark_digest_published", lambda _date: None)

    publisher.git_publish("2026-05-30", [readme])

    assert ["git", "push", "origin", "main"] in calls


def test_git_publish_retries_transient_push_failure(monkeypatch, tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# test\n", encoding="utf-8")
    calls = []
    published = []
    push_attempts = {"count": 0}

    monkeypatch.setattr(publisher.settings, "project_root", tmp_path)
    monkeypatch.setattr(publisher.settings.publish, "git_push", True)
    monkeypatch.setattr(publisher.settings.publish, "push_retry", 3)
    monkeypatch.setattr(publisher.settings, "allow_git_push", True, raising=False)
    monkeypatch.setattr(publisher.time, "sleep", lambda _seconds: None)

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        if cmd == ["git", "push", "origin", "main"]:
            push_attempts["count"] += 1
            if push_attempts["count"] == 1:
                raise subprocess.CalledProcessError(128, cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(publisher.subprocess, "run", fake_run)
    monkeypatch.setattr(publisher.db, "mark_digest_published", published.append)

    assert publisher.git_publish("2026-05-30", [readme]) is True

    assert calls.count(["git", "push", "origin", "main"]) == 2
    assert published == ["2026-05-30"]


def test_git_publish_sets_home_for_systemd_environment(monkeypatch, tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# test\n", encoding="utf-8")
    (tmp_path / ".git-data").mkdir()
    child_envs = []

    monkeypatch.setattr(publisher.settings, "project_root", tmp_path)
    monkeypatch.setattr(publisher.settings.publish, "git_push", True)
    monkeypatch.setattr(publisher.settings, "allow_git_push", True, raising=False)
    monkeypatch.delenv("HOME", raising=False)

    def fake_run(cmd, **kwargs):
        child_envs.append(kwargs["env"])
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(publisher.subprocess, "run", fake_run)
    monkeypatch.setattr(publisher.db, "mark_digest_published", lambda _date: None)

    publisher.git_publish("2026-05-30", [readme])

    assert child_envs
    assert all(env["HOME"] == str(Path.home()) for env in child_envs)
