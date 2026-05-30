# 美股KOL每日摘要

最后更新：2026-05-30

这个仓库每天北京时间 20:30 自动抓取 X 上 55 位美股相关 KOL 的发言，整理成一页当天市场摘要。你可以先看今日完整报告，再看下面的当日总结和各 KOL 细节。

[阅读今日完整报告](digests/2026/05/30.md)

## 你会看到什么

- **当日总结**：今天最重要的市场共识、分歧和特朗普相关影响
- **最近 7 天**：快速回看过去一周的变化
- **KOL 明细**：每位账号当天具体说了什么
- **历史归档**：按月查看以前的日报

## 自己运行

- 默认不会执行远端 `git push`；只有 `publish.git_push=true` 且 `KOL_MONITOR_ALLOW_PUSH=true` 同时满足时才会推送。
- 如果你从 GitHub clone 后直接运行，它不会自动推送到原仓库；要发布到自己的仓库，请先把 `origin` 改成自己的 fork。
- 只想本地验证流程，可以运行 `kol-monitor run-once --no-publish`。

## 2026-05-30 当日总结

# 美股 KOL 每日情报汇总

---

## 一、特朗普相关

> ⚠️ 本日 @realDonaldTrump 账号数据解析失败（summary_failed），无法直接提取当日发言内容。以下为基于其他 KOL 引用及市场背景的推测性分析，推测依据已注明。

**推测线索一：$TKO 被点名**

