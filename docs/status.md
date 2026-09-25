# 项目状态

> 这份文档回答：项目现在在哪一步、下一步做什么、有什么阻塞。每次会话结束时由 agent 更新。

**最后更新：** 2026-09-25
**当前阶段：** P1 — 战斗模拟器数据清单

## 最近完成

- **P0 项目初始化**（2026-09-25）：建立文档体系、流程提示词、初始 ADR；克隆 HDT 源码作为只读参考（v1.58.3 / `509bb0b9`）；对 Bob's Buddy 调用链做了初步摸底，产出数据清单草稿 [`facts/bobsbuddy-simulator-input.md`](facts/bobsbuddy-simulator-input.md)。
- **未决问题分工与本机环境摸底**（2026-09-25）：记录本机环境 [`facts/local-environment.md`](facts/local-environment.md)；本机 HDT 是 1.58.1 修改版，所有者决定以它为验证环境（[ADR-0005](decisions/0005-modded-hdt-as-test-environment.md)）。
- **Q-001 / Q-003 / Q-005 调研**（2026-09-25）：
  - **Q-001 已关闭（P1-T2 完成）**：Bob's Buddy 核心类型全部公开，能在 HDT 之外自己构造 `Input` 并调用模拟，1.76.0 和 1.78.8 都实测通过（[`facts/bobsbuddy-public-api.md`](facts/bobsbuddy-public-api.md)，原型 `spikes/bobsbuddy-api/`）。
  - **Q-005 已关闭（本地构建部分）**：用 .NET SDK 就能编译引用本机 HDT 的插件（[`facts/hdt-baseline.md`](facts/hdt-baseline.md) 的"插件加载""插件构建"，原型 `spikes/hdt-plugin-skeleton/`）。
  - **Q-003 事实已整理，待所有者判断**：HDT 和 Bob's Buddy 都是专有软件；HearthSim 条款只授予个人非商业使用，禁止修改、衍生、再分发；没有针对插件调用 DLL 的明确条款（[`facts/licensing.md`](facts/licensing.md)）。
  - 新增 Q-011：新版 Bob's Buddy 会删除下架卡牌的实现，离线模拟需要版本策略。

## 进行中

无。

## 下一步（按优先级）

1. **P1-T1** 完整静态分析 `BobsBuddyUtils.cs` 和 `BobsBuddyInvoker` 的所有战斗中更新入口，补全数据清单（同时覆盖 Q-006、Q-007 的源码部分）；顺带把 `Minion` 的公开字段与 HDT 赋值逐一对照。
2. **P1-T4 / Q-004 / Q-010** 用本机已有的 HDT 日志，对照 `RunSimulation` 的日志语句，评估 "Simulation Input" 的完整度，同时看修改版的日志与源码是否一致。
3. **Q-009 / Q-011** P1-T4 能从日志重建真实场面后，用真实场面测模拟耗时，并比较 1.76.0 与 1.78.8 的结果差异。

## 未决问题分工

- **agent 可独立完成：** Q-009（本机测速）、Q-006 和 Q-007 的源码梳理、Q-011 的版本对比。
- **用本机已有数据先得初步结论（所有者已授权读取，入库内容匿名化）：** Q-004、Q-007（初步估算）、Q-008（历史对局频率）、Q-010。
- **需所有者配合：**
  - Q-003：判断 [`facts/licensing.md`](facts/licensing.md) 末尾的 4 个问题；之后才能确认 ADR-0002。
  - Q-005 后续：是否需要 CI（GitHub 上拿不到新版 HDT 二进制文件）、代码托管在哪里。
  - Q-008：今后每周大约打几局；数据不够时能否用其他合规数据补充。
  - Q-009：批量模拟可接受的耗时标准。
  - 可选的早期验证：把 `spikes/hdt-plugin-skeleton` 编译出的 DLL 放进 HDT 插件目录、重启并启用，确认修改版 HDT 能加载插件（步骤见该目录 README）。
  - Q-002、Q-006、Q-007 实测比例、Q-004 对照基准：P2 原型插件写好后需要所有者打若干局。

## 阻塞 / 需要所有者决定

- [ADR-0002](decisions/0002-bobsbuddy-as-primary-simulator.md) 为 `proposed`：Q-001 已支持该方案，等 Q-003 判断后确认。
- [ADR-0004](decisions/0004-capture-light-compute-async.md) 为 `proposed`，P2-T1 设计时细化后确认。
