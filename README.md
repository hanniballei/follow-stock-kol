# 美股 X/KOL 每日摘要

这个仓库每天北京时间 20:30 自动抓取美股相关 X/KOL 的发言，整理成一页当天市场摘要。你可以先看今日完整报告，再看下面的当日总结和各 KOL 细节。

## 你会看到什么

- **当日总结**：今天最重要的市场共识、分歧和特朗普相关影响
- **最近 7 天**：快速回看过去一周的变化
- **KOL 明细**：每位账号当天具体说了什么
- **历史归档**：按月查看以前的日报

## 自己运行

- 默认不会执行远端 `git push`；只有 `publish.git_push=true` 且 `KOL_MONITOR_ALLOW_PUSH=true` 同时满足时才会推送。
- 如果你从 GitHub clone 后直接运行，它不会自动推送到原仓库；要发布到自己的仓库，请先把 `origin` 改成自己的 fork。
- 只想本地验证流程，可以运行 `kol-monitor run-once --no-publish`。

## 手动操作

```bash
kol-monitor run-once
kol-monitor run-once --no-publish
kol-monitor fetch-only
kol-monitor daemon
```

数据和媒体保留在本地，GitHub 主页只展示 Markdown 摘要。每天生成的新首页会在 20:30 后自动覆写这里。
