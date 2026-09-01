# DeepSeek V4 Flash / Pro 用于每日日报：官方型号、能力与价格核验

研究日期：2026-08-31；生产参数与价格复核：2026-09-01

证据范围：仅采用 DeepSeek 与 Anthropic 官方一手资料；DeepSeek 发布记录核验到 2026-08-21，价格与在线文档于 2026-08-31 首次访问，并于 2026-09-01 再次核验。未用第三方模型市场、媒体文章或聚合价目补充事实。

## 结论摘要

1. **`DeepSeek V4 Flash` 与 `DeepSeek V4 Pro` 都是官方型号，不是第三方平台杜撰的商品名。** DeepSeek 官方托管 API 的稳定调用 ID 分别是 `deepseek-v4-flash`、`deepseek-v4-pro`；截至研究日，它们分别指向 `DeepSeek-V4-Flash-0731` 与 `DeepSeek-V4-Pro-0813`。[D1][D5]
2. 两者均有 1M 上下文、最高 384K 输出，支持 thinking / non-thinking、JSON Output、工具调用、Responses API 与 Anthropic API。Flash 仍标为 API public beta；Pro 0813 已 GA，并在 App、Web、API 可用。[D1][D2][D4]
3. 本项目正常在北京时间 20:30 运行，即 12:30 UTC。DeepSeek 官方工作日峰时为 01:00–04:00、06:00–10:00 UTC，其余时间及周末均为 off-peak，因此正常日报预计适用低峰价。[D1]
4. 按官方目录单价、且按相同计费 token 数比较，正常低峰时：
   - Flash 相对 Anthropic 官方 Sonnet 4.6 标准价：缓存未命中输入便宜约 92.7%，输出便宜约 95.6%，缓存命中输入便宜约 97.7%。
   - Pro：缓存未命中输入便宜 78.0%，输出便宜 86.8%，缓存命中输入便宜约 92.7%。
5. **这些倍率不能直接等同于本项目真实账单节省。** 2026-08-31 比较时的 Claude 基线通过多个 Anthropic-compatible 第三方代理调用 `claude-sonnet-4-6`，Anthropic 官方标准价不代表这些代理的实际费率；项目于 2026-09-01 切换为 DeepSeek 首选后，Claude 仅作降级备用。此外，tokenizer、缓存命中率、thinking 产生的额外 token 与重试次数都会改变实际成本。[D6][D9][D12][A2]
6. 官方资料没有“中文美股 KOL 每日总结、归因正确率、ticker 对齐、来源链接保真”这类直接 benchmark，也没有与本项目 Claude 链路的同批盲测。厂商自报通用、长上下文和 Agent benchmark 只能说明候选能力，不能证明日报效果。实际效果必须用同一批历史推文做 A/B。
7. **2026-09-01 价格复核未发现变更。** V4 Pro 仍为缓存命中输入 `$0.022/$0.044`、缓存未命中输入 `$0.66/$1.32`、输出 `$1.98/$3.96`（off-peak/peak，均为每百万 token）。官方单次最大输出仍标为 384K；项目把请求的 `max_tokens` 设为 `384000` 只是放宽生成上限，并不会按 384K 预扣费用，仍按响应 `usage` 中实际生成量计费。官方页面没有把 “K” 展开成精确整数，`384000` 是项目采用的十进制解释，不应写成官方逐字承诺。[D1][D12][D13]

## 1. 官方型号、API 别名与可用性

| 层级 | Flash | Pro | 含义 |
|---|---|---|---|
| 官方产品名 | DeepSeek V4 Flash | DeepSeek V4 Pro | 官方产品系列名称 [D3] |
| 当前具体版本 | `DeepSeek-V4-Flash-0731` | `DeepSeek-V4-Pro-0813` | 当前 checkpoint / 版本名 [D1][D5] |
| 官方托管 API ID | `deepseek-v4-flash` | `deepseek-v4-pro` | `api.deepseek.com` 的稳定滚动调用 ID [D1][D5] |
| 官方 Hugging Face 仓库 | `deepseek-ai/DeepSeek-V4-Flash-0731` | `deepseek-ai/DeepSeek-V4-Pro` | 官方账号下的开源权重/模型卡标识，不是托管 API 的 `model` 参数 [D10][D11] |
| 发布状态 | 0731 为正式 checkpoint；API public beta | 0813 GA | Flash 2026-07-31 更新；Pro 2026-08-13 GA [D2][D4][D11] |
| 官方服务可用性 | API | App、Web、API | 以官方发布页措辞为准 [D2][D4] |

