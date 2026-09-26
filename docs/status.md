# 项目状态

> 这份文档回答：项目现在在哪一步、下一步做什么、有什么阻塞。每次会话结束时由 agent 更新。

**最后更新：** 2026-09-26
**当前阶段：** P1 — 战斗模拟器数据清单

## 最近完成

- **异地继续采集说明**（2026-09-26）：确认诊断插件 0.1.0 对「继续打、继续记」功能齐备，不必改插件。操作见 [`process/field-capture.md`](process/field-capture.md)。
- **P1-T3 字段实测标注**（2026-09-26）：官方 HDT 3 局 / 27 场战斗全部验收通过。Q-006、Q-007 关闭。清单补了采集时机、对手可见性（实测）和版本敏感说明。统计见 [`facts/diag-capture-measured.md`](facts/diag-capture-measured.md)，字段表见 [`facts/bobsbuddy-simulator-input.md`](facts/bobsbuddy-simulator-input.md)。
- **诊断记录 3 局验收通过**（2026-09-26）：`cd944c` 9 场、`a8ee8b` 8 场、`e07627` 10 场；开战快照 / HDT Input / Output / 战后快照齐全；0 错误；无插件超时；匿名化通过。不需要修插件或重打。
- **换用官方版 HDT**（2026-09-25）：ADR-0007 取代 ADR-0005；Q-010、Q-012 关闭。
- **P1-T1 / T2 / T4**（2026-09-25）：源码清单、公开 API、日志对照。Q-001、Q-003、Q-004 已关闭。

## 进行中

- **P1-T5 清单 v1 待审阅**：草稿 [`design/P1-data-checklist-v1.md`](design/P1-data-checklist-v1.md)。**未**标成完成。已知缺口：对手花费、`2717`、战斗中补录、双人 / 畸变 / Malorne 等无正例。

## 下一步（按优先级）

1. **所有者（可在无开发环境的电脑上）：** 按 [`process/field-capture.md`](process/field-capture.md) 拷走 `HdtDiagLogger.dll`，用官方 HDT 继续打。优先碰到任务、对手奥秘、Malorne、畸变、战斗中补录就留下；打完把整个 `BgHelperDiag\` 带回来。
2. **所有者：** 审阅数据清单 v1（`design/P1-data-checklist-v1.md`）。
3. **Q-013 / Q-009 / Q-011（独立进程，不阻塞 P1-T3）：** 用记录里的场面设置 / 不设置 HDT 未赋值字段；测单场耗时；同一场面在 BB 1.76.0 / 1.78.1 / 1.78.8 下比失败率和胜率。脚本可从 `spikes/hdt-diag-logger/tools/` 的分析工具接着写。
4. **P2-T1：** 采集方案。要点：快照改到 `2022=0`（或同时拍）；按对局 id 丢掉旧 invoker；`2717` 同时记 TF 和玩家实体。
5. 往返验证（实体快照重建 Input vs `hdt_bb` Output，约 2 个百分点）可与 Q-013 一起做。

## 未决问题分工

- **agent 可独立完成：** Q-009、Q-011、Q-013 离线实验；P2-T1 草案。
- **需所有者配合：**
  - 审阅 P1-T5 清单 v1。
  - Q-008：今后每周大约打几局；数据不够时能否用其他合规数据补充。
  - Q-009：批量模拟可接受的耗时标准。
  - Q-005 后续：是否需要 CI、代码托管在哪里。
  - **追认数据来源：** 日志分析时额外读取了修改版写的 `C:\Program Files\HDT\对战记录\`（只有英雄名和卡名，不含 BattleTag），仓库里只写了统计数字。

## 阻塞 / 需要所有者决定

- [ADR-0004](decisions/0004-capture-light-compute-async.md) 为 `proposed`，P2-T1 设计时细化后确认。
- P1-T5 等所有者审阅后再勾完成。
