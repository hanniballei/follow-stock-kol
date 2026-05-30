# 运维与运行说明

最后更新：2026-05-30

## 1. 如何持久化运行

推荐使用 systemd，让程序在机器重启后自动恢复，并在异常退出后自动重启。

仓库里已提供模板：`deploy/kol-monitor.service`。内容如下：

```ini
[Unit]
Description=KOL Monitor Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/trading/us-stock/kol-monitor
EnvironmentFile=/root/trading/us-stock/kol-monitor/.env
ExecStart=/root/trading/us-stock/kol-monitor/.venv/bin/kol-monitor daemon
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

常用命令：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kol-monitor.service
sudo systemctl status kol-monitor.service
journalctl -u kol-monitor.service -f
```

如果当前环境没有 systemd，可以临时用：

```bash
nohup .venv/bin/kol-monitor daemon >> kol_monitor.log 2>&1 &
```

但长期建议 systemd，因为 nohup 进程更难管理重启、状态和日志。

## 2. 每次为一个推特博主拉取多少条

配置在 `config/settings.yaml`：

- 首次接入：`fetcher.initial_pull_size = 50`
- 增量抓取第一轮：`50`
- 增量抓取后续轮次：`50 -> 100 -> 100 -> 100 -> 100`
- 单次请求上限：`fetcher.max_results_per_request = 100`
- 最大轮数：`fetcher.max_rounds = 5`

也就是说：

- 首次接入某个 KOL，只拉最新 50 条。
- 正常每天增量时，通常只调用一次，拉最新 50 条。
- 如果 50 条里没有遇到数据库锚点，会扩大到 100 条继续查重。
- 因为 6551 的 `twitter_user_tweets` 没有 cursor，超过 100 条的深度不能靠分页解决，只能靠 search 兜底。

## 3. 防漏拉机制

核心锚点是 `kols.last_seen_tweet_id`。

每个 KOL 的增量抓取流程：

1. 读取数据库里该 KOL 的 `last_seen_tweet_id`。
2. 调 6551 `twitter_user_tweets` 拉最新 50 条。
3. 把返回的 tweet_id 全部转成 `int` 比较，避免字符串比较出错。
4. 如果这批推文里出现了上次锚点，或者最小 tweet_id 已经小于上次锚点，说明和历史数据发生重叠。
5. 只保留 `tweet_id > last_seen_tweet_id` 的推文入库。
6. 只有本轮确实有新推文时，才把 `last_seen_tweet_id` 更新为新推文里的最大 id。
7. 如果最多 5 轮仍找不到重叠，就把该 KOL 标记为 `incomplete = True`。

主抓取结束后会补救 `incomplete`：

1. 对 `incomplete=True` 的 KOL 调 `twitter_search`。
2. 查询条件使用 `fromUser=<handle>` 和 `sinceDate=<last_fetched_at - 1 day>`。
3. 补入遗漏推文。
4. 清除 `incomplete` 标记。

注意：4xx 不重试，避免 token 无效、欠费、权限问题时反复烧调用量。只对连接错误和读取超时重试。

## 4. 归档策略与 BuilderPulse 借鉴

参考仓库：`https://github.com/BuilderPulse/BuilderPulse/tree/main#chinese`

可学习的点：

1. 首页只放“今日摘要”和“最近 7 天记录”，完整日报放归档文件。这样 README 会更像一个入口页，而不是越来越长的全文集合。
2. 今日报告用醒目的按钮或链接跳到完整日报，用户一眼能找到当天全文。
3. 归档按语言和年份分区，例如 `zh/2026/2026-05-28.md`；文件名含完整日期，GitHub 列表里天然可排序。
4. 最近 7 天每一天都有一句话摘要，适合作为“track record”，让读者快速判断这个日报是否持续有价值。
5. 单篇日报内部层次很清楚：开头先给编辑判断，再给 Top signals、白话简报、机会拆解、行动建议。

本项目不完全照搬：

- 我们目前只有中文日报，不需要 `en/zh` 双语目录。
- 我们保留 `digests/YYYY/MM/DD.md` 的年月日分层，因为长期运行多年时目录不会过大。
- README 仍保留 KOL 列表和当日总结，但后续可以把首页改得更像 BuilderPulse：顶部只展示今日市场一句话、核心主题、完整日报链接和最近 7 天链接；各 KOL 明细继续放到完整 digest 文件里。

建议后续优化：

1. 在 `digests` 表增加 `headline` 或 `one_line` 字段，用于 README 的最近 7 天 track record。
2. README 顶部增加“今日完整报告”链接，指向当天 `digests/YYYY/MM/DD.md`。
3. 历史归档保留最近 7 天日报链接 + 最近 12 个月目录链接。
4. 单篇 digest 开头增加“编辑摘要 / 今日 Top 3 / 白话简报”，再展开 6 个内容维度和 KOL 明细。