官方当前还列出独立的实验视觉型号 `deepseek-v4-flash-vision-exp`；它不是纯文本 `deepseek-v4-flash` 的同义词。[D1][D5]

旧 ID `deepseek-chat` 与 `deepseek-reasoner` 已在 2026-07-24 退役，不应作为当前 V4 的正式调用方式。[D2][D3]

### 如何识别第三方商品名

第三方平台即使展示“DeepSeek V4 Flash / Pro”，也只能说明其商品标签引用了官方产品名，不能据此推断：

- endpoint 是 DeepSeek 官方 `https://api.deepseek.com`；
- `model` 别名一定映射到 0731 / 0813；
- 价格、缓存、限流与 DeepSeek 官方一致；
- 更新节奏与官方托管 API 同步。

因此，本文价格只适用于 DeepSeek 官方托管 API。第三方平台价格和实际版本必须向该平台单独核验，不能混写为“DeepSeek 官方价”。[D1][D5]

## 2. 官方规格与目录价格

所有价格均为美元 / 100 万 token。[D1]

| 项目 | `deepseek-v4-flash` | `deepseek-v4-pro` |
|---|---:|---:|
| 当前版本 | DeepSeek-V4-Flash-0731 | DeepSeek-V4-Pro-0813 |
| 上下文 | 1M | 1M |
| 最大输出 | 384K | 384K |
| thinking 模式 | thinking / non-thinking；默认 thinking | thinking / non-thinking；默认 thinking |
| 默认 thinking effort | high | high |
| 缓存命中输入，off-peak | $0.007 | $0.022 |
| 缓存命中输入，peak | $0.014 | $0.044 |
| 缓存未命中输入，off-peak | $0.22 | $0.66 |
| 缓存未命中输入，peak | $0.44 | $1.32 |
| 输出，off-peak | $0.66 | $1.98 |
| 输出，peak | $1.32 | $3.96 |
| 官方并发上限 | 2500 | 500 |
| JSON Output / Tool Calls | 支持 | 支持 |
| Responses API / Anthropic API | 支持 | 支持 |

峰时规则为周一至周五 01:00–04:00、06:00–10:00 UTC；off-peak 价格是 peak 的 50%。周末全天及工作日其他时段均为 off-peak。[D1]

项目的 20:30 Asia/Shanghai 等于 12:30 UTC，落在 off-peak。只有手工补跑或改调度后进入上述窗口，才应按 peak 价估算。

## 3. 与当前 Sonnet 4.6 官方标准价对比

### 3.1 Anthropic 官方基线

截至 2026-08-31，Anthropic 官方将 Claude Sonnet 4.6 标为 **Legacy，但仍 Active / available**；模型 ID 是 `claude-sonnet-4-6`，发布日期 2026-02-17，承诺不早于 2027-02-17 退役。[A1][A4]

| 项目 | Claude Sonnet 4.6 官方 Claude API |
|---|---:|
| 上下文 | 1M |
| 同步 Messages API 最大输出 | 128K |
| Message Batches beta 最大输出 | 300K |
| 标准输入 | $3 / MTok |
| 5 分钟缓存写入 | $3.75 / MTok |
| 1 小时缓存写入 | $6 / MTok |
| 缓存读取 / refresh | $0.30 / MTok |
| 标准输出 | $15 / MTok |

上述是 Anthropic 官方 Claude API 的公开标准价，不是项目 Claude 降级代理链路的账单价。[A1][A2]

### 3.2 正常日报时段的单价倍率

本表按 12:30 UTC 的 DeepSeek off-peak 价格计算，并假设比较的是相同数量的各自计费 token。

| 计费项 | Sonnet 4.6 官方价 | Flash off-peak | 相对 Sonnet | Pro off-peak | 相对 Sonnet |
|---|---:|---:|---:|---:|---:|
| 缓存未命中输入 | $3.00 | $0.22 | 便宜 92.7%；Sonnet 为 13.64 倍 | $0.66 | 便宜 78.0%；Sonnet 为 4.55 倍 |
| 输出 | $15.00 | $0.66 | 便宜 95.6%；Sonnet 为 22.73 倍 | $1.98 | 便宜 86.8%；Sonnet 为 7.58 倍 |
| 缓存命中输入 | $0.30 | $0.007 | 便宜 97.7%；Sonnet 为 42.86 倍 | $0.022 | 便宜 92.7%；Sonnet 为 13.64 倍 |

