# 项目状态

> 这份文档回答：项目现在在哪一步、下一步做什么、有什么阻塞。每次会话结束时由 agent 更新。

**最后更新：** 2026-10-05
**当前阶段：** P2 — 个人局内数据收集工具（P1 已完成）

## 最近完成

- **10.5 拔线场次 diag 完整性**（2026-10-05）：团子当日对照 BgHelperDiag。无拔线局 `6ab052` 10/10；`c88ca9` 10/11；最新德雷阿佳丝局 `20ad61` **11/12**（仅 T10「直接拔线」缺 Combat；T6–T9/T11「不知结果」阵容+BB 仍在）。泽瑞拉局仅中途启用残局 `bdd811`。见 [`facts/diag-disconnect-completeness-20261005.md`](facts/diag-disconnect-completeness-20261005.md)、[`worklog/2026-10-05-disconnect-diag-completeness.md`](worklog/2026-10-05-disconnect-diag-completeness.md)。
- **HDT 无响应排查搁置**（2026-10-05）：重启电脑后，无论是否启用 `HdtDiagLogger` 均未再出现未响应。前一日证据指向 HearthMirror Cross-thread Hang、很大概率非本插件；现无法稳定复现，**排查暂停**。若再出现再开。见 [`worklog/2026-10-04-hdt-hang-triage.md`](worklog/2026-10-04-hdt-hang-triage.md)。
- **采集策略确认**（2026-10-04）：所有者后续以**团子版**采集 + 团子对战记录对照；已写 [ADR-0008](decisions/0008-tuanzi-capture-with-record-crosscheck.md)，并更新 [`process/field-capture.md`](process/field-capture.md)。
- **团子版 diag 兼容性**（2026-10-04）：`20261004_200638_13406d`（团子 HDT 1.58.6.0 / BB 1.85.0）与官方样本 Input/Output schema 一致；与 `data/tuanzi/2026年10月04日.txt` 阵容+模拟五率 10/10 对齐。见 [`facts/diag-tuanzi-compat-20261004.md`](facts/diag-tuanzi-compat-20261004.md)。
- **BgHelperDiag 大批次评估**（2026-10-04）：所有者放入 `data/BgHelperDiag` 共 48 局（09-27~10-03），跨 HDT 1.58.3→1.58.6 / BB 1.78.1→1.85.0。537/539 场战斗完整；发现匿名化误伤 `Player` 键（10 局可修复）、`hearthstoneBuild` 不可信。见 [`facts/diag-capture-batch-20261003.md`](facts/diag-capture-batch-20261003.md)、[`worklog/2026-10-04-diag-dataset-eval.md`](worklog/2026-10-04-diag-dataset-eval.md)。
- **项目整体评估与计划补充**（2026-09-26）：所有者采纳全部 8 条建议，已写入 `roadmap.md`：新增 P2-T0 离线重放工具、P2-T7 赛后复盘报告 v0、P3-T0 核心假设早期验证；P2-T1 / P2-T6 补充要求；P2、P3 退出标准填了占位值。详见 [`worklog/2026-09-26-project-review.md`](worklog/2026-09-26-project-review.md)。
- **P1 完成**（2026-09-26）：所有者接受带缺口的数据清单 v1（[`design/P1-data-checklist-v1.md`](design/P1-data-checklist-v1.md)），缺口按 `partial` 处理，转入 P2-T6 长期监控。
- **异地继续采集说明**（2026-09-26）：诊断插件 0.1.0 对「继续打、继续记」功能齐备。操作见 [`process/field-capture.md`](process/field-capture.md)。
- **P1-T3 字段实测标注**（2026-09-26）：官方 HDT 3 局 / 27 场战斗全部验收通过，Q-006、Q-007 关闭。见 [`facts/diag-capture-measured.md`](facts/diag-capture-measured.md)。
- **换用官方版 HDT**（2026-09-25）：ADR-0007 取代 ADR-0005。
- **P1-T1 / T2 / T4**（2026-09-25）：源码清单、公开 API、日志对照。

## 进行中

无。

## 下一步（按优先级）

1. **agent：P2-T0 离线重放工具。** 先写短方案（`design/P2-replay-harness.md`），再实现：诊断记录 `_input` 转储 → BB `Input` → 独立进程模拟 → 与记录 `Output` 对照。必须按 `meta` 的 BB 版本选 DLL；过滤残留 invoker；修复被匿名化改名的 `Player` 键。之后顺带做 Q-009 / Q-011 / Q-013 实验。
2. **agent：修诊断插件匿名化**（可并入 P2-T1 或小补丁）：禁止无词边界替换，避免再腐蚀 `Player` / `$type`。
3. **agent：P3-T0 核心假设早期验证**（依赖 P2-T0）：建议先用 BB 1.85.0 队列（~16 局）做全交叉模拟，再扩到全量。
4. **agent：P2-T1 采集方案。** 要点：快照改到 `2022=0`（或同时拍）；按对局 id 丢掉旧 invoker；`2717` 同时记 TF 和玩家实体；`hearthstoneBuild` 在元数据稳定后写入；诊断记录可导入；压缩与保留；起草"HDT `_input` 为主数据源"的 ADR。
5. **所有者：** 按 [`process/field-capture.md`](process/field-capture.md) 用**团子版**继续采集；每批带回 `BgHelperDiag/<id>` + 当日 `对战记录` 文本到 `data/tuanzi/`。当前样本已够 P2-T0 开工，采集与开发可并行。

## 待决事项默认值（所有者未否决即按此执行）

| 事项 | 默认值 |
| --- | --- |
| Q-008 对局频率 | 按每周约 15–20 局规划（活跃期实测约 77 局/月；本批 7 天 48 局更高）。只用自己的数据，不引入外部数据补充 |
| Q-009 耗时标准 | 赛后后台计算：每局全部回合 ≤ 10 分钟，不影响正常使用电脑；局内实时的预算留到 P4-T1 |
| Q-005 CI 与托管 | 暂不做 CI，只在本机构建；托管等需要时再定 |
| 个人采集环境 | **团子版 + 对战记录对照**（ADR-0008）。插件语义仍以官方为准；避免拔线 |
| ADR-0004 | 维持 `proposed`，P2-T1 细化后再请所有者确认 |

## 阻塞 / 需要所有者决定

- 无硬阻塞。上表默认值如有不同意的，直接说即可。
