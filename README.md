# 美股KOL每日摘要

最后更新：2026-05-31

这个仓库每天北京时间 20:30 自动抓取 X 上 55 位美股相关 KOL 的发言，整理成一页当天市场摘要。你可以先看今日完整报告，再看下面的当日总结和各 KOL 细节。

[阅读今日完整报告](digests/2026/05/31.md)

## 你会看到什么

- **当日总结**：今天最重要的市场共识、分歧和特朗普相关影响
- **最近 7 天**：快速回看过去一周的变化
- **KOL 明细**：每位账号当天具体说了什么
- **历史归档**：按月查看以前的日报

## 自己运行

- 默认不会执行远端 `git push`；只有 `publish.git_push=true` 且 `KOL_MONITOR_ALLOW_PUSH=true` 同时满足时才会推送。
- 如果你从 GitHub clone 后直接运行，它不会自动推送到原仓库；要发布到自己的仓库，请先把 `origin` 改成自己的 fork。
- 只想本地验证流程，可以运行 `kol-monitor run-once --no-publish`。

## 2026-05-31 当日总结

# 美股 KOL 每日情报摘要

---

## 一、特朗普相关

**核心判断：** 当日推文以政治攻防与个人形象为主，无直接股市政策信号。但以下几条存在潜在市场联动，逐一列出推测依据。