若输入均为缓存未命中，令每日输入为 `I` MTok、输出为 `O` MTok，目录价估算式为：

```text
Anthropic Sonnet 4.6 标准价 = 3.00 × I + 15.00 × O
DeepSeek V4 Flash off-peak   = 0.22 × I + 0.66 × O
DeepSeek V4 Pro off-peak     = 0.66 × I + 1.98 × O
```

但不能把式中 Sonnet 结果当作项目 Claude 降级时的真实费用：该代理链路并非已确认按 Anthropic 官方价结算。

### 3.3 为什么账单节省不会机械等于单价节省

- DeepSeek 官方说明不同模型 tokenization 方法不同，应以响应 `usage` 为准，同一文本未必产生相同 token 数。[D12]
- DeepSeek 默认启用 high thinking；推理内容会增加延迟，并可能增加输出计费量。[D6]
- DeepSeek 缓存是自动、best-effort 的前缀缓存，不保证 100% 命中；日报每天的推文正文变化很大，不能先验按全量缓存价预算。[D9]
- 项目有多后端 fallback 和重试；失败调用、重试及不同后端的真实费率都会影响账单。
- Anthropic 官方缓存价包含显式 cache write/read 机制，而 DeepSeek Anthropic-compatible 接口明确忽略 `cache_control`，两者缓存语义不完全相同。[D8][A2]

## 4. 预期效果：官方证据能说明什么

### 4.1 能确认的能力适配

- **容量不是瓶颈。** 两个 DeepSeek 型号均为 1M 上下文、官方标称 384K 最大输出；相对 Sonnet 4.6 的 1M / 128K 同步规格，DeepSeek 有更高理论输出上限。项目已于 2026-09-01 按十进制解释把 DeepSeek Layer 1/2 的请求上限提升到 `384000`，但实际日报通常会自行提前结束，不等于每次生成 384K。[D1][D13][A1]
- **结构化输出可用。** 两者官方均支持 JSON Output；但 DeepSeek 文档同时提示 JSON Output 偶尔可能返回空内容，仍需保留当前解析、重试和本地兜底。[D1][D7]
- **复杂度可调。** 两者支持 non-thinking、low、high、max；默认 thinking=high。官方建议 low 用于简单任务，high 用于日常 Agent 工作流，max 用于复杂任务。[D4][D6]
- **长上下文与事实问答有厂商自报数据。** DeepSeek 官方模型卡给出了 1M 长上下文、英文/中文 SimpleQA 等指标，可用于比较 Flash 与 Pro 的方向性差异。[D10]

### 4.2 DeepSeek 官方自报 benchmark：只作方向参考

以下来自 DeepSeek 官方 Hugging Face 模型卡的 “Comparison across Modes”。这些是厂商自报结果，不是独立第三方复测，也不是本项目日报 benchmark。[D10]

| 指标 | Flash High | Pro High | Flash Max | Pro Max | 可谨慎观察到的方向 |
|---|---:|---:|---:|---:|---|
| SimpleQA-Verified Pass@1 | 28.9 | 46.2 | 34.1 | 57.9 | Pro 明显更高 |
| Chinese-SimpleQA Pass@1 | 73.2 | 77.7 | 78.9 | 84.4 | Pro 更高 |
| MRCR 1M MMR | 76.9 | 83.3 | 78.7 | 83.5 | Pro 更高 |
| CorpusQA 1M ACC | 59.3 | 56.5 | 60.5 | 62.0 | High 下 Flash 略高，Max 下 Pro 略高 |
| Terminal Bench 2.0 ACC | 56.6 | 63.3 | 56.9 | 67.9 | Pro 更高 |
| Toolathlon Pass@1 | 43.5 | 49.0 | 47.8 | 51.8 | Pro 更高 |

这些数据支持“Pro 是更保守的质量候选、Flash 是更低成本候选”的初步判断，但不能推出以下结论：

- Pro 一定比当前 Sonnet 4.6 日报更准；
- Flash 一定能保持当前中文表达、归因和来源链接质量；
- 通用事实问答分数能代表 ticker / 数字 / KOL 归因正确率；
- Agent 或代码 benchmark 能代表摘要可读性。

