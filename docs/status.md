# 项目状态

> 这份文档回答：项目现在在哪一步、下一步做什么、有什么阻塞。每次会话结束时由 agent 更新。

**最后更新：** 2026-10-05
**当前阶段：** P2 — 个人局内数据收集工具（P2-T0…T3 任务已完成；P2 **退出标准**仍差连续 10 局团子配对样本）

## 最近完成

- **插件 0.2.0 首局验收**（2026-10-05）：`20261005_104908_ed11e0`（伊利丹，第 5 名，12 回合）。`pluginVersion=0.2.0`，`records.jsonl.gz` 已压；ready **12/12**、团子对照 **12/12**、重放 3σ **12/12**。匿名化未误伤 `$type`/`Player`/`Windfury`/`ControlledByPlayer`。团子配对样本 **6/10**。见 [`worklog/2026-10-05-plugin-020-first-game.md`](worklog/2026-10-05-plugin-020-first-game.md)。
- **P2-T3 离线导入与质量报告**（2026-10-05）：`tools/standard_layer` 产出每回合 JSONL + 质量报告；战果来源 `tuanzi`/`hdt`/`lb`；可选 `--replay`。本机 52 局 609 回合 ready **99.0%**；团子配对 5 局 ready **93.1%**、对照 **54/54**、重放 3σ **54/54**。见 [`facts/standard-layer-import.md`](facts/standard-layer-import.md)、[`worklog/2026-10-05-p2t3-standard-layer.md`](worklog/2026-10-05-p2t3-standard-layer.md)。分支 `feat/P2-T3-offline-import`。
- **P2-T2 诊断插件转正**（2026-10-05）：`HdtDiagLogger` **0.2.0**——匿名化词边界 + BB 结构保留名；局末 `records.jsonl.gz`；`tools/diag_io.py`。见 [`design/P2-data-capture.md`](design/P2-data-capture.md) §8、[`worklog/2026-10-05-p2t2-diag-plugin.md`](worklog/2026-10-05-p2t2-diag-plugin.md)。
- **P2-T1 短方案 + ADR**（2026-10-05）：[`design/P2-data-capture.md`](design/P2-data-capture.md) approved；ADR-0004 / ADR-0010 accepted。
- **P2-T0 离线重放与往返验证**（2026-10-05）：261/261 场五率往返通过。见 [`facts/replay-roundtrip.md`](facts/replay-roundtrip.md)。

## 进行中

无。

## 下一步（按优先级）

1. **agent：P3-T0 核心假设早期验证**（依赖 P2-T0✓、P2-T3✓）：用 `data/standard/turns.jsonl` 的 `ready` 行；建议先用 BB 1.85.0 队列做全交叉模拟，再扩到全量。
2. **所有者：** 继续按 [`process/field-capture.md`](process/field-capture.md) 用团子版 + **0.2.0** 采集，把新局 `BgHelperDiag/<id>` + 当日对战记录带回；再凑 **4** 局配对即可满连续 10 局以正式满足 P2 退出标准。合并/验收分支：`feat/P2-T2-diag-plugin-patches`、`feat/P2-T3-offline-import`。

## 待决事项默认值（所有者未否决即按此执行）

| 事项 | 默认值 |
| --- | --- |
| Q-008 对局频率 | 按每周约 15–20 局规划（活跃期实测约 77 局/月；本批 7 天 48 局更高）。只用自己的数据，不引入外部数据补充 |
| Q-009 耗时标准 | **已关闭**：赛后后台每局全部回合 ≤ 10 分钟；实测每局模拟合计 ≪ 该预算。局内实时预算留到 P4-T1 |
| Q-005 CI 与托管 | 暂不做 CI，只在本机构建；托管等需要时再定 |
| 个人采集环境 | **团子版 + 对战记录对照**（ADR-0008）。插件语义仍以官方为准；允许拔线，战果由上下文还原（ADR-0009） |
| ADR-0004 / ADR-0010 | **已接受**（P2-T1，2026-10-05） |
| `ready` 与清单盲区 | 未知手牌 / Input 中 `2717` 恒 0 等记入 `gapFlags`，不单凭此降为 `partial`（P2-T3 实现记录） |

## 阻塞 / 需要所有者决定

- 无硬阻塞。P2 退出标准差「连续 10 局」团子样本；不同意 `ready` 默认值时直接说即可。
