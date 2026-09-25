# 项目状态

> 这份文档回答：项目现在在哪一步、下一步做什么、有什么阻塞。每次会话结束时由 agent 更新。

**最后更新：** 2026-09-25
**当前阶段：** P1 — 战斗模拟器数据清单（刚开始）

## 最近完成

- **P0 项目初始化**（2026-09-25）：建立文档体系、流程提示词、初始 ADR；克隆 HDT 源码作为只读参考（v1.58.3 / `509bb0b9`）；对 Bob's Buddy 调用链做了初步摸底，产出数据清单草稿 [`facts/bobsbuddy-simulator-input.md`](facts/bobsbuddy-simulator-input.md)。

## 进行中

无。

## 下一步（按优先级）

1. **P1-T1** 完整静态分析 `BobsBuddyUtils.cs`（随从/饰品/目标对象的转换，草稿只读了约前 160 行）以及 `BobsBuddyInvoker` 中所有战斗中更新入口，补全数据清单。
2. **P1-T2** 检查 `BobsBuddy.dll` 的公开 API（`Input`、`Player`、`Minion`、`SimulationRunner` 等类型的可见性和可构造性），回答 [Q-001](research/open-questions.md)。
3. **P1-T4** 确认 HDT 日志中 "Simulation Input" 段落的完整度，评估能否作为采集结果的对照基准（[Q-004](research/open-questions.md)）。

## 阻塞 / 需要所有者决定

- [ADR-0002](decisions/0002-bobsbuddy-as-primary-simulator.md)、[ADR-0004](decisions/0004-capture-light-compute-async.md) 为 `proposed`，待 P1 结论后请所有者确认。
- 本机 git 未配置 `user.name`，初始提交尚未完成（见 [worklog](worklog/2026-09-25-project-bootstrap.md)）。