### 4.3 官方产品定位

DeepSeek 官方把 Flash 描述为更小、更快、更经济，推理能力接近 Pro，并称其在简单 Agent 任务上与 Pro 相当；Flash 0731 又重点增强了 Agent 能力。Pro 则被定位为更强世界知识、推理和复杂 Agent 能力，0813 GA 特别强调生产环境提升。[D3][D4][D11]

Anthropic 对 Sonnet 4.6 的官方定位包括 coding、computer use、long-context reasoning、agent planning、knowledge work 与 design；发布说明还强调 instruction following、较少 hallucination、文档理解，并称早期客户反馈中 financial analysis 表现突出。[A3] 但这些也是厂商自报，且与 DeepSeek 模型卡并非同一套评测，不能直接横向排位。

### 4.4 对本项目的审慎预期

- **V4 Flash：** 成本优势最大、官方并发更高，但仍是 public beta；在官方自报事实问答和长上下文表中通常低于 Pro。若日报最关心“便宜且可接受”，它适合作为先测候选，不宜未经盲测直接全量替换。
- **V4 Pro：** 仍显著便宜于 Anthropic 官方 Sonnet 4.6 标准价，且 GA、官方自报事实问答和多数长上下文指标更强。若更重视数字/ticker 归因与稳定性，它是更合理的第一候选；但仍没有证据证明可保持当前日报质量。
- **当前 Sonnet 4.6：** 官方已归为 legacy，但仍 Active；Anthropic 官方对 instruction following、文档理解与 financial analysis 有较直接的产品声明。它是本项目已经运行并积累质量修复经验的基线，切换成本不只在 API 兼容，还包括提示词、清洗器和质量门控的重新校准。

## 5. 迁移时的 API 与参数陷阱

### 5.1 Anthropic-compatible endpoint

DeepSeek 官方 Anthropic API base URL 是：

```text
https://api.deepseek.com/anthropic
```

可继续使用 Anthropic SDK，并把 `model` 设为 `deepseek-v4-flash` 或 `deepseek-v4-pro`。[D8]

DeepSeek 官方兼容页还规定：

- 传入以 `claude-opus` 开头的模型名，会映射到 `deepseek-v4-pro`；
- 传入以 `claude-haiku` 或 `claude-sonnet` 开头的模型名，会映射到 `deepseek-v4-flash`；
- 其他不支持的模型名会自动映射到 `deepseek-v4-flash`。[D8]

因此，如果只把本项目 base URL 改成 DeepSeek、仍传当前 `claude-sonnet-4-6`，官方规则会调用 **Flash**，不会调用 Pro。要明确使用 Pro，应把项目模型值改为 `deepseek-v4-pro`。

### 5.2 默认 high thinking 会改变现有行为

2026-08-31 迁移前，项目普通 Claude 后端请求传 `temperature=0.3`，但不显式传 `thinking`。DeepSeek 官方则默认启用 thinking，默认 effort=high；在 thinking 模式下 `temperature`、`top_p`、`presence_penalty`、`frequency_penalty` 均无效。[D6]

所以“只改 base URL 和 model”并不等价于保持当前生成方式：

- 延迟可能增加；
- reasoning/output token 可能增加；
- `temperature=0.3` 不再起预期作用；
- 质量与成本都必须重新测量。

若要先复刻当前偏确定性的非 thinking 行为，应在 Anthropic Messages 请求中显式传 `thinking: {"type": "disabled"}`；若要利用 DeepSeek thinking，则应显式决定 low/high/max 并为每档记录延迟、输出 token 和质量。[D6][D8]

### 5.3 缓存机制并非 Anthropic prompt caching 的直接替代

DeepSeek Context Caching 默认自动开启；命中需要后续请求完整复用已持久化的前缀单元，响应 `usage` 会返回 `prompt_cache_hit_tokens` 与 `prompt_cache_miss_tokens`。缓存为 best-effort，构建需时间，闲置后会清除，不能保证命中。[D9]

同时，DeepSeek Anthropic-compatible 文档把 content/tool block 的 `cache_control` 标为 ignored。[D8] 因此迁移后应以 DeepSeek usage 字段实测命中率，不能沿用 Anthropic 显式 cache_control 的成本假设。

## 6. 建议的项目 A/B 判定方式

