# 美股 KOL 每日监控

这个仓库会自动抓取美股相关 X/KOL 的推文，生成当日总结，并把结果发布到仓库主页。

当前首页由 `kol-monitor` 自动维护：

- 每天北京时间 20:30 自动生成一版新的 `README.md`
- 当日完整总结会同步到 `digests/YYYY/MM/DD.md`
- 数据库和媒体文件保留在本地，不推送 GitHub

手动操作命令：

```bash
kol-monitor run-once
kol-monitor run-once --no-publish
kol-monitor fetch-only
kol-monitor daemon
```

最近一次自动总结完成后，这个文件会被当天的主页摘要覆写。
