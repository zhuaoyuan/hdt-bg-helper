# 项目状态

> 这份文档回答：项目现在在哪一步、下一步做什么、有什么阻塞。每次会话结束时由 agent 更新。

**最后更新：** 2026-09-25
**当前阶段：** P1 — 战斗模拟器数据清单

## 最近完成

- **换用官方版 HDT**（2026-09-25）：所有者安装了官方 HDT 1.58.3（自带 BB 1.78.1），今后保持最新。ADR-0007 取代 ADR-0005，Q-010、Q-012 关闭。
- **所有者决定不特意保留团子版历史日志和对战记录**（2026-09-25）：版本已和当前不同。已写入仓库的统计结论（Q-004、Q-008 等）仍然有效，但后续原型不再依赖这批日志，改用诊断记录插件的数据。
- **P1-T1 源码静态分析完成**（2026-09-25）：数据清单补全了附魔映射、触发时序、战斗中更新的触发条件、HDT 从未赋值的 BB 字段，每个字段加了对手可见性。见 [`facts/bobsbuddy-simulator-input.md`](facts/bobsbuddy-simulator-input.md)、[`facts/bobsbuddy-minion-enchantments.md`](facts/bobsbuddy-minion-enchantments.md)。Q-006、Q-007 有了源码层结论，剩下实测部分。
- **本机日志分析**（2026-09-25）：
  - Q-004 关闭：日志只能近似重建输入，Output 可作胜/平/负对照。见 [`facts/hdt-log-simulation-input.md`](facts/hdt-log-simulation-input.md)。
  - Q-010：修改版是第三方"团子版"，没发现改动模拟输入逻辑的证据，但带拔线功能（新登记为 Q-012）。
  - Q-008 初步估算：严格分桶下个人数据只够回合 ≤12、每桶约 30 个样本。见 [`research/q008-personal-data-volume.md`](research/q008-personal-data-volume.md)。
  - 脚本在 `spikes/hdt-log-analysis/`。
- **Q-003 关闭 / ADR-0006 接受**（2026-09-25）。

## 进行中

- **诊断记录插件**（方案 [`design/P1-diagnostic-logger.md`](design/P1-diagnostic-logger.md) 已批准；代码 [`spikes/hdt-diag-logger/`](../spikes/hdt-diag-logger/README.md)）：方案第 7 节第 1–5 步已实现，离线测试通过，DLL 已部署到 `%APPDATA%\HearthstoneDeckTracker\Plugins`。**等所有者重启 HDT、启用插件并打 1 局。**

## 下一步（按优先级）

1. **所有者：** 重启 HDT → 在"选项 > 追踪器 > 插件"启用 "BG Helper Diagnostic Logger" → 打 1 局酒馆战棋。
2. **agent：** 运行 `check_capture.py` 做验收检查（方案第 5 节），根据结果调整插件；通过后请所有者再打 3–5 局。
3. **分析记录**：逐项核对数据清单，实测 Q-002 / Q-006 / Q-007；用记录下的真实场面在独立进程里做 Q-009（测速）、Q-011（BB 1.76.0 / 1.78.1 / 1.78.8 对比）、Q-013（未赋值字段影响）。
4. **P1-T3 / P1-T5**：根据分析结果补全字段标注，发布数据清单 v1，交所有者审阅。

## 未决问题分工

- **agent 可独立完成：** 拿到记录后的验收检查和插件调整； Q-009、Q-011、Q-013 离线实验；官方版产生带模拟的日志后，复核 `facts/hdt-log-simulation-input.md` 的日志格式。
- **需所有者配合：**
  - **追认数据来源：** 日志分析时额外读取了修改版写的 `C:\Program Files\HDT\对战记录\`（只有英雄名和卡名，不含 BattleTag），仓库里只写了统计数字。
  - Q-008：今后每周大约打几局；数据不够时能否用其他合规数据补充。
  - Q-009：批量模拟可接受的耗时标准。
  - Q-005 后续：是否需要 CI、代码托管在哪里。
  - 诊断记录插件：启用一次确认能加载；之后带着它打 4–6 局（Q-002、Q-006、Q-007 的实测都靠这批记录）。

## 阻塞 / 需要所有者决定

- [ADR-0004](decisions/0004-capture-light-compute-async.md) 为 `proposed`，P2-T1 设计时细化后确认。