官方资料只能确认“可调用、容量足够、目录价低、具备结构化输出”，不能确认日报效果。建议用相同历史数据、冻结提示词和清洗逻辑，至少比较：

1. Sonnet 4.6 当前链路；
2. V4 Flash non-thinking 与 high；
3. V4 Pro non-thinking 与 high。

核心人工盲测项应是：数字/ticker/KOL 归因、遗漏率、无来源断言、链接保真、中文可读性、JSON 可解析率、质量门控触发率；同时记录输入/输出/reasoning token、cache hit/miss、端到端耗时和重试率。只有这组同源数据才能回答“效果比目前如何”和“真实每天省多少钱”。

## 7. 2026-09-01：Think Max、最大输出与计费复核

### 7.1 官方 `384K`、项目 `384000` 与 Think Max 分别控制什么

DeepSeek 官方规格页仍列出 1M 上下文与 “384K” 最大输出，但没有说明这里的 K 应展开为 `384000` 还是 `393216`。项目目前采用十进制解释 `max_tokens=384000`；该精确整数是项目设置，不是官方页面逐字给出的数值。Chat Completions API 对 `max_tokens` 的定义是“本次最多可生成的 token 数”，同时说明输入 token 与生成 token 的总长度不能超过模型上下文。因此：[D1][D13]

- `max_tokens=384000` 是项目按官方 “384K” 规格选择的单次生成上限，不是目标输出长度，也不是预购额度；
- 1M 上下文仍约束 `输入 + 生成` 的总量，输入越长，实际可用输出空间越少；
- 模型正常完成时会早于上限停止，账单只按实际 `usage` 扣费；
- 若命中 `stop_reason=max_tokens` / `finish_reason=length`，响应可能被截断，项目应继续把它视为不完整，而不是接受残缺 JSON 或报告。[D13]

Anthropic-compatible API 对 `thinking`、`output_config` 与 `max_tokens` 的支持语义不同：[D6][D8]

```python
thinking={"type": "enabled"}
output_config={"effort": "max"}
max_tokens=384000
```

- `thinking.enabled` 开启思考模式；默认其实也是开启，但显式传递可以固定生产行为；
- `output_config.effort=max` 选择官方最高实际推理等级；`medium`、`high`、`xhigh` 都映射为 high，只有 `max` 映射为 max；
- `effort=max` 不是 384K token 预算，也不保证消耗完上限；它控制模型投入的推理强度；
- DeepSeek 的 Anthropic 兼容层会忽略 `thinking.budget_tokens`，所以不能用 Anthropic 的 `budget_tokens` 精确切分“思考”和“正文”；
- thinking 模式下 `temperature`、`top_p`、`presence_penalty`、`frequency_penalty` 均无效，兼容层可能接受这些字段但不会生效。[D6][D8]

官方 OpenAI 格式响应把 `reasoning_tokens` 列在 `completion_tokens_details` 下，而总生成量记录为 `completion_tokens`；价格页没有给思考 token 单独折扣，而是按总输出 token 定价。因此预算时应把思考与最终正文都视为输出计费量，不能只数最终 Markdown/JSON 的可见 token。[D1][D13]

### 7.2 2026-09-01 V4 Pro 官方价格：无变化

截至 2026-09-01 再次访问官方价格页，V4 Pro 单价与 2026-08-31 记录完全一致，单位均为美元 / 100 万 token：[D1]

| 计费项 | Off-peak | Peak |
|---|---:|---:|
| 缓存命中输入 | $0.022 | $0.044 |
| 缓存未命中输入 | $0.66 | $1.32 |
| 输出（含 thinking 产生的生成量） | $1.98 | $3.96 |

工作日 01:00–04:00、06:00–10:00 UTC 为 peak，其余工作日时段和周末全天为 off-peak。项目北京时间 20:30 的正常调度对应 12:30 UTC，因此仍落在 off-peak。[D1]

`max_tokens` 拉到 384K 不会直接增加一次正常完成请求的费用。单次请求的实际官方费用公式是：

```text
V4 Pro off-peak = 缓存命中输入 MTok × 0.022
                + 缓存未命中输入 MTok × 0.66
                + 实际输出 MTok × 1.98

V4 Pro peak     = 缓存命中输入 MTok × 0.044
                + 缓存未命中输入 MTok × 1.32
                + 实际输出 MTok × 3.96
```

