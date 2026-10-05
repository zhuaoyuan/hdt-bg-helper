# 路线图

> 这份文档回答：项目分哪几个阶段、每个阶段做哪些任务、怎样才算完成。任务状态的实时进展看 [`status.md`](status.md)。

优先级由所有者在 2026-09-25 确认：**数据清单 → 采集工具 → 战力评估引擎 → HDT 实时集成 →（远期）方向决策**。

状态标记：`[ ]` 未开始 `[~]` 进行中 `[x]` 完成 `[-]` 取消

---

## P0 项目初始化 ✅

- [x] P0-T1 建立 agent 工作文档体系（[ADR-0001](decisions/0001-agent-driven-docs-structure.md)）
- [x] P0-T2 克隆 HDT 源码并确定事实基线版本
- [x] P0-T3 Bob's Buddy 调用链初步摸底，形成数据清单草稿

---

## P1 战斗模拟器数据清单 ✅

**目标：** 得到一份"要让 Bob's Buddy 重现某一场战斗，必须采集哪些数据"的完整清单，每个字段注明来源、采集时机和可见性。

- [x] P1-T1 静态分析 HDT 中构造模拟器输入的全部代码：`BobsBuddyInvoker.cs`、`BobsBuddyUtils.cs`、`TagChangeActions.cs` / `PowerHandler.cs` 中所有调用 `BobsBuddyInvoker` 的位置
- [x] P1-T2 检查 `BobsBuddy.dll` 公开 API：能否在插件或独立进程中自行构造 `Input` 并调用 `SimulationRunner`（Q-001，结论见 `facts/bobsbuddy-public-api.md`）
- [x] P1-T3 对清单每个字段标注：采集时机（战斗前快照 / 战斗中揭示 / 派生计算）、可见性（己方 / 对手 / 队友）、是否版本敏感
- [x] P1-T4 确认 HDT 日志中 Bob's Buddy 输入/输出的记录完整度，评估能否作为对照基准（Q-004，结论见 `facts/hdt-log-simulation-input.md`）
- [x] P1-T5 发布数据清单 v1，并列出已知覆盖缺口（所有者 2026-09-26 接受带缺口的 v1；缺口转入 P2-T6 长期监控）

**退出标准：**
1. 清单覆盖 `SetupInputPlayer`、`SnapshotBoardState` 及全部战斗中更新入口写入的每一个 `Input` 字段；
2. Q-001 有明确结论（可直接调用 / 需反射 / 不可行）；
3. 所有者审阅通过。

---

## P2 个人局内数据收集工具 ✅

**目标：** 在每场酒馆战棋对局中可靠地保存"模拟就绪"的战斗快照，并能证明保存下来的数据是对的。

**范围（2026-10-05 所有者确认重估，见 [`worklog/2026-10-05-p2-rescope.md`](worklog/2026-10-05-p2-rescope.md)）：** 诊断插件 `HdtDiagLogger` 转正为采集工具，不另写新插件；它的记录目录就是原始层。团子对战记录（ADR-0008）承担"阵容 / 当场五率"的独立校验，并提供实际战果与名次。原 T2–T7 已合并为下面 4 项。

- [x] P2-T0 **离线重放与往返验证**（合并原 T0、T5）：把诊断记录里 HDT `_input` 的反射转储按字段还原成 BB `Input`，按 `meta` 的 BB 版本在独立进程里模拟，与记录的 `Output` 对照。附带 Q-009（耗时）、Q-011（跨 BB 版本）、Q-013（未赋值字段）实验。P3-T0 的前置。结论见 `facts/replay-roundtrip.md`、`spikes/replay-harness/`（2026-10-05）
- [x] P2-T1 **短方案 + ADR**（`design/P2-data-capture.md`）：诊断记录目录即原始层，标准层由离线导入生成；以 HDT `_input` 为主数据源、实体快照只作后备（[ADR-0010](decisions/0010-hdt-input-dump-as-primary-source.md)，并接受细化后的 [ADR-0004](decisions/0004-capture-light-compute-async.md)）；压缩与保留策略。不再单独设计三层存储与 schema 演进体系（2026-10-05）
- [x] P2-T2 **诊断插件转正**（替代原插件骨架、原始层采集）：插件 **0.2.0**——匿名化词边界 + 结构保留名，不再误改 `Player` / `$type` / `ControlledByPlayer` / `Windfury`；`records.jsonl` 局末压成 `.gz`。过滤残留 invoker、选取 `2022=0` 之后的记录放在离线导入里做；`2717` 补录、`hearthstoneBuild` 修正为可选项（未做）
- [x] P2-T3 **离线导入与质量报告**（吸收原标准层投影、质量报告、复盘报告 v0）：诊断记录 + 团子文本批量配对 → 每回合一行（回合、对手英雄、Input 引用、Output、实际胜负与伤害、名次、完整性状态 `ready` / `partial` / `unsupported` / `invalid`）。拔线回合尽量用上下文还原战果，并标注来源（ADR-0009、Q-014）。报告包括：各状态占比、团子对照通过率、重放偏差、P1 清单缺口的正例出现情况、HDT 升级后的冒烟检查。这张表也是 P3-T0 的输入和"HDT 当场胜率"基线（2026-10-05：`tools/standard_layer`；核实见 `facts/standard-layer-import.md`）