KOL @hanking66 明确提及"川普买入 $TKO，号召跟随黄毛操作冲入"。推测依据：特朗普本人或其关联账号在社交媒体上公开表态持有或看好 $TKO（TKO Group Holdings，旗下拥有 WWE 和 UFC），此类总统级背书历史上会短期推动相关标的异动。[$TKO 相关推文](https://x.com/hanking66/status/2060561816359752069)

**推测线索二：SpaceX 上市时间窗口**

多位 KOL（@WallStreet0Name、@ArtofSpecuycky）提及 SpaceX 预计 6 月 12 日上市，合约报价 190+。特朗普与马斯克的政治关系密切，若特朗普当日发言涉及太空政策、星链或马斯克，可能进一步催化 $SPCX 相关预期。推测依据：特朗普政府持续推进商业航天政策，任何正面表态均可能提振市场情绪。[$SPCX 相关推文](https://x.com/WallStreet0Name/status/2060607453813981212)

**推测线索三：关税与中国竞争叙事**

@raycat2021 提及美欧担忧中国企业将内卷式竞争输出海外，冲击本土企业并压制薪资。若特朗普当日发言涉及对华关税或贸易限制，受益标的可能包括本土制造业、半导体设备（如 $AMAT、$LRCX）及国防板块；受损方向为依赖中国供应链的消费电子与零售。推测依据：特朗普近期持续在关税议题上发声，中国竞争叙事是其核心政治话语。[$raycat2021 相关推文](https://x.com/raycat2021/status/2060715968410877977)

---

## 二、今日关键词

- **Agentic AI**：驱动通用服务器与端侧 PC 需求双升
- **CPO / 光子学超级周期**：富士康 Q3 启动，2026 年爆发
- **MLCC 供需错配**：AI 服务器端 80%+ CAGR，交货期超 20 周
- **$DELL 财报超预期**：AI 服务器季收入同比 +757%，盘后暴涨 33%
- **软件板块轮动**：$IGV 单日 +6.25%，$NOW +14%，$OKTA +28%
- **$NVDA 进军 PC 市场**：ARM 架构剑指 2000 亿美元笔记本市场
- **SpaceX 上市倒计时**：6 月 12 日，合约报价 190+
- **K 型经济分化**：股市新高 vs 消费者信心历史低点

---

## 三、重要新闻

- **$DELL 财报超预期**：AI 服务器季收入 161 亿美元，同比 +757%，盘后暴涨近 33%，Agentic AI 驱动通用服务器高速增长。[$DELL 相关推文](https://x.com/ArtofSpecuycky/status/2060571365561049121)

- **$NVDA MSCI 调仓砸盘**：尾盘因 MSCI 半年度机械性调仓，20 分钟内市值蒸发超 1400 亿美元；同时 MSCI 加仓博通、微软、闪迪、美光，减持 $NVDA 和 $INTC。[$NVDA 相关推文](https://x.com/hanking66/status/2060549567146594319)

- **$MSFT 将发布新软件**：支持 AI Agent 在 Windows PC 本地执行任务，利好端侧 AI 落地，Computex 前夕消息密集。[$MSFT 相关推文](https://x.com/jukan05/status/2060709797830566262)

- **三星为 OpenAI 开发定制 SoC 合作陷入停滞**：韩媒报道，多位 KOL 转发确认。[$QCOM 相关推文](https://x.com/zephyr_z9/status/2060646781684416545)

- **光子产业链 ETF $FOTO 正式上市**：主动管理型，覆盖光通信、激光器、硅光、光电子器件，$LITE 占首位持仓 13.1%。[$FOTO 相关推文](https://x.com/tychozzz/status/2060697443650683071)

- **摩根士丹利研报**：$NVDA 从 GB300 升级至 VR200 后，单台 NVL72 机架成本从 399 万美元升至 780 万美元（+95%），Memory 部件涨幅最高（+435%）。[$NVDA 相关推文](https://x.com/SpermCapital/status/2060515250060087675)

- **字节跳动 AI4S 团队重组**：同步推进 $QCOM ASIC 大规模定制芯片及 ARM/RISC-V 双轨 CPU，科学计算被中国大厂列为战略 AI 方向。[$QCOM 相关推文](https://x.com/zephyr_z9/status/2060518857606062504)

- **5 月收官九连阳**：$SPY 守住 750 关键支撑，标普 5 月涨 5%，纳指涨超 8%。[$SPY 相关推文](https://x.com/ArtofSpecuycky/status/2060571365561049121)

---

## 四、宏观判断

**多头观点（主流）**

- 牛市尚未结束，5 月九连阳收官，$SPY 750 是下周多空分水岭，跌破 740 才触发多头连锁止损。[@ArtofSpecuycky](https://x.com/ArtofSpecuycky/status/2060571365561049121)
- 软件板块轮动已实质落地，AI 叙事证伪空头踩踏，$IGV 重回 200 日均线。[@ArtofSpecuycky](https://x.com/ArtofSpecuycky/status/2060571365561049121)
- 日本资产处于全球折价率最高水平，看好日本牛市。[@cnfinancewatch](https://x.com/cnfinancewatch/status/2060666699620462940)
- IPO 首日平均涨 23%，但此后三年跑输市场 25%，提示 IPO 热潮中的长期风险。[@raycat2021](https://x.com/raycat2021/status/2060718149239279744)

**风险提示**

- 期权结构进入危险区间：标普看涨期权成交量创史上最高，买 Call 占比达 70%；DSPX 升至 42 点创年高，3 个月隐含相关性跌至 8.49%（2024 年 7 月来最低），VIX 7 月期货已在 20 以上。[@ArtofSpecuycky](https://x.com/ArtofSpecuycky/status/2060571365561049121)
- 关键时间节点风险：6 月 12 日 SpaceX 上市、6 月 18 日 FOMC 叠加 OpEx，预判 6 月中至 7 月初标普有 3-5% 回调。[@ArtofSpecuycky](https://x.com/ArtofSpecuycky/status/2060571365561049121)
- K 型经济分化加剧：股市屡创新高，消费者信心却跌至历史低点。[@charliebilello](https://x.com/charliebilello/status/2060671720994791518)
- 小票爆炒频率明显上升（$ASTC 3 天 30 倍、$HUBC 1 天 6 倍），典型牛市下半场信号，操纵横行。[@artinmemes](https://x.com/artinmemes/status/2060579951263502339)

---

## 五、产业 / 个股焦点

### AI 基础设施与服务器

- **$DELL**：财报超预期，AI 服务器季收入 161 亿同比 +757%；通用服务器受 Agentic AI 驱动，不依赖 $NVDA GPU 供应链；B2B 内存供应优先权强，PC 端韧性超预期。[推文1](https://x.com/jukan05/status/2060621480208355415) [推文2](https://x.com/TJ_Research/status/2060671163848614319)
- **$NVDA**：MSCI 调仓机械砸盘提供买点；PE 32.81 / Forward PE 24.45 / PEG 0.66 估值极低；正式瞄准 2000 亿美元 PC 市场，ARM 架构进军笔记本；VR200 机架成本较 GB300 涨 95%，Memory 涨幅最高。[推文1](https://x.com/ArtofSpecuycky/status/2060557166655000962) [推文2](https://x.com/FluentInFinance/status/2060565612762673240) [推文3](https://x.com/SpermCapital/status/2060515250060087675)

### 软件板块

- **$NOW**：单日暴涨 14%，自由现金流创历史最大增长，有 KOL 4 月 13 日买入后持仓从 83 涨至 124，认为上涨未结束。[推文1](https://x.com/ArtofSpecuycky/status/2060571365561049121) [推文2](https://x.com/nft_hu/status/2060526508817682557)
- **$OKTA**：单日暴涨 28%，软件轮动核心受益标的。[@ArtofSpecuycky](https://x.com/ArtofSpecuycky/status/2060571365561049121)
- **$MSFT**：涨 5%，AI Agent 本地执行软件即将发布，端侧 AI 落地催化剂。[@jukan05](https://x.com/jukan05/status/2060709797830566262)
- **$ADBE**：形成反向头肩底，Burry 持仓背书，短期目标 $270 缺口回补；软件轮动 + 财报预期，中线目标 300/330。[推文1](https://x.com/Mr_Derivatives/status/2060535039755198747) [推文2](https://x.com/ArtofSpecuycky/status/2060557166655000962)
- **$MDB**：AI 双重筛选后判断将突破下降趋势线，基本面无问题。[@WallStreet0Name](https://x.com/WallStreet0Name/status/2060518602168778996)

### 光子学 / 光通信

- **$FOTO**：光子产业链主动管理型 ETF 正式上市，覆盖光通信、激光器、硅光全链条。[@tychozzz](https://x.com/tychozzz/status/2060697443650683071)
- **$LITE**：占 $FOTO 首位持仓 13.1%，AI 数据中心光互连核心标的。[@tychozzz](https://x.com/tychozzz/status/2060697443650683071)
- **$SIVE**：市值从 1.5 亿成长至 20 亿美元，光子学管道 5 个月内增长 77%，SATCOM 量产订单即将落地，CPO 需求远超供给，2027 年后营收曲线有望指数级增长；客户包括 $JBL、$AAPL、$MRVL。[推文1](https://x.com/aleabitoreddit/status/2060597940461486513) [推文2](https://x.com/aleabitoreddit/status/2060615296357196178)
- **富士康 CPO**：股东会透露 CPO 交换产品 Q3 启动，2026 年出货 1 万台并爆发式增长，H2 出货量将开始体现财报。[@aleabitoreddit](https://x.com/aleabitoreddit/status/2060685584365150508)

### 功率器件 / 被动元件

- **SiC / GaN**：$NVDA 800V HVDC 数据中心架构落地将催生新需求，GaN 增速（42% CAGR）更快，实际增速大概率超 Yole 2024 年预测。[@nft_hu](https://x.com/nft_hu/status/2060705088101024154)
- **MLCC**：AI 服务器端 80%+ CAGR，高端品交货期超 20 周，价格上涨 20-40%；Murata、Taiyo Yuden、SEMCO 扩产；设备与原材料供应商将跑赢 MLCC 生产商。[推文1](https://x.com/nft_hu/status/2060528583911862675) [推文2](https://x.com/LinQingV/status/2060661994538315922)

### 其他个股

- **$AVGO**：上升通道盘整 42 天量能放大，下周三财报催化，目标 500/545。[@ArtofSpecuycky](https://x.com/ArtofSpecuycky/status/2060557166655000962)
- **$MU**：有 KOL 深夜研读 8 年财报电话会议记录，暗示深度研究动作，值得关注后续观点。[@insane_analyst](https://x.com/insane_analyst/status/2060605346784416003)
- **$PLTR / $HOOD / $ONDS / $TSLA**：被看好持有甚至加杠杆，靠卖期权生活策略。[@cnfinancewatch](https://x.com/cnfinancewatch/status/2060696262366855439)
- **$NOK**：下周有望成主角，回踩 14.1 补缺口叠加 EMA20 为 Leap Call 买点，存在价值重估空间。[推文1](https://x.com/hanking66/status/2060618347084161393) [推文2](https://x.com/ArtofSpecuycky/status/2060557166655000962)
- **$NBIS**：抛压释放完毕可以介入。[@hanking66](https://x.com/hanking66/status/2060618347084161393)
- **$GEV**：跌出黄金坑但尚未止跌，需等待确认信号。[@hanking66](https://x.com/hanking66/status/2060618347084161393)
- **$CRWV**：突破下跌趋势线，目标 128/145。[@ArtofSpecuycky](https://x.com/ArtofSpecuycky/status/2060557166655000962)
- **$AMKR**：Bull Flag 形态，目标 100。[@ArtofSpecuycky](https://x.com/ArtofSpecuycky/status/2060557166655000962)
- **$SMR**：站上 EMA20/50，突破 13 目标 17-20。[@ArtofSpecuycky](https://x.com/ArtofSpecuycky/status/2060557166655000962)
- **$CRCL**：回补 100 缺口为买点，右侧突破关注 112-115。[@ArtofSpecuycky](https://x.com/ArtofSpecuycky/status/2060557166655000962)
- **SpaceX / $SPCX**：预计 6 月上市，合约报价 190+，建议 168-175 区间大资金做多。[@WallStreet0Name](https://x.com/WallStreet0Name/status/2060607453813981212)

---

## 六、交易信号

| 方向 | 标的 | 信号描述 | 来源 |
|------|------|----------|------|
| 多 | $DELL | 财报超预期盘后 +33%，AI 服务器逻辑验证 | [链接](https://x.com/ArtofSpecuycky/status/2060571365561049121) |
| 多 | $NVDA | MSCI 砸盘提供买点，208-203 为理想入场区，建议 Leap Call | [链接](https://x.com/ArtofSpecuycky/status/2060557166655000962) |
| 多 | $AVGO | 下周三财报催化，目标 500/545 | [链接](https://x.com/ArtofSpecuycky/status/2060557166655000962) |
| 多 | $NOW | 自由现金流创历史新高，上涨行情未结束 | [链接](https://x.com/nft_hu/status/2060526508817682557) |
| 多 | $ADBE | 反向头肩底 + 软件轮动，目标 270 缺口 / 中线 300-330 | [链接](https://x.com/Mr_Derivatives/status/2060535039755198747) |
| 多 | $SIVE | CPO 超级周期，光子学管道 77% 增长，SATCOM 量产在即 | [链接](https://x.com/aleabitoreddit/status/2060597940461486513) |
| 多 | $NOK | 回踩 14.1 补缺口 + EMA20，Leap Call 买点 | [链接](https://x.com/ArtofSpecuycky/status/2060557166655000962) |
| 多 | $CRWV | 突破下跌趋势线，目标 128/145 | [链接](https://x.com/ArtofSpecuycky/status/2060557166655000962) |
| 多 | $AMKR | Bull Flag，目标 100 | [链接](https://x.com/ArtofSpecuycky/status/2060557166655000962) |
| 多 | $SMR | 站上 EMA20/50，目标 17-20 | [链接](https://x.com/ArtofSpecuycky/status/2060557166655000962) |
| 多 | $SPCX | SpaceX 上市前，168-175 区间大资金做多 | [链接](https://x.com/WallStreet0Name/status/2060607453813981212) |
| 多 | $MDB | AI 筛选看多，将突破下降趋势线 | [链接](https://x.com/WallStreet0Name/status/2060518602168778996) |
| 观察 | $MU | KOL 深度研读 8 年财报，后续观点值得跟踪 | [链接](https://x.com/insane_analyst/status/2060605346784416003) |
| 观察 | $GEV | 跌出黄金坑，尚未止跌，等待确认 | [链接](https://x.com/hanking66/status/2060618347084161393) |
| 警惕 | $SPY | 750 下方 740 为 Gamma 翻转区，跌破触发连锁止损 | [链接](https://x.com/ArtofSpecuycky/status/2060571365561049121) |
| 警惕 | 小票 | $ASTC / $HUBC 等爆炒，操纵横行，散户慎入 | [链接](https://x.com/artinmemes/status/2060579951263502339) |

---

## 七、投资理念

- **不择时，但要懂结构**：@BrianFeroldi 强调完美择时收益可观但不现实，长期持有优质企业更可靠。[@BrianFeroldi](https://x.com/BrianFeroldi/status/2060677984713884005)

- **AI 并非零和博弈**：大模型、企业定制、推理基础设施、云厂商、端侧推理需求并存，不同层次的玩家都有空间。[@zephyr_z9](https://x.com/zephyr_z9/status/2060517771780493518)

- **硬件远超软件**：软件股 $CRM 等仅反弹 10-15% 且此前已跌 25-60%，而 AI 硬件股 $SNDK、$AAOI 等轻松上涨 200-1000%，本轮 AI 行情硬件是主战场。[@aleabitoreddit](https://x.com/aleabitoreddit/status/2060578117320904884)

- **供应链上游比生产商更值得买**：MLCC 设备与原材料供应商将跑赢 MLCC 生产商，资本开支潮中卖铲子的逻辑依然成立。[@LinQingV](https://x.com/LinQingV/status/2060661994538315922)

- **IPO 长期陷阱**：首日平均涨 23%，但此后三年跑输市场 25%，SpaceX 估值 1.8 万亿、市销率 93 倍，高估值 IPO 需谨慎。[@raycat2021](https://x.com/raycat2021/status/2060718149239279744)

- **仓位管理优先于方向判断**：期权结构已进入危险区间，看涨情绪极度拥挤时，控制仓位比押注方向更重要。[@ArtofSpecuycky](https://x.com/ArtofSpecuycky/status/2060571365561049121)

- **等均线再买，纪律比判断重要**：以 $INTC 跌至 20 日线为例，有纪律的入场点比追涨更能保护本金。[@hanking66](https://x.com/hanking66/status/2060560140663943242)

## 最近 7 天

- [2026-05-30](digests/2026/05/30.md)

## 监控的 KOL

- [@10kdiver](https://x.com/10kdiver)
- [@3ethtomoon](https://x.com/3ethtomoon)
- [@aleabitoreddit](https://x.com/aleabitoreddit)
- [@alphatrends](https://x.com/alphatrends)
- [@AnnaEconomist](https://x.com/AnnaEconomist)
- [@Areskapitalon](https://x.com/Areskapitalon)
- [@ArtofSpecuycky](https://x.com/ArtofSpecuycky)
- [@artinmemes](https://x.com/artinmemes)
- [@awealthofcs](https://x.com/awealthofcs)
- [@biancoresearch](https://x.com/biancoresearch)
- [@BrianFeroldi](https://x.com/BrianFeroldi)
- [@ByrneHobart](https://x.com/ByrneHobart)
- [@caizhenghai](https://x.com/caizhenghai)
- [@charliebilello](https://x.com/charliebilello)
- [@cnfinancewatch](https://x.com/cnfinancewatch)
- [@cyrilxuq](https://x.com/cyrilxuq)
- [@elerianm](https://x.com/elerianm)
- [@fi56622380](https://x.com/fi56622380)
- [@FluentInFinance](https://x.com/FluentInFinance)
- [@hanking66](https://x.com/hanking66)
- [@insane_analyst](https://x.com/insane_analyst)
- [@josephwang](https://x.com/josephwang)
- [@jukan05](https://x.com/jukan05)
- [@labubu_trader](https://x.com/labubu_trader)
- [@leopoldasch](https://x.com/leopoldasch)
- [@LinQingV](https://x.com/LinQingV)
- [@LizAnnSonders](https://x.com/LizAnnSonders)
- [@LucyBuilding](https://x.com/LucyBuilding)
- [@LynAldenContact](https://x.com/LynAldenContact)
- [@morganhousel](https://x.com/morganhousel)
- [@Mr_Derivatives](https://x.com/Mr_Derivatives)
- [@nbblock](https://x.com/nbblock)
- [@nft_hu](https://x.com/nft_hu)
- [@NickTimiraos](https://x.com/NickTimiraos)
- [@octopusycc](https://x.com/octopusycc)
- [@qinbafrank](https://x.com/qinbafrank)
- [@raycat2021](https://x.com/raycat2021)
- [@realDonaldTrump](https://x.com/realDonaldTrump)
- [@relly_eth](https://x.com/relly_eth)
- [@Remzztrades](https://x.com/Remzztrades)
- [@ripster47](https://x.com/ripster47)
- [@Ritholtz](https://x.com/Ritholtz)
- [@rwang07](https://x.com/rwang07)
- [@Scottrades](https://x.com/Scottrades)
- [@ShanghaoJin](https://x.com/ShanghaoJin)
- [@shufen46250836](https://x.com/shufen46250836)
- [@SpermCapital](https://x.com/SpermCapital)
- [@sssjeffpu](https://x.com/sssjeffpu)
- [@starzq](https://x.com/starzq)
- [@SV_Nomad](https://x.com/SV_Nomad)
- [@TJ_Research](https://x.com/TJ_Research)
- [@tychozzz](https://x.com/tychozzz)
- [@WallStreet0Name](https://x.com/WallStreet0Name)
- [@xiaomustock](https://x.com/xiaomustock)
- [@zephyr_z9](https://x.com/zephyr_z9)

<details>
<summary>各 KOL 详细总结（点击展开）</summary>

### @realDonaldTrump · 20 条

**核心观点**：summary_failed

**情绪**：unclear

- 暂无要点。

### @cnfinancewatch · 12 条

**核心观点**：牛市未结束，持有芯片/机器人/日本资产，英伟达不卖

**情绪**：bullish

- 看好$PLTR、$HOOD、$ONDS及$TSLA，建议持有甚至加杠杆，靠卖期权生活 ($PLTR, $HOOD, $ONDS, $TSLA) [原推](https://x.com/cnfinancewatch/status/2060696262366855439)
- 英伟达未见顶，当前是牛市，不应卖出 ($NVDA) [原推](https://x.com/cnfinancewatch/status/2060695120463446349)
- $NOW 股价跌超50%，但自由现金流创历史最大增长，暗示被低估 ($NOW) [原推](https://x.com/cnfinancewatch/status/2060668033136459952)
- 英伟达台北发布会值得期待，AI PC（CPU+GPU深度整合）是当前市场刚需，万至两万美元区间尚无完美产品 ($NVDA) [原推](https://x.com/cnfinancewatch/status/2060669610823958992)
- 日本资产目前处于全球折价率最高水平，看好日本牛市 [原推](https://x.com/cnfinancewatch/status/2060666699620462940)
- 24年曾呼吁全仓芯片和机器人，26年将再开100人订阅社群，到期解散 [原推](https://x.com/cnfinancewatch/status/2060697194957816046)

### @hanking66 · 7 条

**核心观点**：看多NVDA、NOK、NBIS、GEV等超跌股，建议逢低买入

**情绪**：bullish

- 下周重点关注四只超跌股：$NVDA被视为白菜价、$NOK下周有望成主角、$NBIS抛压释放完毕可以介入、$GEV跌出黄金坑但尚未止跌 ($NVDA, $NOK, $NBIS, $GEV) [原推](https://x.com/hanking66/status/2060618347084161393)
- $NVDA大概率用ARM架构进军PC CPU市场，对$INTC构成威胁，INTC承压，建议逢低买入NVDA ($NVDA, $INTC) [原推](https://x.com/hanking66/status/2060612487557554685)
- 川普买入$TKO，号召跟随黄毛操作冲入 ($TKO) [原推](https://x.com/hanking66/status/2060561816359752069)
- 提醒投资者要有耐心等到5日/10日/20日线再买，以$INTC跌至20日线为例说明纪律重要性 ($INTC) [原推](https://x.com/hanking66/status/2060560140663943242)
- MSCI指数调仓：加仓博通、微软、闪迪、美光，减持$NVDA和$INTC，导致隔夜大变天 ($NVDA, $INTC) [原推](https://x.com/hanking66/status/2060549567146594319)

### @zephyr_z9 · 5 条

**核心观点**：AI基础设施全面扩张，推理优化、科学计算与定制芯片并行驱动行业需求

**情绪**：bullish

- MiMo-V2.5系列通过Hybrid SWA架构将KVCache压缩至1/7，生产侧缓存命中率达93%-95%，支撑API降价 [原推](https://x.com/zephyr_z9/status/2060686816865620027)
- 韩媒报道三星为OpenAI开发定制SoC的合作已陷入停滞 [原推](https://x.com/zephyr_z9/status/2060646781684416545)
- 某即将入职教授将150万美元全部预算押注ChatGPT token+本科生，认为效果优于招收研究生 [原推](https://x.com/zephyr_z9/status/2060637725984956918)
- 字节跳动AI4S团队重组，同步推进 $QCOM ASIC大规模定制芯片及ARM/RISC-V双轨CPU，科学计算被中国大厂列为战略AI方向 ($QCOM) [原推](https://x.com/zephyr_z9/status/2060518857606062504)
- 大模型、企业定制、推理基础设施、三大云厂商、端侧推理需求并存，AI并非零和博弈 [原推](https://x.com/zephyr_z9/status/2060517771780493518)

### @BrianFeroldi · 5 条

**核心观点**：不择时市场，专注投资者教育与长期价值理念

**情绪**：neutral

- 不尝试择时市场，但数据显示若能完美择时收益可观 [原推](https://x.com/BrianFeroldi/status/2060677984713884005)
- 多次推广免费投资信息图电子书，面向希望学习分析企业的投资者 [原推](https://x.com/BrianFeroldi/status/2060662743913357472)
- 分享查理·芒格十大书单，获得高互动（223赞/53转） [原推](https://x.com/BrianFeroldi/status/2060513613308166409)

### @jukan05 · 4 条

**核心观点**：AI Agent推动通用服务器与Windows PC端侧计算需求，Dell受益明显

**情绪**：bullish

- $MSFT 预计发布新软件，支持AI Agent在Windows PC本地执行任务，利好端侧AI落地 ($MSFT, $NVDA) [原推](https://x.com/jukan05/status/2060709797830566262)
- 韩媒报道三星曾为OpenAI开发定制SoC，但合作近期已陷入停滞 [原推](https://x.com/jukan05/status/2060646311469498784)
- $DELL 财报超预期：通用服务器受Agentic AI驱动高速增长、PC端供应链优势明显，$NVDA N1/N1X若打入WoA市场将进一步提升OEM议价能力 ($DELL, $NVDA) [原推](https://x.com/jukan05/status/2060621480208355415)
- 作者将赴台北参加Computex，后续可能带来一线产业链信息 [原推](https://x.com/jukan05/status/2060554094620950653)

### @nft_hu · 4 条

**核心观点**：看好AI基础设施相关供应链，包括SiC/GaN功率器件、MLCC及软件平台

**情绪**：bullish

- SiC与GaN市场差距收窄，GaN增速（42% CAGR）更快，但$NVDA 800V HVDC数据中心架构落地将催生新需求，实际增速大概率超Yole 2024年预测 ($NVDA) [原推](https://x.com/nft_hu/status/2060705088101024154)
- MLCC市场深度分析：AI服务器MLCC以80%+ CAGR高速增长，高端品lead time超20周，价格上涨20-40%；Murata、Taiyo Yuden、SEMCO等Tier1扩产，设备与原材料供应商将是最大受益者，预计将跑赢MLCC生产商 [原推](https://x.com/nft_hu/status/2060528583911862675)
- 4月13日买入$NOW，持仓从83涨至124，认为上涨行情尚未结束 ($NOW) [原推](https://x.com/nft_hu/status/2060526508817682557)

### @aleabitoreddit · 4 条

**核心观点**：光子学/CPO超级周期正在加速，$SIVE是核心标的，AI硬件远超软件股表现

**情绪**：bullish

- 富士康股东会透露CPO交换产品Q3启动，2026年出货1万台并爆发式增长，旗下子公司Shunsin（6451）负责先进光学业务，H2出货量将开始体现在财报中 [原推](https://x.com/aleabitoreddit/status/2060685584365150508)
- $SIVE市值从1.5亿成长至20亿美元，客户包括$JBL、$AAPL、$MRVL等，Win Semi产能可扩展性被看空者低估，预计美国机构将在下一轮超级周期前震出散户 ($SIVE, $JBL, $AAPL, $MRVL, $LITE, $AVGO, $NBIS, $RKLB) [原推](https://x.com/aleabitoreddit/status/2060615296357196178)
- $SIVE财报电话会极度看涨：光子学管道5个月内增长77%，SATCOM量产订单即将落地，美国双重上市推进顺利，CPO需求远超供给，2027年后营收曲线有望呈指数级增长 ($SIVE, $JBL, $LITE, $AVGO) [原推](https://x.com/aleabitoreddit/status/2060597940461486513)
- 软件股$CRM等仅反弹10-15%且此前已跌25-60%，而AI硬件股$SNDK、$AAOI等轻松上涨200-1000%，两类资产表现天壤之别 ($CRM, $FIG, $SNDK, $AAOI) [原推](https://x.com/aleabitoreddit/status/2060578117320904884)

### @WallStreet0Name · 4 条

**核心观点**：美股偏乐观，关注SpaceX上市机会与$MDB突破趋势，会员服务调整为按需订阅

**情绪**：bullish

- 会员到期无需立即续费，比特币行情已更新，黄金建议小白回避，美股内容将持续发布在X上，网站80%内容免费，会员改为按需订阅模式 [原推](https://x.com/WallStreet0Name/status/2060669918593609903)
- SpaceX（$SPCX）预计6月上市，当前合约报价190+，建议在168-175区间大资金做多；Bitget有pre-SPCX认购价164刀，适合小资金参与 ($SPCX) [原推](https://x.com/WallStreet0Name/status/2060607453813981212)
- $MDB基本面无问题，经AI双重筛选后判断未来将突破下降趋势线，看多 ($MDB) [原推](https://x.com/WallStreet0Name/status/2060518602168778996)

### @raycat2021 · 3 条

**核心观点**：IPO长期跑输大盘，SpaceX估值高企，中国竞争压力输出海外

**情绪**：bearish

- IPO首日平均涨23%，但此后三年跑输市场25%；SpaceX估值或达1.8万亿美元，市销率93倍，Starlink用户1030万，2025年预计营收114亿美元，EBITDA率63% [原推](https://x.com/raycat2021/status/2060718149239279744)
- 美欧担忧中国企业将内卷式竞争输出海外，冲击本土企业并压制薪资 [原推](https://x.com/raycat2021/status/2060715968410877977)
- 历史典故：1900年唐才常自立军勤王行动因资金匮乏、立场矛盾而失败，康有为海外空谈 [原推](https://x.com/raycat2021/status/2060713143542935869)

### @charliebilello · 2 条

**核心观点**：股市创历史新高与消费者信心创历史低点并存，K型经济分化加剧

**情绪**：bearish

- K型经济的缩影：股市屡创新高，消费者信心却跌至历史低点，两极分化显著 [原推](https://x.com/charliebilello/status/2060671720994791518)
- 作者每周向数万名投资者发送市场重要图表与主题简报，推广订阅 [原推](https://x.com/charliebilello/status/2060692704506392995)

### @ArtofSpecuycky · 2 条

**核心观点**：软件板块轮动实质落地，SPY 750是下周多空分水岭，仓位管理优先于方向判断

**情绪**：bullish

- 5月收官九连阳，$SPY守住750关键支撑，标普5月涨5%，纳指涨超8%；750下方7400为做市商Gamma翻转区，跌破将触发多头连锁止损 ($SPY) [原推](https://x.com/ArtofSpecuycky/status/2060571365561049121)
- 软件板块全面爆发：$IGV单日暴涨6.25%重回200日均线，$MSFT涨5%，$NOW涨14%，$OKTA涨28%，$SNOW持续强势，AI叙事证伪空头踩踏 ($IGV, $MSFT, $NOW, $OKTA, $SNOW) [原推](https://x.com/ArtofSpecuycky/status/2060571365561049121)
- $NVDA尾盘因MSCI半年度调仓被机械性砸盘，20分钟内市值蒸发超1400亿美元；$DELL盘后AI服务器季收入161亿同比+757%，盘后暴涨近33% ($NVDA, $DELL) [原推](https://x.com/ArtofSpecuycky/status/2060571365561049121)
- 期权结构进入危险区间：标普看涨期权成交量创史上最高，买Call占比达70%；DSPX升至42点创年高，3个月隐含相关性跌至8.49%（2024年7月来最低），VIX 7月期货已在20以上 [原推](https://x.com/ArtofSpecuycky/status/2060571365561049121)
- 关键时间节点：6月12日SpaceX上市、6月18日FOMC叠加OpEx，预判6月中至7月初标普有3-5%回调；高盛指出高位动量股资金已流向低位滞涨股 [原推](https://x.com/ArtofSpecuycky/status/2060571365561049121)
- 中短线机会：$AVGO上升通道盘整42天量能放大，下周三财报催化，目标500/545；$CRWV突破下跌趋势线，目标128/145；$AMKR Bull Flag形态，目标100 ($AVGO, $CRWV, $AMKR) [原推](https://x.com/ArtofSpecuycky/status/2060557166655000962)
- 中短线机会续：$CRCL回补100缺口为买点，右侧突破关注112-115；$SMR站上EMA20/50，突破13目标17-20；$ADBE下跌趋势线临近突破，软件轮动+财报预期，目标300/330 ($CRCL, $SMR, $ADBE) [原推](https://x.com/ArtofSpecuycky/status/2060557166655000962)
- 长线机会：$NVDA PE 32.81/Forward PE 24.45/PEG 0.66估值极低，208-203为理想买点，建议Leap Call；$NOK回踩14.1补缺口叠加EMA20为Leap Call买点，存在价值重估空间 ($NVDA, $NOK) [原推](https://x.com/ArtofSpecuycky/status/2060557166655000962)

### @FluentInFinance · 2 条

**核心观点**：NVDA凭借全栈策略进军2000亿美元PC/笔记本市场，延续统治级扩张路径

**情绪**：bullish

- $NVDA 正式瞄准价值 $200B 的PC市场，复制其在游戏GPU和数据中心AI领域的统治策略 ($NVDA) [原推](https://x.com/FluentInFinance/status/2060565612762673240)
- $NVDA 进入市场从不为竞争，而是为了主导——全栈打法如今剑指笔记本市场 ($NVDA) [原推](https://x.com/FluentInFinance/status/2060557497643983258)

### @tychozzz · 1 条

**核心观点**：纯光子产业链ETF $FOTO上市，覆盖光通信/硅光/激光器核心标的

**情绪**：bullish

- 光子产业链主动管理型ETF $FOTO正式上市，打包光通信、激光器、硅光、光电子器件相关标的，类似内存存储板块的DRAM ETF逻辑 ($FOTO) [原推](https://x.com/tychozzz/status/2060697443650683071)
- $LITE 占前七大持仓首位（13.1%），卡位激光器与光子器件，是AI数据中心光互连核心标的 ($FOTO, $LITE) [原推](https://x.com/tychozzz/status/2060697443650683071)

### @TJ_Research · 1 条

**核心观点**：Dell受益于AI驱动的通用服务器增长，PC端韧性超预期，NVIDIA Arm芯片带来额外上行空间

**情绪**：bullish

- Agentic AI推动通用服务器需求，$DELL 在高利润通用服务器领域持续受益，不依赖NVIDIA GPU供应链 ($DELL) [原推](https://x.com/TJ_Research/status/2060671163848614319)
- $DELL 作为Tier-1厂商在内存供应上具有优先权，B2B市场定价能力强，PC端表现优于市场预期 ($DELL) [原推](https://x.com/TJ_Research/status/2060671163848614319)
- 若$NVDA N1/N1X在WoA站稳脚跟，$DELL 等OEM可借此向$INTC和$AMD施压，获得额外议价空间 ($NVDA, $DELL, $INTC, $AMD) [原推](https://x.com/TJ_Research/status/2060671163848614319)

### @LinQingV · 1 条

**核心观点**：AI服务器驱动MLCC市场高增长，设备与原材料供应商将超越MLCC生产商表现

**情绪**：bullish

- MLCC整体市场规模约150亿美元，AI服务器MLCC以80%+年复合增长率领跑，通用服务器因AI Agent推动CPU需求也将加速增长（30-40% CAGR），智能手机端2026-27年将负增长 [原推](https://x.com/LinQingV/status/2060661994538315922)
- MLCC价格上涨驱动因素：镍/银原材料成本高企、高端（高容高压）产品供需错配、交货期超20周，中国市场囤货与重复下单推动现货价格上涨20-40% [原推](https://x.com/LinQingV/status/2060661994538315922)
- 村田（Murata）、太阳诱电（Taiyo Yuden）、三星电机（SEMCO）等一线厂商扩产聚焦AI服务器市场，预计中低端市场将向二三线及中国供应商开放（类Macronix效应） [原推](https://x.com/LinQingV/status/2060661994538315922)
- MLCC生产设备与原材料供应商将是本轮资本开支潮最大受益者，预计其表现将超越MLCC生产商股票 [原推](https://x.com/LinQingV/status/2060661994538315922)

### @insane_analyst · 1 条

**核心观点**：作者深夜研读美光8年财报电话会议记录，暗示正在深度研究$MU

**情绪**：unclear

- 作者周五夜间沉浸式研读 $MU 8年财报电话会议记录并制作CEO Sanjay梗图，显示对该股有深度研究动作 ($MU) [原推](https://x.com/insane_analyst/status/2060605346784416003)

### @artinmemes · 1 条

**核心观点**：美股牛市下半场小票炒作盛行，带单群操纵横行，建议用Reddit热度捕捉第1.5波

**情绪**：bearish

- $ASTC 3天30倍、$HUBC 1天6倍，小票爆炒频率明显上升，典型牛市下半场信号 ($ASTC, $HUBC) [原推](https://x.com/artinmemes/status/2060579951263502339)
- 操盘套路固定：找仙股 → 核心群/卫星群/Reddit水军/KOL联动喊单 → 边拉边喊 → 择机dump，基本面分析几乎无用 [原推](https://x.com/artinmemes/status/2060579951263502339)
- 参与策略：付费群胜率一般；或通过Reddit 24小时热度涨幅榜捕捉新上榜票，尝试逮第1.5波 [原推](https://x.com/artinmemes/status/2060579951263502339)

### @ShanghaoJin · 1 条

**核心观点**：发布哲学感悟，无具体市场观点

**情绪**：unclear

- 发布一句易经感悟「止而巽，动不穷也」，与「光」相关，无涉及具体股票或市场判断。 [原推](https://x.com/ShanghaoJin/status/2060551178946269543)

### @ByrneHobart · 1 条

**核心观点**：今日分享西德宪法允许其他地区单方面申请并入的独特历史条款

**情绪**：neutral

- 西德宪法设有条款，允许其他德国地区自行决定加入，作者认为这是史上罕见的允许他国单方面被并入的宪法安排 [原推](https://x.com/ByrneHobart/status/2060540284606276046)

### @Mr_Derivatives · 1 条

**核心观点**：$ADBE技术面形成反向头肩底，短期目标看涨至$270缺口回补

**情绪**：bullish

- $ADBE 软件股跌深反弹机会：股价多次测试50日均线，形成迷你反向头肩底形态，Burry持仓背书，短期目标看涨至$270缺口回补，类比$PYPL此前缺口填补走势 ($ADBE, $PYPL) [原推](https://x.com/Mr_Derivatives/status/2060535039755198747)

### @Remzztrades · 1 条

**核心观点**：感谢超10万粉丝两年来的陪伴，期待更多盈利交易日

**情绪**：neutral

- 连续两年每日分享交易思路与心得，粉丝突破10万，表达感恩并展望未来更多绿色交易日 [原推](https://x.com/Remzztrades/status/2060531659963801764)

### @SpermCapital · 1 条

**核心观点**：摩根士丹利预计英伟达VR200机架成本较GB300涨幅约95%，Memory涨幅最为显著

**情绪**：bullish

- 摩根士丹利研报估算$NVDA从GB300升级至VR200后，单台NVL72机架总成本从约399万美元升至780万美元，涨幅约95%；其中Memory部件从37.4万美元涨至200.2万美元，涨幅最高 ($NVDA) [原推](https://x.com/SpermCapital/status/2060515250060087675)

</details>

## 历史归档

- [2026-05](digests/2026/05/)