按项目采用的十进制 `384000` 计算，极端情况下若单次响应真的生成满，仅输出费用约为 `$0.76032`（off-peak）或 `$1.52064`（peak）。若再假设 1M 也按十进制解释，同一请求把剩余约 616K 全部用作缓存未命中输入，则单请求输入加输出理论上界约为 `$1.16688`（off-peak）或 `$2.33376`（peak）。这是便于预算的容量上界，不是官方保证的精确极限，也不是正常日报预测；真实预算必须汇总每个 Layer 2、修复/翻译重试和 Layer 1 响应的实际 usage。

### 7.3 自动缓存的计费边界

DeepSeek Context Caching 对所有用户默认开启，不要求代码显式创建缓存。命中要求后续请求完整匹配已落盘的缓存前缀单元；系统是 best-effort，不保证 100% 命中，构建需要时间，闲置缓存通常会在数小时到数天内清除。[D9]

响应 usage 提供：

- `prompt_cache_hit_tokens`：按缓存命中输入价计费；
- `prompt_cache_miss_tokens`：按缓存未命中输入价计费；
- 二者之和构成输入 token；输出仍重新推理生成，不因输入缓存命中而免收输出费。[D9][D13]

DeepSeek Anthropic-compatible 接口会忽略消息或工具块中的 `cache_control`，因此不能把 Anthropic 的显式 prompt caching 写入/读取规则直接套用过来。应以 DeepSeek 返回的 hit/miss usage 为账单依据。[D8][D9]

### 7.4 本项目 Think Max 实测费用估算

2026-09-01 用 2026-08-31 真实推文做了 Think Max 隔离样本测试，请求均使用官方 `deepseek-v4-pro`、`effort=max`、off-peak 价格。这些是单次模型输出，会因模型随机性、推文内容和质量修复重试而变动：

| 样本 | 推文数 | 实际输出 token（reasoning + 正文） | 耗时 | 单请求 off-peak 费用 |
|---|---:|---:|---:|---:|
| `zephyr_z9` | 1 | 2,380 | 48 秒 | 约 $0.0056 |
| `cyrilxuq` | 3 | 5,916 | 119 秒 | 约 $0.0127 |
| `aleabitoreddit` | 8 | 18,906 | 306 秒 | 约 $0.0393 |
| `cnfinancewatch` | 16 | 20,618 | 326 秒 | 约 $0.0411 |
| `realDonaldTrump` | 19 | 17,704 | 334 秒 | 约 $0.0378 |
| `blazingbees` | 28 | 13,078 | 234 秒 | 约 $0.0289 |
| 整期 Layer 1 | 31 个 KOL 的 Layer 2 JSON | 18,664 | 275 秒 | 约 $0.0538 |

用 8/31 当天 31 个活跃 KOL、165 条推文的活跃度分布外推，并将当天 non-thinking 提示输入量 88,372 token 作为输入基准：

| 估算口径 | 单期 off-peak | 30 期 | 365 期 |
|---|---:|---:|---:|
| 样本中位放大倍数 | 约 $0.57 | 约 $17.16 | 约 $208.79 |
| 按 KOL 推文数最近样本加权 | 约 $0.62 | 约 $18.52 | 约 $225.37 |
| 样本 75 分位放大倍数 | 约 $0.80 | 约 $24.00 | 约 $292.06 |

因此正常生产预算可按 **$0.57–$0.80/期、$17–$24/30 期** 估算；考虑来源/ticker 修复重试、偶发降级和模型波动，建议为该日报预留 **$20–$30/月**。输入缓存只会小幅改变这个结果，因为 Think Max 下输出费用是主要部分。

384K 拉满时的纯容量极端上界不应当作日常预算：8/31 当天有 31 个 Layer 2 请求 + 1 个 Layer 1，若 32 个请求每个都真正输出满 384,000 token，仅输出费就约为 **$24.33/期 off-peak** 或 **$48.66/期 peak**，30 期 off-peak 约 $729.91。实测单请求为 2,380–20,618 token，与 384K 上限相差一个数量级以上。

按上述样本耗时和 Layer 2 并发 4 外推，正常整期约 **24 分钟**；实际受最慢请求、重试和 provider 排队影响，建议运维上按 25–45 分钟观察窗口判断，不要在 5 分钟级单请求运行时误判为卡死。

### 7.5 人民币换算与本次实测支出