- **USDA"棉花优先于化学品"政策**：特朗普政府推动美国本土纺织业复兴，若后续出台采购优先令或补贴政策，可能利好美国本土棉花种植与纺织供应链相关标的（如 $PVH、$HBI、$VFC 等服装制造商，以及农业类 ETF $MOO）。目前仅为政策方向表态，尚无具体立法，属推测阶段。[@realDonaldTrump 原文](https://x.com/realDonaldTrump/status/truth_1780204097295237428)

- **肯尼迪中心翻新争议**：特朗普抨击联邦法官叫停翻新工程，并扬言弹劾法官。若司法与行政对抗升级，可能加剧市场对政策不确定性的担忧，短期对风险资产情绪偏负面，但目前仍属政治层面事件。[@realDonaldTrump 原文](https://x.com/realDonaldTrump/status/truth_1780181339409705238)

- **Fox News 媒体曝光**：特朗普为 Fox News 晚间节目（$FOX / $FOXA）做背书宣传，对收视率有边际正向影响，但量级有限，不构成交易信号。[@realDonaldTrump 原文](https://x.com/realDonaldTrump/status/truth_1780168656973302939)

- **白宫无人机停机坪展示**：特朗普展示白宫屋顶无人机基础设施，结合近期美国加速布局无人机产业的背景（见产业焦点部分），可推测政府对无人机基础设施投入的政治意愿持续强化，对国内无人机产业链构成中期政策利好。[@realDonaldTrump 原文](https://x.com/realDonaldTrump/status/truth_1780174680962480321)

- **其余推文**（体检认知测试、倒影池修缮、纽约州长批评、佐治亚选举案）均为纯政治内容，无可识别的市场联动。

---

## 二、今日关键词

- **MLCC 供需错配**：AI 服务器拉动高端 MLCC 需求，47μF/22μF 规格短缺，现货价格上涨 20–40%
- **AI PC 换机潮**：$MSFT Windows AI 生态落地进度是核心变量，$NVDA N1X 芯片出货约 1000 万台
- **财报周倒计时**：$AVGO、$CRWD、$PANW、$CRDO、$HPE 等密集登场
- **Edge AI 三足鼎立**：$NVDA 入局 AI PC 不等于利空 $INTC/$AMD，三者可并行受益
- **期权结构预警**：VIX 远期溢价、$DSPX 创年内新高，底层脆弱性积累

---

## 三、重要新闻

- **高盛大幅上调韩国存储股盈利预测**：SK 海力士（$000660.KS）2027 年营业利润预测从 261 兆韩元上调至 401 兆韩元；三星电子（$005930.KS）2028 年预测从 495 兆上调至 610 兆韩元。[@jukan05 · 1](https://x.com/jukan05/status/2061045030387699909) [@jukan05 · 2](https://x.com/jukan05/status/2061044139853283730)

- **微软向三星预付约 100 亿美元**：据 GSR，超大规模云厂商向存储厂商支付 15–30% 预付款，微软已向 $005930.KS 三星预付高达 100 亿美元，锁定 HBM/DRAM 产能。[@jukan05 · 3](https://x.com/jukan05/status/2060958332966609060)

- **$DELL 首台 Vera Rubin NVL72 在 $CRWV CoreWeave 落地部署**：$NVDA 与 $DELL 合作的最新一代 AI 服务器正式交付，标志着 Rubin 架构进入商用阶段。[@jukan05 · 4](https://x.com/jukan05/status/2060916762405974402)

- **美股首只纯光子产业链 ETF $FOTO 上市**：主动管理，前七大持仓含 $LITE、$IPGP、$COHR、$CIEN、$LASR、$FN、$AAOI，但混入工业/国防激光非 AI 赛道标的，需注意成分纯度。[@SpermCapital](https://x.com/SpermCapital/status/2060940467672322221)

- **华为混合键合技术领先行业**：华为 2026 年麒麟手机将采用 1.5μm 键合间距 3D 堆叠，2027 年进一步缩至 1μm；$TSM SoIC 当前仍在 6μm，英特尔 Foveros Direct 为 9μm，华为互连密度领先 16–36 倍。[@zephyr_z9](https://x.com/zephyr_z9/status/2060911676611018786)

- **$TTD CEO 大额自购**：CEO 在 $25 附近公开市场买入 1.5 亿美元股票，当前股价约 $21，内部人信心信号明显。[@Mr_Derivatives](https://x.com/Mr_Derivatives/status/2060906681979277397)

---

## 四、宏观判断

- **五月九连阳后需冷静**：标普 749 是六月开局核心锚点，守住则 AI 硬件向软件轮动逻辑延续；跌破 7400 则下行速度将超预期。[@ArtofSpecuycky · 1](https://x.com/ArtofSpecuycky/status/2060927433898070092)

- **期权结构发出警报**：VIX 远期溢价、$DSPX 创年内新高、3 个月隐含相关性跌至 2024 年 7 月以来最低，底层脆弱性正在积累。[@ArtofSpecuycky · 2](https://x.com/ArtofSpecuycky/status/2060927433898070092)

- **估值与宏观信号偏谨慎**：席勒 PE 达 42 倍（仅次于 2000 年互联网泡沫），美元指数日线 MACD 死叉，比特币 ETF 持续净流出。[@ArtofSpecuycky · 3](https://x.com/ArtofSpecuycky/status/2060927433898070092)

- **6 月关键时间节点**：6 月 12 日 SpaceX 上市是流动性虹吸事件；6 月 18 日 FOMC + OpEx 叠加，预计届时出现 3–5% 调整；六月底至七月初是下半年最佳加仓窗口。[@ArtofSpecuycky · 4](https://x.com/ArtofSpecuycky/status/2060927433898070092)

- **纳指周定投 20 年回测**：年化 9.2%–9.5%，比月定投多盈利约 39 万元，最大回撤 43.84%，需配合止盈策略。[@cnfinancewatch](https://x.com/cnfinancewatch/status/2060888800046485906)

- **A 股存量博弈**：芯片算力板块预计今年 9–10 月见顶，后续轮动方向依次为太阳能、太阳能电站，以及 AI 终端应用标的。[@cnfinancewatch · 2](https://x.com/cnfinancewatch/status/2060878463473697188)

---

## 五、产业 / 个股焦点

### AI 基础设施 & 算力

- **$AVGO 博通**：盘整 42 天 MACD 即将金叉，成交量放大至平时两倍，财报若超预期将带动整条 AI 基础设施链。[@ArtofSpecuycky · 5](https://x.com/ArtofSpecuycky/status/2060927433898070092)
- **$DELL + $NVDA**：首台 Vera Rubin NVL72 在 $CRWV 落地，Rubin 架构商用里程碑。[@jukan05 · 4](https://x.com/jukan05/status/2060916762405974402)
- **$DELL AI 工厂架构**：戴尔完整 AI 基础设施体系解析。[@SpermCapital · 1](https://x.com/SpermCapital/status/2060933182527041885)

### MLCC & 被动元件

- **供需错配格局**：仅 47μF 与 22μF 规格短缺，并非全面性短缺；中国市场囤货推动现货价格上涨 20–40%，交货期超 20 周。[@zephyr_z9](https://x.com/zephyr_z9/status/2061002229591740517) [@LucyBuilding](https://x.com/LucyBuilding/status/2061060401421554147)
- **最大受益者是设备与原材料供应商**，而非 Murata、Taiyo Yuden 等 MLCC 生产商本身；村田与 Nippon Chemicon 主动压缩利润率抢占低端份额以遏制中国竞争对手。[@LucyBuilding · 2](https://x.com/LucyBuilding/status/2061060401421554147) [@jukan05 · 5](https://x.com/jukan05/status/2060963413430554713)
- **AI 数据中心 48V/800V 供电升级**推动高压超低 ESL MLCC 需求激增，村田与太阳诱电凭借 BaTiO₃ 粉体及 Core-Shell 材料技术形成壁垒。[@nft_hu · 1](https://x.com/nft_hu/status/2060989431352631615)

### AI PC & Edge AI

- **$MSFT 是 AI PC 概念最大受益者**，下周概念有望被炒作，离新高仍有空间。[@hanking66](https://x.com/hanking66/status/2060950834163470703)
- **$NVDA 入局 AI PC 不利空 $INTC/$AMD**：Edge AI 推理不会全上云，三家可齐头并进。[@TJ_Research](https://x.com/TJ_Research/status/2060877490634059980)
- **$NVDA N1X**：供应链预测未来两年出货约 1000 万台，属小众市场；真正换机潮取决于 Windows AI 生态落地进度。[@LinQingV](https://x.com/LinQingV/status/2060952328484929931)

### 功率半导体

- **从 B200 到 Feynman**，单机架功率半导体含量从 1.1 万美元涨至 19.1 万美元（17 倍），Rubin 后进入指数增长；VRM+PSU 约占七成是英飞凌核心阵地，IBC 环节 GaN 占优，英诺赛科已与 $NVDA 达成 800V 直流架构合作并规模化交付。[@nft_hu · 2](https://x.com/nft_hu/status/2060963776418205762)

### 光子 & 光模块

- **$FOTO ETF 上市**，持仓含 $LITE、$IPGP、$COHR、$CIEN、$LASR、$FN、$AAOI，注意混入非 AI 赛道标的。[@SpermCapital · 2](https://x.com/SpermCapital/status/2060940467672322221)
- **$CRDO** 光模块 CPO 标的，周一盘后财报是近期催化剂。[@artinmemes](https://x.com/artinmemes/status/2061037637310325246)

### 无人机产业链

- 美国加速布局无人机产业，核心驱动：俄乌/中东战争验证低成本无人机价值、本土产能不足、财政优先级提升。[@SpermCapital · 3](https://x.com/SpermCapital/status/2060978472437096538)

### 供应链咽喉节点

- **$AXTI / $SOI / $SIVE**："咽喉节点投资理论"，随路透社与机构对供应链博弈的关注度上升而得到验证。[@aleabitoreddit](https://x.com/aleabitoreddit/status/2060896847695384736)
- **$SIVE（Sivers Semiconductors）**：75 年老牌瑞典半导体厂，当前处于阶段顶部且利空来袭，不适合高位布局。[@SpermCapital · 4](https://x.com/SpermCapital/status/2060896454365818923)

### 韩国存储

- **$005930.KS 三星**：高盛上调盈利预测 + 微软百亿美元预付款，晶圆代工与 DRAM 协同效应值得关注。[@jukan05 · 2](https://x.com/jukan05/status/2061044139853283730) [@insane_analyst](https://x.com/insane_analyst/status/2060914252693770560)
- **$000660.KS SK 海力士**：高盛 2027 年利润预测上调幅度达 54%。[@jukan05 · 1](https://x.com/jukan05/status/2061045030387699909)

---

## 六、交易信号

| 标的 | 方向 | 逻辑摘要 | 来源 |
|------|------|----------|------|
| $MSFT | 看多 | AI PC 概念下周炒作，离新高仍有空间，可赌一波破新高 | [@hanking66](https://x.com/hanking66/status/2060950834163470703) |
| $AVGO | 看多 | 42 天盘整 MACD 金叉在即，成交量放大，财报超预期概率高 | [@ArtofSpecuycky · 5](https://x.com/ArtofSpecuycky/status/2060927433898070092) |
| $TTD | 短线看多 | CEO $25 附近买入 1.5 亿，当前 $21，死猫反弹目标 $30 | [@Mr_Derivatives](https://x.com/Mr_Derivatives/status/2060906681979277397) |
| $CRDO | 关注财报 | 周一盘后光模块 CPO 财报，叠加黄仁勋当日定调 | [@artinmemes · 1](https://x.com/artinmemes/status/2061037637310325246) |
| $HPE | 关注财报 | 周一盘后企业级 AI 服务器财报 | [@artinmemes · 2](https://x.com/artinmemes/status/2061037637310325246) |
| $PANW | 关注财报 | 周二盘后全球网安龙头财报 | [@artinmemes · 3](https://x.com/artinmemes/status/2061037637310325246) |
| $GTLB | 关注财报 | 周二盘后 AI 开发运维平台财报 | [@artinmemes · 4](https://x.com/artinmemes/status/2061037637310325246) |
| $CRWD | 关注财报 | 周三盘后 AI 网安 SaaS 财报，与 $AVGO 同日 | [@artinmemes · 5](https://x.com/artinmemes/status/2061037637310325246) |
| $QQQ / $IWM | 等回踩再加仓 | 六月上旬不追高，等回踩 749–750 再加仓；六月底 3–5% 回调是下半年最佳买点 | [@ArtofSpecuycky · 6](https://x.com/ArtofSpecuycky/status/2060927433898070092) |
| $SPY | 关注关键位 | 749 守住则多头逻辑延续；跌破 7400 下行超预期 | [@ArtofSpecuycky · 7](https://x.com/ArtofSpecuycky/status/2060927433898070092) |
| $NVDA / $INTC / $AMD | 看多 | Edge AI 三足鼎立，$NVDA 入局 AI PC 反而印证 $INTC/$AMD 逻辑 | [@TJ_Research](https://x.com/TJ_Research/status/2060877490634059980) |
| $AXTI / $SOI | 看多 | 供应链咽喉节点，机构关注度上升中 | [@aleabitoreddit](https://x.com/aleabitoreddit/status/2060896847695384736) |
| $SIVE | 谨慎 / 回避 | 阶段顶部 + 利空来袭，不适合高位布局 | [@SpermCapital · 4](https://x.com/SpermCapital/status/2060896454365818923) |

---

## 七、投资理念

- **咽喉节点理论**：在供应链博弈中，押注不可替代的关键节点（如特定规格 MLCC 原材料、稀有半导体衬底）往往比押注终端品牌更有效率。[@aleabitoreddit](https://x.com/aleabitoreddit/status/2060896847695384736)

- **设备与材料 > 生产商**：MLCC 扩产周期中，设备与原材料供应商的 CAPEX 受益早于且大于生产商本身，类似半导体设备在晶圆厂扩产中的逻辑。[@LucyBuilding · 3](https://x.com/LucyBuilding/status/2061060401421554147)

- **市场噪音识别**：当 X 平台上每个人都在用力喊自己的标的时，信息噪音极高，需提高独立判断权重，降低跟风冲动。[@WallStreet0Name](https://x.com/WallStreet0Name/status/2060959778135019706)

- **加密圈警示**：链上财富神话几乎全与操盘相关，项目方和 VC 口称 build 实则卖币，传统资金不会接这种盘。去中心化叙事已名存实亡。[@octopusycc](https://x.com/octopusycc/status/2061035654369423653)

- **定投纪律**：纳指周定投 20 年年化 9.2%–9.5%，胜在执行纪律而非择时，最大回撤 43.84% 提示需配合止盈策略，不能裸持。[@cnfinancewatch · 3](https://x.com/cnfinancewatch/status/2060888800046485906)

- **换机潮的真正驱动力是 OS 而非硬件**：AI PC 的核心变量是操作系统能否深度整合用户数据与跨应用工作流，Windows 目前仍不足，硬件先行不等于需求先行。[@LinQingV · 2](https://x.com/LinQingV/status/2060952328484929931)

## 最近 7 天

- [2026-05-31](digests/2026/05/31.md)
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

### @realDonaldTrump · 29 条

**核心观点**：特朗普当日推文聚焦政治攻防与个人形象，无直接股市相关内容

**情绪**：neutral

- 特朗普宣称在沃尔特里德军医中心体检结果极佳，认知测试四次满分30/30，呼吁所有总统及副总统候选人强制参加高难度认知测试 [原推](https://x.com/realDonaldTrump/status/truth_1780202129335032806)
- 特朗普猛烈抨击联邦法官Christopher Cooper叫停肯尼迪中心翻新工程，并要求摘除"特朗普"名字，指其妻Amy Jeffress存在利益冲突，扬言法官应被弹劾 [原推](https://x.com/realDonaldTrump/status/truth_1780181339409705238)
- 特朗普考虑取消周三典礼上的表演艺人，改由本人发表"美国回来了"主题演讲集会，称自己是全球最大的吸引力 [原推](https://x.com/realDonaldTrump/status/truth_1780156982401651987)
- USDA推动"棉花优先于化学品"政策，力推美国本土纺织业复兴 [原推](https://x.com/realDonaldTrump/status/truth_1780204097295237428)
- Dhillon申请佐治亚州选举诚信案法官回避，指该法官疑似出席过Fani Willis活动 [原推](https://x.com/realDonaldTrump/status/truth_1780204128801801850)
- 特朗普宣传与女儿媳Lara Trump的Fox News专访（晚9点），并推荐Mark Levin节目（晚8点） [原推](https://x.com/realDonaldTrump/status/truth_1780168656973302939)
- 特朗普展示白宫屋顶无人机停机坪及与英国国王查尔斯会面照片，并以中国"大礼堂"类比为白宫宴会厅辩护 [原推](https://x.com/realDonaldTrump/status/truth_1780174680962480321)
- 特朗普称林肯纪念堂与华盛顿纪念碑之间的倒影池修缮进展顺利，预计7月4日前完工，造价远低于前任政府 [原推](https://x.com/realDonaldTrump/status/truth_1780157542515888456)
- 特朗普批评纽约州长Kathy Hochul施政失败，为共和党候选人Bruce Blakeman站台 [原推](https://x.com/realDonaldTrump/status/truth_1780159556874036153)

### @SpermCapital · 17 条

**核心观点**：关注财报周科技股、无人机产业链、光子ETF及AI基础设施主题

**情绪**：neutral

- 6月财报周重点：周四 $AVGO、CrowdStrike、Palo Alto 盘前披露，消费零售 Dollar General、Victoria's Secret、Ulta Beauty 等陆续登场 ($AVGO) [原推](https://x.com/SpermCapital/status/2060983419316625436)
- 美国加速布局无人机产业，核心驱动：俄乌/中东战争验证低成本无人机价值、本土产能不足、财政优先级提升 [原推](https://x.com/SpermCapital/status/2060978472437096538)
- 美股首只纯光子产业链ETF $FOTO 上市，主动管理，前七大持仓含 $LITE、$IPGP、$COHR、$CIEN、$LASR、$FN、$AAOI，但混入工业/国防激光非AI赛道标的 ($FOTO, $LITE, $IPGP, $COHR, $CIEN, $LASR, $FN, $AAOI) [原推](https://x.com/SpermCapital/status/2060940467672322221)
- $DELL AI工厂架构解析，展示戴尔如何构建完整AI基础设施体系 ($DELL) [原推](https://x.com/SpermCapital/status/2060933182527041885)
- $Sive（Sivers Semiconductors）深度拆解：75年老牌瑞典半导体厂，毫米波射频起家，2017年收购英国CST Global后转型，当前处于阶段顶部且利空来袭，不适合高位布局 ($SIVE) [原推](https://x.com/SpermCapital/status/2060896454365818923)

### @jukan05 · 8 条

**核心观点**：高盛上调SK海力士与三星盈利预测，MLCC厂商转向份额优先策略，AI算力供应链景气持续

**情绪**：bullish

- 高盛大幅上调 $000660.KS SK海力士2026-2028年营业利润预测，2027年预测从261兆韩元上调至401兆韩元 ($000660) [原推](https://x.com/jukan05/status/2061045030387699909)
- 高盛同步上调 $005930.KS 三星电子2026-2028年营业利润预测，2028年预测从495兆韩元上调至610兆韩元 ($005930) [原推](https://x.com/jukan05/status/2061044139853283730)
- 村田制作所与Nippon Chemicon主动压缩利润率抢占MLCC低端市场份额以遏制中国竞争对手，MLCC设备与材料环节更值得关注 [原推](https://x.com/jukan05/status/2060963413430554713)
- 据GSR，超大规模云厂商向存储厂商支付15-30%预付款，微软已向 $005930.KS 三星预付高达100亿美元 ($005930) [原推](https://x.com/jukan05/status/2060958332966609060)
- $DELL 与 $NVDA 合作的首台Vera Rubin NVL72已在 $CRWV CoreWeave落地部署 ($DELL, $NVDA, $CRWV) [原推](https://x.com/jukan05/status/2060916762405974402)

### @BrianFeroldi · 5 条

**核心观点**：分享投资教育内容与经典投资人对话，无明确个股观点

**情绪**：neutral

- 推广免费投资信息图电子书，面向希望学习分析企业的投资者 [原推](https://x.com/BrianFeroldi/status/2061062792396808485)
- 分享 Warren Buffett 与 Peter Lynch 的对话视频，获得高互动（167赞/91转） [原推](https://x.com/BrianFeroldi/status/2061042378874486838)
- 再次推广免费投资信息图电子书，定位为教投资者分析企业 [原推](https://x.com/BrianFeroldi/status/2060957045084336605)
- 推广免费投资信息图电子书视觉内容 [原推](https://x.com/BrianFeroldi/status/2060941945073959363)
- 发布「8种股票投资风格」图解，获高互动（182赞/73转） [原推](https://x.com/BrianFeroldi/status/2060874984935878997)

### @cnfinancewatch · 5 条

**核心观点**：纳指周定投20年收益最优，A股存量博弈芯片算力将见顶，关注后续弱势板块轮动

**情绪**：neutral

- MLCC行业领先格局分析，涉及相关厂商竞争地位对比（原文为图表链接） [原推](https://x.com/cnfinancewatch/status/2060885177581314211)
- 量化回测纳斯达克20年定投：周定投收益最优，年化9.2%-9.5%，比月定投多盈利39万元；最大回撤43.84%，需配合止盈策略 [原推](https://x.com/cnfinancewatch/status/2060888800046485906)
- A股当前为存量资金博弈，芯片算力板块预计今年9-10月见顶；后续轮动方向依次为太阳能（隆基绿能）、太阳能电站（华电新能、三峡新能、龙源电力），以及AI终端应用标的海康威视、顺丰控股、东方财富、比亚迪、美的集团 [原推](https://x.com/cnfinancewatch/status/2060878463473697188)
- 哲学感慨：所谓自由正在戕害世界，让世界变成我们讨厌的样子 [原推](https://x.com/cnfinancewatch/status/2060902461259579703)
- 文章链接内容待读取，暂无法提取具体观点 [原推](https://x.com/cnfinancewatch/status/2061039595043873171)

### @hanking66 · 3 条

**核心观点**：AI PC概念下周将被炒作，$MSFT是最大受益者，可赌破新高

**情绪**：bullish

- AI PC深度思考：当本地模型足够聪明、OS完全迎合AI且软硬件全打通，可能催生全新形态PC和新一轮换机潮 [原推](https://x.com/hanking66/status/2061058956009812108)
- Vibe coding普及后重复造轮子问题严重，散户不需要懂PE/PEG/EBITDA，需要的是直接告诉买哪个；建议buy the dip长期持有 [原推](https://x.com/hanking66/status/2061009669297230170)
- 下周AI PC概念将被炒作，$MSFT是最大受益者，离新高还差很多，可赌一波破新高；虽然Mac软硬件领先$MSFT难以追上，但不影响股价趋势反转 ($MSFT) [原推](https://x.com/hanking66/status/2060950834163470703)

### @zephyr_z9 · 3 条

**核心观点**：华为混合键合技术领先，MLCC短缺仅限特定规格，半导体供应链格局生变

**情绪**：bearish

- MLCC短缺并非全面性，仅47μF与22μF规格供应紧张，市场存在误解 [原推](https://x.com/zephyr_z9/status/2061002229591740517)
- 华为2026年麒麟手机将采用1.5μm键合间距3D堆叠架构，2027年进一步缩至1μm；相比之下$TSM SoIC仍在6μm、2030年目标4.5μm，英特尔Foveros Direct为9μm，华为互连密度领先16-36倍 ($TSM) [原推](https://x.com/zephyr_z9/status/2060911676611018786)
- 表情包互动推文，无实质内容 [原推](https://x.com/zephyr_z9/status/2060929128438919454)

### @raycat2021 · 2 条

**核心观点**：当日内容与美股无关，均为流行文化与消费品话题

**情绪**：unclear

- 分享AC/DC经典摇滚《Highway to Hell》相关感慨，与市场无关 [原推](https://x.com/raycat2021/status/2061059805918507138)
- 斯沃琪与爱彼联名怀表Royal Pop遭哄抢，售价400-420美元，转售价高达3000美元 [原推](https://x.com/raycat2021/status/2060903897125060885)

### @TJ_Research · 2 条

**核心观点**：Edge AI赛道三家齐进，$NVDA入局反而印证$INTC和$AMD的AI PC逻辑

**情绪**：bullish

- 市场误判$NVDA做AI PC会利空$INTC/$AMD，实则三家可齐头并进，Edge AI推理不会全上云，所有电子产品将被重新定义 ($NVDA, $INTC, $AMD) [原推](https://x.com/TJ_Research/status/2060877490634059980)
- 非市场内容：作者发布希腊旅行动态 [原推](https://x.com/TJ_Research/status/2061051580351140295)

### @ArtofSpecuycky · 2 条

**核心观点**：五月九连阳后需冷静，守住标普749关键线，六月上旬仍有逼空但中旬风险最高

**情绪**：neutral

- 下周重点关注财报日历，包括 $AVGO 和 $CRWD 等，具体名单待披露 ($AVGO, $CRWD) [原推](https://x.com/ArtofSpecuycky/status/2061018073185091633)
- 标普749是六月开局核心锚点，守住则AI硬件向软件轮动逻辑延续；跌破7400则下行速度将超预期 ($SPY) [原推](https://x.com/ArtofSpecuycky/status/2060927433898070092)
- 期权结构发出警报：VIX远期溢价、$DSPX 创年内新高、3个月隐含相关性跌至2024年7月以来最低，底层脆弱性积累 ($VIX) [原推](https://x.com/ArtofSpecuycky/status/2060927433898070092)
- 六月月度波幅区间：$SPY 上沿782.05 / 下沿730.91；下周周度区间766.87 / 746.09，782附近是年度波幅极限，均值回归概率超68% ($SPY) [原推](https://x.com/ArtofSpecuycky/status/2060927433898070092)
- 6月12日SpaceX上市是流动性虹吸事件，叠加6月18日FOMC+OpEx，预计届时出现3-5%调整，六月底至七月初是下半年最佳加仓窗口 [原推](https://x.com/ArtofSpecuycky/status/2060927433898070092)
- $AVGO 盘整42天MACD即将金叉，成交量放大至平时两倍，财报若超预期将带动整条AI基础设施链 ($AVGO) [原推](https://x.com/ArtofSpecuycky/status/2060927433898070092)
- 席勒PE达42倍（仅次于2000年互联网泡沫），美元指数日线MACD死叉，比特币ETF持续净流出，多重宏观信号偏谨慎 ($BTC) [原推](https://x.com/ArtofSpecuycky/status/2060927433898070092)
- 操作思路：六月上旬不追高，等回踩749-750再加仓 $QQQ $IWM；六月中旬高位移动止盈；六月底3-5%回调是下半年最佳买点 ($QQQ, $IWM) [原推](https://x.com/ArtofSpecuycky/status/2060927433898070092)

### @nft_hu · 2 条

**核心观点**：AI数据中心驱动MLCC与功率半导体需求爆发，村田、太阳诱电及GaN厂商最受益

**情绪**：bullish

- AI数据中心48V/800V供电升级推动高压、超低ESL、高容值MLCC需求激增，村田制作与太阳诱电凭借BaTiO₃粉体及Core-Shell材料技术形成难以复制的竞争壁垒 [原推](https://x.com/nft_hu/status/2060989431352631615)
- 从B200到Feynman，单机架功率半导体含量从1.1万美元涨至19.1万美元（17倍），Rubin后进入指数增长；VRM+PSU约占七成是英飞凌核心阵地，IBC环节GaN占优，英诺赛科已与$NVDA达成800V直流架构合作并规模化交付 ($NVDA) [原推](https://x.com/nft_hu/status/2060963776418205762)

### @Mr_Derivatives · 2 条

**核心观点**：$TTD CEO大额自购支撑，短期死猫反弹至$30存在机会

**情绪**：bullish

- $TTD 当前价$21，CEO在$25附近公开市场买入$1.5亿股票，预计短期死猫反弹可看至$30，列入观察名单 ($TTD) [原推](https://x.com/Mr_Derivatives/status/2060906681979277397)

### @LucyBuilding · 1 条

**核心观点**：AI服务器驱动MLCC市场高速增长，设备与原材料供应商将超越MLCC生产商成最大受益者

**情绪**：bullish

- MLCC整体市场规模约150亿美元，AI服务器MLCC以80%+CAGR增长，通用服务器因AI Agent推动CPU需求也将加速（30-40% CAGR），但智能手机/移动端MLCC至少在2026-27年将负增长 [原推](https://x.com/LucyBuilding/status/2061060401421554147)
- MLCC涨价驱动因素：镍/银原材料成本上升、高端（高容高压）MLCC供需错配、交货期超20周，中国市场囤货与重复下单推动现货价格上涨20-40% [原推](https://x.com/LucyBuilding/status/2061060401421554147)
- Murata、Taiyo Yuden、SEMCO等一线厂商正快速扩产以服务AI服务器市场，Murata预计混合ASP持平；二三线及中国厂商将趁机扩张中低端市场（Macronix效应） [原推](https://x.com/LucyBuilding/status/2061060401421554147)
- MLCC生产设备与原材料供应商将是本轮CAPEX扩张最大受益者，预计其表现将超越MLCC生产商股票 [原推](https://x.com/LucyBuilding/status/2061060401421554147)

### @artinmemes · 1 条

**核心观点**：下周财报密集，AI芯片、光模块、网安、企业SaaS是核心看点

**情绪**：bullish

- 周一盘后关注光模块CPO标的 $CRDO 与企业级AI服务器 $HPE，叠加黄仁勋当日定调 ($CRDO, $HPE) [原推](https://x.com/artinmemes/status/2061037637310325246)
- 周二盘后重点：全球网安龙头 $PANW 与AI开发运维平台 $GTLB 双双报告 ($PANW, $GTLB) [原推](https://x.com/artinmemes/status/2061037637310325246)
- 周三盘后压轴：AI光互联龙头 $AVGO 博通、AI网安SaaS $CRWD CrowdStrike 及医疗云 $VEEV 集中登场 ($AVGO, $CRWD, $VEEV) [原推](https://x.com/artinmemes/status/2061037637310325246)
- 周四盘后看 $LULU、$DOCU、$IOT、$RBRK 等多赛道标的，周五非农收尾 ($LULU, $DOCU, $IOT, $RBRK) [原推](https://x.com/artinmemes/status/2061037637310325246)

### @octopusycc · 1 条

**核心观点**：加密圈充斥内幕操盘与割韭菜，区块链去中心化叙事已是虚伪

**情绪**：bearish

- 批评仍在鼓吹区块链去中心化的人非蠢即坏，认为币安、OKX等拥抱美股TradFi是务实而非背叛 [原推](https://x.com/octopusycc/status/2061035654369423653)
- 链上所谓财富神话几乎全与开盘子（操盘）相关，Trump之后的暴富几乎都是阴谋，内幕老鼠仓横行 [原推](https://x.com/octopusycc/status/2061035654369423653)
- 项目方和VC口称build实则疯狂卖币，做市商（MM）掏池子，传统资金不会接这种盘 [原推](https://x.com/octopusycc/status/2061035654369423653)

### @WallStreet0Name · 1 条

**核心观点**：市场噪音大，各方都在强推自己看好的标的

**情绪**：neutral

- 观察到X平台上每个人都在用力喊自己的标，暗示市场情绪嘈杂、信息噪音较高 [原推](https://x.com/WallStreet0Name/status/2060959778135019706)

### @LinQingV · 1 条

**核心观点**：N1X芯片PC出货约1000万台，但on-device AI驱动换机潮的关键仍是Windows系统支持而非硬件本身

**情绪**：neutral

- $NVDA N1X处理器供应链预测未来两年出货约1000万台，定位有需求的AI算力用户，仍属小众市场 ($NVDA) [原推](https://x.com/LinQingV/status/2060952328484929931)
- 2026年PC市场热点与on-device AI关系不大：MacBook Neo出货上调约100%（500万→1000万），买家看重的是价格、设计和生态，而非本地AI算力 [原推](https://x.com/LinQingV/status/2060952328484929931)
- 当前PC端AI使用主要依赖云端LLM服务（浏览器或API调用），核心算力在云端而非设备本地 [原推](https://x.com/LinQingV/status/2060952328484929931)
- on-device AI驱动换机潮的核心是OS支持：需要操作系统深度整合用户数据与跨应用工作流，Windows目前仍不足 [原推](https://x.com/LinQingV/status/2060952328484929931)
- $NVDA N1X设备可为AI重度用户提供媲美Mac的本地算力与大内存选项，但真正的换机周期取决于Windows的AI生态能否落地 ($NVDA) [原推](https://x.com/LinQingV/status/2060952328484929931)

### @cyrilxuq · 1 条

**核心观点**：作者认为市场对中概股的理解普遍不够深刻

**情绪**：unclear

- 作者表示看过许多人对中概股的评价，认为大家对中概股的理解仍不够深刻，但未展开具体观点 [原推](https://x.com/cyrilxuq/status/2060938381337768074)

### @insane_analyst · 1 条

**核心观点**：看多三星，看好其晶圆代工与DRAM部门的协同效应

**情绪**：bullish

- 考虑做多三星，看好Samsung Foundry与DRAM部门之间的协同效应及大量联合设计机会 ($005930.KS) [原推](https://x.com/insane_analyst/status/2060914252693770560)

### @aleabitoreddit · 1 条

**核心观点**：押注供应链咽喉节点，$AXTI/$SOI/$SIVE 或将载入史册

**情绪**：bullish

- 作者提出'咽喉节点投资理论'，认为从 $AXTI 到 $SOI 再到 $SIVE 的布局，正随路透社、机构及各国对供应链博弈的反应而得到验证 ($AXTI, $SOI, $SIVE) [原推](https://x.com/aleabitoreddit/status/2060896847695384736)

### @Remzztrades · 1 条

**核心观点**：作者利用周末备战未来数月重要行情机会，情绪积极备战

**情绪**：bullish

- 作者放弃休息、用周末备战未来数月行情，认为一次好的交易机会就能改变人生 [原推](https://x.com/Remzztrades/status/2060874577236889800)

</details>

## 历史归档

- [2026-05](digests/2026/05/)
