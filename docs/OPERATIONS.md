# 运维与运行说明

最后更新：2026-06-30

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
journalctl -u kol-monitor.service -n 100 --no-pager
journalctl -u kol-monitor.service -f
sudo systemctl restart kol-monitor.service
sudo systemctl stop kol-monitor.service
sudo systemctl start kol-monitor.service
sudo systemctl disable kol-monitor.service
```

如果当前环境没有 systemd，可以临时用：

```bash
nohup .venv/bin/kol-monitor daemon >> kol_monitor.log 2>&1 &
```

但长期建议 systemd，因为 nohup 进程更难管理重启、状态和日志。

当前这台机器已经按 systemd 持久化运行，服务文件位于 `/etc/systemd/system/kol-monitor.service`，`ExecStart` 指向仓库里的 `.venv/bin/kol-monitor daemon`。

如果只是临时验证某次改动，建议使用：

```bash
.venv/bin/kol-monitor run-once --no-publish
```

这会生成本地 `README.md` 和 `digests/`，但不会推 GitHub。验证结束如果不想保留这些产物，直接删除即可。

日报使用调度时刻之间的滚动 24 小时窗口。当前 `20:30` 调度下，日期为 `YYYY-MM-DD` 的日报覆盖“前一日 20:30（不含）到当日 20:30（含）”；这能确保晚间推文不会因 UTC/北京时间日期边界而永远漏出日报。

如果只是回查或修复某天日报质量，不要用 `regen-digest` 或 `run-once --no-publish`，因为它们会写发布文件。先用：

```bash
.venv/bin/kol-monitor quality-draft --date 2026-06-16
```

它只读取 DB 里已有 digest，并把草稿写到 `/tmp/kol-monitor-quality-drafts/2026-06-16/`：

- `draft.md`：推荐候选稿
- `cleaned_existing.md`：清理旧 Layer 1 后的版本
- `repaired_fallback.md`：从规范化 Layer 2 拼出的本地兜底稿
- `layer2_normalized.json`：过滤缺来源、外文残留、明显归属冲突后的 Layer 2
- `quality_report.json`：质量扫描结果

`quality-draft` 不写 DB、README、`digests/`，也不执行 git；确认 `quality_report.json` 通过后，再决定是否手工替换历史日报。

### GitHub 发布安全开关

公开 clone 后直接运行不会自动推送到原仓库。远端 push 需要同时满足两个条件：

1. `config/settings.yaml` 里 `publish.git_push=true`
2. 环境变量 `KOL_MONITOR_ALLOW_PUSH=true`

当前这台机器使用被 git 忽略的 `.env.local` 开启 `KOL_MONITOR_ALLOW_PUSH=true`，因此每日任务仍会更新 GitHub 主页。其他用户 fork/clone 后如果想发布到自己的仓库，需要先确认 `origin` 指向自己的 fork，再打开这个开关。

## 2. 每次为一个推特博主拉取多少条

配置在 `config/settings.yaml`：

- 首次接入：`fetcher.initial_pull_size = 20`
- 增量抓取第一轮：`20`
- 增量抓取后续轮次：`20 -> 40 -> 80 -> 100 -> 100`
- 单次请求上限：`fetcher.max_results_per_request = 100`
- 最大轮数：`fetcher.max_rounds = 5`

也就是说：

- 首次接入某个 KOL，只拉最新 20 条。
- 正常每天增量时，通常只调用一次，拉最新 20 条。
- 如果 20 条里没有遇到数据库锚点，会依次扩大到 40、80、100 条继续查重。
- 因为 6551 的 `twitter_user_tweets` 没有 cursor，超过 100 条的深度不能靠分页解决，只能靠 search 兜底。

## 3. 防漏拉机制

核心锚点是 `kols.last_seen_tweet_id`。

每个 KOL 的增量抓取流程：

1. 读取数据库里该 KOL 的 `last_seen_tweet_id`。
2. 调 6551 `twitter_user_tweets` 拉最新 20 条。
3. 把返回的 tweet_id 全部转成数值排序键比较，避免字符串比较出错；`truth_数字` 这类 ID 取数字后缀比较。
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
例外：如果 `twitter_user_tweets` 对某个真实账号返回 400（例如 `SV_Nomad` 的 `no tweet`），程序会改用 `twitter_search fromUser=<handle>` 兜底一次；这不是对同一 4xx 请求重试。

## 4. 归档策略

当前主方向是：

1. 首页只放“简要描述 + 今日完整报告入口 + 当日总结 + 最近 7 天入口”，让 README 成为清晰的入口页。
2. 完整日报放 `digests/YYYY/MM/DD.md`，首页只展示最有用的那一层。
3. 仍保留年月日分层，因为长期运行多年时目录不会过大，且 GitHub 目录页天然可浏览。
4. 最近 7 天保留一句话入口，方便一眼看出这个日报是否持续有价值。

建议后续优化：

1. 在 `digests` 表增加 `headline` 或 `one_line` 字段，用于 README 的最近 7 天 track record。
2. README 顶部保持“今日完整报告”链接，指向当天 `digests/YYYY/MM/DD.md`。
3. 历史归档保留最近 7 天日报链接 + 最近 12 个月目录链接。
4. 单篇 digest 继续保留“特朗普相关”独立分类，再展开其余 6 个内容维度和 KOL 明细。

## 5. 数据和归档放在哪里

- 原始和结构化数据：`kol_monitor.db`，只保存在本地，不推送 GitHub
- 图片和 GIF：`media/YYYY-MM-DD/<handle>/<tweet_id>_<idx>.<ext>`
- 每日完整总结：`digests/YYYY/MM/DD.md`，开启发布后会随发布流程推送 GitHub
- README 首页：仓库根目录 `README.md`，开启发布后会随发布流程推送 GitHub
- 每月索引：`digests/YYYY/MM/README.md`（由后续月度回顾功能生成），开启发布后会随发布流程推送 GitHub
- 盘前长推文：`premarket/` 已停用，日常 `run-once` / `regen-digest` 不再生成或提交该目录

这套结构的好处是：

1. 原始数据和总结分离，避免主页越跑越长。
2. 日报文件按年月日分层，方便 GitHub 目录页直接浏览。
3. 媒体不进 git，但本地路径稳定，后续可以重建摘要。

## 6. LLM 备用机制

Claude 调用按四层顺序尝试。环境变量名保留了历史命名，不等同于当前调用顺位：

1. 第一顺位备用：`ANTHROPIC_FALLBACK_API_KEY` + `ANTHROPIC_FALLBACK_BASE_URL`，模型同主配置
2. 第二顺位备用：`ANTHROPIC_FOURTH_API_KEY` + `ANTHROPIC_FOURTH_BASE_URL` + `ANTHROPIC_FOURTH_MODEL`
3. 第三顺位备用：`ANTHROPIC_THIRD_API_KEY` + `ANTHROPIC_THIRD_BASE_URL` + `ANTHROPIC_THIRD_MODEL`
4. 最后兜底主凭据：`ANTHROPIC_API_KEY` + `ANTHROPIC_BASE_URL`，模型用 `config/settings.yaml` 的 `ai.model`

四层 `BASE_URL` 都填服务根地址即可，不需要追加 `/v1`；代码仍兼容误填 `/v1` 的旧配置。只有上一层调用抛错或无结果时，才会尝试下一层。当前第二顺位模型名配置为 `claude-sonnet-4-6`，第三顺位模型名配置为 `anthropic/claude-sonnet-4.6`。

`ANTHROPIC_THIRD_*` 这组 Infron 后端当前作为第三顺位兜底，首选使用 `temperature=1` 且显式关闭 thinking。`ANTHROPIC_FALLBACK_*`、`ANTHROPIC_FOURTH_*` 和主凭据仍使用 `config/settings.yaml` 的 `ai.temperature`。这是为了兼容部分 Claude 4.6 后端对 extended thinking/adaptive mode 的限制：当模型启用或走 thinking/adaptive 模式时，非 `1` 的 temperature 会被拒绝。如果该后端仍返回 Bedrock 的 temperature/thinking 校验错误，程序会对同一后端再重试一次，这次不传 `temperature` 和 `thinking`，让 provider 使用默认普通模式；实测这种模式能返回正文，而 adaptive thinking 在低 `max_tokens` 下可能先消耗 thinking block，导致正文为空。

`ANTHROPIC_FOURTH_*` 这组 Packy 后端当前作为第二顺位备用，按普通 Claude 兼容后端处理，使用 `config/settings.yaml` 的 `ai.temperature`，不额外发送 `thinking` 参数。

如果 Layer 1 总摘要四层 LLM 都失败，程序会用已生成的各 KOL 结构化摘要拼出本地兜底日报，并在正文开头标注“本地兜底模板”。如果单个 KOL 的 Layer 2 摘要也失败，会从原始推文生成最小明细，避免当天 README 因单点 LLM 故障完全不更新。

日报发布前会做确定性质量清理：删除明显内部提示词/工作流污染、关键章节中没有 X 来源链接的要点、未链接来源标签、韩文/日文残留过多的行，以及“OpenAI 计划发布 Claude/Anthropic 模型”这类明显归属冲突。Layer 1 还会做中文标点归一化，并把非交易信号章节里的普通长段落整理为 markdown bullet；质量扫描会用 `long_plain_paragraph` warning 标记仍影响可读性的长段落。`quality_report.json` 会把这些问题按 error/warning 记录下来，方便回查是哪一层出错。

如果发布前清洗后的 Layer 1 仍触发 quality error，`publisher.write_outputs()` 会尝试用规范化后的 Layer 2 拼出本地有来源兜底摘要；该兜底摘要通过扫描时才替换发布正文。这个逻辑只保护读者可见输出，不会改写 DB 中的原始 `summary_md`。