人民币换算采用中国外汇交易中心 2026-09-01 09:15 公布的人民币汇率中间价：**1 美元 = 6.7809 元人民币**。下表是 API usage 可明确计算的 Think Max / 384K 参数验证请求，均按 off-peak 价格换算；银行卡或充值渠道的实际结算会有少量点差。[D14]

| 测试 | 实际输出 token | 美元 | 人民币 |
|---|---:|---:|---:|
| Max 参数预检 | 65 | $0.000203 | 约 ¥0.0014 |
| 高负载 Layer 2，5K 截断 | 5,000 | $0.016149 | 约 ¥0.1095 |
| 高负载 Layer 2，16K 截断 | 16,000 | $0.031967 | 约 ¥0.2168 |
| 高负载 Layer 2，64K 完整返回 | 20,618 | $0.041111 | 约 ¥0.2788 |
| 整期 Layer 1，64K 完整返回 | 18,664 | $0.053772 | 约 ¥0.3646 |
| 384K 接口接受性小测 | 54 | $0.000179 | 约 ¥0.0012 |
| `zephyr_z9` Layer 2 | 2,380 | $0.005547 | 约 ¥0.0376 |
| `cyrilxuq` Layer 2 | 5,916 | $0.012723 | 约 ¥0.0863 |
| `aleabitoreddit` Layer 2 | 18,906 | $0.039315 | 约 ¥0.2666 |
| `realDonaldTrump` Layer 2 | 17,704 | $0.037751 | 约 ¥0.2560 |
| `blazingbees` Layer 2 | 13,078 | $0.028876 | 约 ¥0.1958 |
| **上述请求合计** | — | **$0.267592** | **约 ¥1.8145** |

按同一汇率，正常生产估算的 $0.57–$0.80/期约为 **¥3.87–¥5.42/期**，$17–$24/30 期约为 **¥115–¥163/月**；连同重试和波动的建议预算 $20–$30/月约为 **¥136–¥203/月**。理论极端的 $24.33/期约为 ¥164.98/期，不是日常预测。

## 官方来源

所有链接首次访问日期均为 2026-08-31；其中 [D1]、[D6]、[D8]、[D9]、[D12]、[D13] 于 2026-09-01 再次核验。

- [D1] DeepSeek API Docs, Models & Pricing: https://api-docs.deepseek.com/quick_start/pricing
- [D2] DeepSeek API Docs, Change Log: https://api-docs.deepseek.com/updates/
- [D3] DeepSeek, DeepSeek V4 Preview Release (2026-04-24): https://api-docs.deepseek.com/news/news260424
- [D4] DeepSeek, DeepSeek-V4-Pro GA Release (2026-08-13): https://api-docs.deepseek.com/news/news260813
- [D5] DeepSeek API Docs, Your First API Call / current model list: https://api-docs.deepseek.com/
- [D6] DeepSeek API Docs, Thinking Mode: https://api-docs.deepseek.com/guides/thinking_mode
- [D7] DeepSeek API Docs, JSON Output: https://api-docs.deepseek.com/guides/json_mode
- [D8] DeepSeek API Docs, Using the Anthropic API: https://api-docs.deepseek.com/guides/anthropic_api
- [D9] DeepSeek API Docs, Context Caching: https://api-docs.deepseek.com/guides/kv_cache
- [D10] DeepSeek official Hugging Face, DeepSeek-V4-Pro model card: https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/main/README.md
- [D11] DeepSeek official Hugging Face, DeepSeek-V4-Flash-0731 model card: https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731/blob/main/README.md
- [D12] DeepSeek API Docs, Token & Token Usage: https://api-docs.deepseek.com/quick_start/token_usage
- [D13] DeepSeek API Reference, Chat Completions API: https://api-docs.deepseek.com/api/create-chat-completion
- [D14] 中国外汇交易中心，人民币汇率中间价（2026-09-01 09:15）: https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json
- [A1] Anthropic, Claude Sonnet 4.6 model page: https://platform.claude.com/docs/en/models/sonnet-4-6/overview.md
- [A2] Anthropic, API Pricing: https://platform.claude.com/docs/en/about-claude/pricing
- [A3] Anthropic, Introducing Claude Sonnet 4.6 (2026-02-17): https://www.anthropic.com/news/claude-sonnet-4-6
- [A4] Anthropic, Model deprecations / lifecycle status: https://platform.claude.com/docs/en/about-claude/model-deprecations.md
