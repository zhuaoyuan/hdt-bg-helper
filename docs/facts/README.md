# 事实库写作规范

> 这份文档回答：什么内容可以写进 `facts/`、怎么写才能让后来的 agent 放心使用。

## 什么算"事实"

只收录关于**外部系统实际行为**的、有证据的内容：HDT 源码、Bob's Buddy 行为、游戏日志格式、实测数据。我们自己的设计选择不属于事实，写进 `decisions/` 或 `design/`。

## 必备元数据

每份事实文档头部写明：

```text
基线：HDT v1.58.3 / 509bb0b9（或实测环境：HDT 版本、游戏补丁、日期）
最后核实：YYYY-MM-DD
```

## 每条事实的写法

- 带来源：`Hearthstone Deck Tracker/BobsBuddy/BobsBuddyInvoker.cs:519`，或"实测：worklog/2026-10-01-xxx.md"。
- 标注确定性：默认是**已核实**；只有推断的，句首加 **[推断]**，并在 `research/open-questions.md` 登记验证方法。
- 写"是什么"，不写"我们打算怎么办"。

## 何时复核

- 执行版本升级流程（`process/prompts/version-upgrade.md`）时，逐份复核基线相关的事实，更新基线和核实日期。
- 实测结果与事实文档矛盾时，以实测为准，修改文档并在 worklog 记录。

## 目录

| 文件 | 内容 |
| --- | --- |
| [`hdt-baseline.md`](hdt-baseline.md) | HDT 版本、构建、插件接口、事件与战斗时机 |
| [`bobsbuddy-simulator-input.md`](bobsbuddy-simulator-input.md) | Bob's Buddy 调用方式、输入数据清单、触发时序、对手可见性（P1 主交付物；P1-T1 / P1-T3 已完成） |
| [`diag-capture-measured.md`](diag-capture-measured.md) | 官方 HDT 诊断记录实测：验收、Q-006 时序、TagTransfer 标签与缺口比例（2026-09-26，3 局 / 27 场） |
| [`diag-capture-batch-20261003.md`](diag-capture-batch-20261003.md) | 后续 48 局批评估（09-27~10-03）：跨 HDT/BB 版本完整度、覆盖缺口、匿名化腐蚀 |
| [`diag-tuanzi-compat-20261004.md`](diag-tuanzi-compat-20261004.md) | 团子版 HDT 一局 diag 与官方结构兼容；与团子对战记录交叉验证（2026-10-04） |
| [`diag-disconnect-completeness-20261005.md`](diag-disconnect-completeness-20261005.md) | 拔线场次下 diag 完整性：直接拔线缺 Combat；「不知结果」仍可有 BB Input/Output（2026-10-05） |
| [`combat-result-reconstruction.md`](combat-result-reconstruction.md) | 每场实际战果的还原：HDT invoker 字段 + 排行榜血量差；拔线/重连回合的处理与准确率（Q-014，2026-10-05） |
| [`replay-roundtrip.md`](replay-roundtrip.md) | `_input`→独立进程重放往返 261/261；Q-009 耗时、Q-011 跨版本、Q-013 未赋值扰动（P2-T0，2026-10-05） |
| [`standard-layer-import.md`](standard-layer-import.md) | P2-T3 标准层导入：每回合表、ready/团子对照/重放 3σ 本机结果（2026-10-05） |
| [`strength-cross-p3t0.md`](strength-cross-p3t0.md) | P3-T0 全交叉：S/分位成本、bootstrap、战果相关、相对 HDT、基准集、对手场面（2026-10-05） |
| [`hdt-past-opponent-board-render.md`](hdt-past-opponent-board-render.md) | HDT 上次对手阵容叠加层实现；诊断 dump 是否足以离线渲染阵容图（2026-10-05） |
| [`bobsbuddy-minion-enchantments.md`](bobsbuddy-minion-enchantments.md) | 随从附着附魔 → BB `Minion` 字段映射全表（上一份的附表） |
| [`local-environment.md`](local-environment.md) | 所有者本机实际运行的 HDT 版本、数据目录、可用工具 |
| [`bobsbuddy-public-api.md`](bobsbuddy-public-api.md) | `BobsBuddy.dll` 公开 API、独立调用实测、版本差异 |
| [`hdt-log-simulation-input.md`](hdt-log-simulation-input.md) | HDT 日志中模拟 Input/Output 段落的内容与缺口、本机修改版 HDT 的改动 |
| [`licensing.md`](licensing.md) | HDT / Bob's Buddy 许可与 HearthSim 条款原文、官方表态 |
