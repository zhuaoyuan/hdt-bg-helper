# ADR-0010：以 HDT `_input` 反射转储为主数据源，实体快照为后备

- **状态：** accepted（所有者 2026-10-05 对话确认完成 P2-T1）
- **日期：** 2026-10-05
- **相关：** P2-T1、ADR-0002、ADR-0004、ADR-0006、Q-002；`design/P2-data-capture.md`、`facts/replay-roundtrip.md`、`facts/diag-capture-batch-20261003.md`

## 背景

- 早期架构假定：插件采实体与标签 → 标准层 → InputBuilder 重建 Bob's Buddy `Input`（对照 HDT 源码逻辑）。
- 诊断插件已能反射读取并转储 HDT 当场使用的 `BobsBuddyInvoker._input` 与 `Output`（Q-002 在多小版本上持续成功）。
- P2-T0 将 `_input` 按字段还原后，用同版本 BB 独立进程模拟，261/261 场五率往返通过（`facts/replay-roundtrip.md`）。
- 团子对战记录可独立校验阵容与当场五率（ADR-0008），降低「必须自建重建器才能证明数据正确」的压力。
- 自行维护完整 InputBuilder 成本高，且易与 HDT 行为漂移。

## 决定

1. **主数据源**是诊断记录里的 HDT `_input` / `Output` 反射转储（`records.jsonl` 的 `hdt_bb`），不是从实体快照自行重建的 Input。
2. **选用规则：** 只使用本场战斗分段内的记录（`2022=0` 之后 / `combat_phase=true` 分段），排除上一局残留 invoker；具体过滤在离线导入与重放工具中实现。
3. **实体快照与 `power.log.gz` 是后备**：用于诊断、对照、以及反射失效或缺字段时的降级路径；P2 **不**实现完整 InputBuilder。
4. **依赖代价：** 接受对 HDT 内部字段名的依赖（ADR-0006 已允许只读反射）。每次 HDT/BB 升级做冒烟：`check_capture` + 小样本 roundtrip；失败则该版本标记 `unsupported` / `partial`，再评估是否启动后备重建。

## 考虑过的方案

| 方案 | 优点 | 缺点 | 为什么没选 / 为什么选 |
| --- | --- | --- | --- |
| 实体快照 + 自研 InputBuilder 为主 | 少依赖私有字段 | 工程量大；易与 HDT 漂移；P2-T0 已证明非必要 | 没选 |
| **`_input` 转储为主，实体为后备** | 与 HDT 当场一致；已有往返证据；可立刻服务 P3-T0 | 反射可能随大版本断裂 | **选中** |
| 只存 Output / 团子五率，不存 Input | 体积小 | 无法做交叉模拟与分位 | 没选 |

## 后果

- 正面：P2/P3 可直接用已采样本；避免重复实现 HDT 的 SnapshotBoardState 逻辑。
- 负面 / 代价：升级冒烟成为常规；匿名化与残留 invoker 必须在导入侧（及 T2 插件侧）处理好。
- 需要跟进：P2-T2 匿名化词边界；P2-T3 选用规则写入导入；Q-002 在大版本上继续观察。

## 推翻条件

某一 HDT 大版本起反射持续失败或 dump 无法还原，且实体重建在可接受工期内能稳定对齐 BB；或官方提供稳定的公开导出 API 可替代反射。
