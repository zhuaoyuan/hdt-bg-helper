# 架构决策记录（ADR）

> 这份文档回答：什么情况下要写 ADR、怎么写、目前有哪些决定。

## 什么时候写

满足任一条件就写：

- 有两个以上可行方案，选择会影响当前任务之外的工作；
- 改变数据格式、存储、外部依赖、模块边界；
- 推翻或收窄之前的决定；
- 以后的 agent 很可能会问"为什么不用 X"。

## 状态

`proposed`（提议，待所有者确认）→ `accepted`（已接受）→ 可能变成 `superseded by ADR-NNNN`（被取代）或 `deprecated`（废弃）。

- agent 可以新建 `proposed` ADR。
- 改成 `accepted` 需要所有者确认，确认方式写在 ADR 的"状态"一行里（例如"所有者 2026-09-25 对话确认"）。
- 已接受的 ADR **不改写正文**。要改决定就新写一份 ADR，并在旧 ADR 的状态行标注被取代。

## 写法

复制 [`0000-template.md`](0000-template.md)，文件名 `NNNN-short-title.md`，序号递增。

## 索引

| 编号 | 标题 | 状态 |
| --- | --- | --- |
| [ADR-0001](0001-agent-driven-docs-structure.md) | 采用分类文档体系支撑 agent 驱动开发 | accepted |
| [ADR-0002](0002-bobsbuddy-as-primary-simulator.md) | 以 Bob's Buddy 作为首选战斗模拟器 | proposed |
| [ADR-0003](0003-strength-metric-definition.md) | 以"本回合战力分位"作为核心战力指标 | accepted |
| [ADR-0004](0004-capture-light-compute-async.md) | 插件采集保持轻量，原始数据只追加，计算异步化 | proposed |
