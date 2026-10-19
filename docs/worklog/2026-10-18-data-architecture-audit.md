# 2026-10-18 数据架构复核（应记录而不完整）

## 目标

检查当前数据架构（原始层 → 标准层 → 模拟/战力层 → 复盘层），评估哪些数据是“应该记录、但现在不完整”的，按优先级给出补法。只读复核，不改代码/数据。

## 做了什么

- 读代码：`spikes/hdt-diag-logger`（`DiagPlugin` / `GameSession` / `EntitySnapshot` / `HdtBobsBuddyProbe` / `RecordWriter`）、`tools/standard_layer`（导入、status、gaps、result、combat）、`tools/strength`（pool/percentile）、`tools/review_view`（join/boards/model）。
- 读文档：`architecture/overview`、`design/P2-data-capture`、`P1-data-checklist-v1`、`facts/bobsbuddy-simulator-input`、`diag-capture-measured`、`combat-result-reconstruction`、`standard-layer-import`、`replay-roundtrip`、`context/early_discussion` 第四、五节、`context/vision`。
- 读本机数据：`data/standard/turns.jsonl`（933 行）及 `quality_report.*`、`data/standard_188_late` / `standard_20261010` 报告、`data/strength/1.85.0.0/strength.jsonl`、`data/review/*/model.json` 目录结构。
- 统计（grep）：`placement=null` 803/933、`myHero=null` 546/933、`bbVersion=1.88.6.0` 277 行。

## 发现（摘要）

- **`ready` 是“可复现性”指标，不是“真实状态完整”指标。** 系统性盲区只进 `gapFlags` 不降级，且 `gapFlags` 只有 4 类；对手 `ResourcesSpent` 恒 0 却没有对应 flag。
- **名次/终局八人排名没落进标准层**：标准层 `placement` 只从团子取（130/933 非空），但原始排行榜实体里有 `PLAYER_LEADERBOARD_PLACE`（`power_replay.py` 已解析），是低成本可补项。
- **规则上下文（畸变/种族/伤害上限/补丁）没有进标准层和 `strength.jsonl`**，参照池无法按同规则筛选，复算无法证明当时大厅规则。
- **非战斗阶段没有结构化**：商店/金币/购买/出售/刷新/三连/技能使用只在 `power.log.gz` 原始行里；插件不在购物阶段拍快照。愿景明确要求“现在就采集当回合金币、酒馆状态和操作事件”，尚未实现。若继续依赖 raw，必须保证 `power.log.gz` 长期保留（现策略是磁盘紧张时先删它）。
- **标准层不自包含**：`tools/strength/pool.py` 和 `review_view/boards.py` 都回读原始记录；raw 是唯一事实源，但分散在两个根、无 manifest/校验，质量报告停在 55 局/640 回合，而 `turns.jsonl` 已 933 行。
- **当前主版本验证断了**：1.88.6 没有同版本 roundtrip（Q-002 仍 investigating）、两批 1.88.6 数据 `paired=0`；P2 的 78/78 只到 1.85。
- **schema/版本没有演进记录**：插件 0.1.0→0.2.0 仍 `schemaVersion=1`；匿名化 token 会混入英雄名（`oppHero` 带 `player_<hash>` 片段），按英雄名分组会出错。

## 留下的东西

- 新增审计：`docs/research/data-architecture-audit-20261018.md`（20 项缺口，按 P0/P1/P2 分级）。
- 新增未决问题：`docs/research/open-questions.md` Q-022（经济/操作数据是否 P4 前补，还是只保 raw）。
- `docs/status.md` 已更新（最近完成 / 下一步 / 待决）。
- 未改代码、未改数据；2026-10-19 由主会话随 v2 一起提交。

## 下一步

按审计文档第 4 节：先做 P0（名次/终局/规则/完整性/自包含/单一数据集 + 1.88.6 验证），再由所有者决定 Q-022 的 P1 范围。
