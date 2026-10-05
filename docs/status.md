# 项目状态

> 这份文档回答：项目现在在哪一步、下一步做什么、有什么阻塞。每次会话结束时由 agent 更新。

**最后更新：** 2026-10-05
**当前阶段：** P2 — 个人局内数据收集工具（P1 已完成；P2-T0 / P2-T1 / P2-T2 已完成）

## 最近完成

- **P2-T2 诊断插件转正**（2026-10-05）：`HdtDiagLogger` **0.2.0**——匿名化词边界 + BB 结构保留名（不再误伤 `Player` / `$type` / `ControlledByPlayer` / `Windfury`）；局末 `records.jsonl.gz`；`tools/diag_io.py` 与各评估脚本同时认 `.jsonl` / `.gz`。DumpTest + `check_capture` 通过。未做可选的 `2717` / `hearthstoneBuild`。见 [`design/P2-data-capture.md`](design/P2-data-capture.md) §8、[`worklog/2026-10-05-p2t2-diag-plugin.md`](worklog/2026-10-05-p2t2-diag-plugin.md)。分支 `feat/P2-T2-diag-plugin-patches`。
- **P2-T1 短方案 + ADR**（2026-10-05）：[`design/P2-data-capture.md`](design/P2-data-capture.md) approved；[ADR-0004](decisions/0004-capture-light-compute-async.md) 细化后 accepted；新 [ADR-0010](decisions/0010-hdt-input-dump-as-primary-source.md) accepted；[`architecture/overview.md`](architecture/overview.md) 已同步。见 [`worklog/2026-10-05-p2t1-data-capture.md`](worklog/2026-10-05-p2t1-data-capture.md)。
- **P2-T0 离线重放与往返验证**（2026-10-05）：`spikes/replay-harness` 将 `_input` 转储按 `meta` BB 版本独立进程模拟。本机 1.78.1+1.85.0 共 **261/261** 场五率往返通过；关闭 Q-009 / Q-011 / Q-013。见 [`facts/replay-roundtrip.md`](facts/replay-roundtrip.md)、[`design/P2-replay-harness.md`](design/P2-replay-harness.md)、[`worklog/2026-10-05-p2t0-replay-harness.md`](worklog/2026-10-05-p2t0-replay-harness.md)。
- **Q-014 关闭：拔线回合战果可还原**（2026-10-05）：见 [`facts/combat-result-reconstruction.md`](facts/combat-result-reconstruction.md)。
- **P2 范围重估**（2026-10-05，所有者确认）：P2 由 8 项压到 4 项。见 [`worklog/2026-10-05-p2-rescope.md`](worklog/2026-10-05-p2-rescope.md)。

## 进行中

无。

## 下一步（按优先级）

1. **agent：P2-T3 离线导入与质量报告。** 按 [`design/P2-data-capture.md`](design/P2-data-capture.md) 产出每回合一行的表。团子配对可复用 `eval_q014_reconstruct.py` 的方法；战果按 `facts/combat-result-reconstruction.md` 第 4 节取并标注来源（`tuanzi` / `hdt` / `lb` / `unknown`）；重放偏差列可调用 `spikes/replay-harness`。导入须同时认 `records.jsonl` 与 `records.jsonl.gz`。
2. **agent：P3-T0 核心假设早期验证**（依赖 P2-T0✓、P2-T3）：建议先用 BB 1.85.0 队列做全交叉模拟，再扩到全量。
3. **所有者：** 关 HDT 后部署 **0.2.0**（`spikes\hdt-diag-logger\build.ps1 -Deploy`，或拷 `HdtDiagLogger\bin\Release\net472\HdtDiagLogger.dll`）。按 [`process/field-capture.md`](process/field-capture.md) 用**团子版**继续采集（可以拔线）；每批带回 `BgHelperDiag/<id>` + 当日 `对战记录` 文本到 `data/tuanzi/`。日志应见 `loaded 0.2.0`。若要重放 1.80.1/1.81.2 局，需补对应 `BobsBuddy.dll`。

## 待决事项默认值（所有者未否决即按此执行）

| 事项 | 默认值 |
| --- | --- |
| Q-008 对局频率 | 按每周约 15–20 局规划（活跃期实测约 77 局/月；本批 7 天 48 局更高）。只用自己的数据，不引入外部数据补充 |
| Q-009 耗时标准 | **已关闭**：赛后后台每局全部回合 ≤ 10 分钟；实测每局模拟合计 ≪ 该预算。局内实时预算留到 P4-T1 |
| Q-005 CI 与托管 | 暂不做 CI，只在本机构建；托管等需要时再定 |
| 个人采集环境 | **团子版 + 对战记录对照**（ADR-0008）。插件语义仍以官方为准；允许拔线，战果由上下文还原（ADR-0009） |
| ADR-0004 / ADR-0010 | **已接受**（P2-T1，2026-10-05） |

## 阻塞 / 需要所有者决定

- 无硬阻塞。请部署插件 0.2.0 后继续采集；上表默认值如有不同意的，直接说即可。