**退出标准（P2-T1 可修正）：** 连续 10 局真实对局中：非"直接拔线"回合的 `ready` 占比 ≥ 90%；`ready` 回合与团子记录的阵容、五率、模拟次数 100% 一致；用同版本 BB 重放的胜/平/负率与记录之差在两次抽样合并误差的 3σ 以内。

> **退出（2026-10-05，所有者提前结束）：** 配对 **7** 局（含 0.2.0 的 `ed11e0`、`e1f536`）ready **78/82=95.1%**、团子对照 **78/78**、重放 3σ **78/78**；全量历史 ready 仍约 99%。字面「连续 10 局」未凑满，三条质量门槛已满足，**P2 关闭**。见 [`worklog/2026-10-05-p2-early-exit.md`](worklog/2026-10-05-p2-early-exit.md)。

---

## P3 战力评估引擎（离线）

**目标：** 对任意 `ready` 快照，给出"本回合战力分位"及其置信度（定义见 [ADR-0003](decisions/0003-strength-metric-definition.md)）。

- [x] P3-T0 **核心假设早期验证**（依赖 P2-T0、P2-T3）：BB 1.85.0 同回合全交叉（`player_vs_player` + `player_vs_both`）。结论：成本远低于 Q-009；bootstrap 中位宽 ≈12–14 百分位点；分位对当场战果有中等区分，但对「本场对阵」相对 HDT 无增量；固定基准集弱于全池；对手场面进池未见明显毒化。**不推翻 ADR-0003**。见 `facts/strength-cross-p3t0.md`、`spikes/strength-cross/`（2026-10-05）
- [x] P3-T1 设计方案 + 校准：参照池/放宽/抽样/缓存/置信区间。方案 `design/P3-T1-strength-engine.md`（**approved**）+ [ADR-0011](decisions/0011-strength-pool-round-robin.md)（**accepted**）。校准 E1–E5：`facts/strength-calibration.md`（2026-10-05：iterations=500，K=30，\(G_\text{min}=6\)，\(w_\text{relax}=0.25\)+L1，L2 关；Q-015/Q-016 关闭）
- [x] P3-T2 批量模拟服务（状态哈希去重、结果缓存、模拟器版本标记）：`tools/ReplaySim` + `tools/strength`；验收见 `facts/strength-batch-p3t2.md`（2026-10-05）
- [x] P3-T3 分位计算与不确定度输出：`tools/strength` 循环赛 \(S/Q\) + 聚类 bootstrap + `strength.jsonl`；验收见 `facts/strength-percentile-p3t3.md`（2026-10-05）。**交付完成并已合入 `main`；退出标准第 1 条未达标**（中位宽 23.5、≤20 占 25%）
- [ ] P3-T4 指标有效性评估（区分度、稳定性、与名次/后续血量的关系；相对 HDT 的增量在名次标签上比）
- [ ] P3-T5 复盘视图原型（按回合展示分位、置信度、实际对手和结果）
- [x] P3-T6 **局面阵容图离线渲染**（P3-T5 的组件，可单独交付）：无状态单侧随从横排 PNG（`tools/board_render/` `render_side`）；本机 HDT 贴图；v1 只画随从。验收 1–5 通过（所有者 2026-10-05 确认）；已合入 `main`。方案 `design/P3-board-render.md`（implemented）、[ADR-0012](decisions/0012-board-render-side-unit.md)

**退出标准（2026-10-05 所有者确认）：**
1. 当前主版本队列（≥20 局）中，回合 ≤12 的己方 `ready` 场面：聚类 bootstrap 95% 区间宽度**中位 ≤15**，且 **≥80%** 的场面 ≤20 个百分位点；
   - **2026-10-05 T3 实测（1.85 / 30 局 / 329 场面）：中位 23.53，≤20 占 25.2% — 未过**（见 `facts/strength-percentile-p3t3.md`）。
2. 新增 1 局的增量计算 ≤10 分钟（本机墙钟）；一个版本的回填 ≤2 小时；
3. P3-T4：局均分位与名次、下一回合血量显著相关；相对 HDT 的增量信息在**名次**标签上比较，不比本场战果。

---

## P4 HDT 实时集成

**目标：** 对局中在 HDT 覆盖层低干扰地显示当前战力分位与置信度，不影响 HDT 与游戏性能。

- [ ] P4-T1 设计方案：计算时机与延迟预算、缓存/预计算策略、覆盖层 UI
- [ ] P4-T2 实现与性能验证

---

## P5（远期）方向决策等上层模块

基于战力分位、阵容模板、回合、血量、历史数据做方向选择复盘与提示。启动前需重新评估。
