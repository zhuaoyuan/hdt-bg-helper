# 项目状态

> 这份文档回答：项目现在在哪一步、下一步做什么、有什么阻塞。每次会话结束时由 agent 更新。

**最后更新：** 2026-09-25
**当前阶段：** P1 — 战斗模拟器数据清单

## 最近完成

- **P1-T1 源码静态分析完成**（2026-09-25）：数据清单补全了附魔映射、触发时序、战斗中更新的触发条件、HDT 从未赋值的 BB 字段，每个字段加了对手可见性。见 [`facts/bobsbuddy-simulator-input.md`](facts/bobsbuddy-simulator-input.md)、[`facts/bobsbuddy-minion-enchantments.md`](facts/bobsbuddy-minion-enchantments.md)。Q-006、Q-007 有了源码层结论，剩下实测部分。
- **本机日志分析**（2026-09-25）：
  - Q-004 关闭：日志只能近似重建输入，Output 可作胜/平/负对照。见 [`facts/hdt-log-simulation-input.md`](facts/hdt-log-simulation-input.md)。
  - Q-010：修改版是第三方"团子版"，没发现改动模拟输入逻辑的证据，但带拔线功能（新登记为 Q-012）。
  - Q-008 初步估算：严格分桶下个人数据只够回合 ≤12、每桶约 30 个样本。见 [`research/q008-personal-data-volume.md`](research/q008-personal-data-volume.md)。
  - 脚本在 `spikes/hdt-log-analysis/`。
- **Q-003 关闭 / ADR-0006 接受**（2026-09-25）。

## 进行中

无。

## 下一步（按优先级）

1. **Q-009 / Q-011**：写一次性原型，把日志里的 Input 段落近似重建成 BB `Input`（CardId、攻血、关键词、`ScriptDataNum`、场上顺序），用这批真实场面：
   - 在独立进程里测单场耗时；
   - 分别在 BB 1.76.0 和 1.78.8 下跑，统计失败和胜率偏差。
2. **Q-013**：同一个原型里，对比设置 / 不设置 HDT 从未赋值的 BB 字段，看是否影响结果。
3. **P1-T3**：按已有的可见性列，把"待实测"项整理成 P2 原型的实测清单。
4. **P1-T5**：发布数据清单 v1，列出已知覆盖缺口，交所有者审阅。

## 未决问题分工

- **agent 可独立完成：** Q-009（本机测速）、Q-011（版本对比）、Q-013（未赋值字段影响）、Q-010 的成员级签名对比。
- **需所有者配合：**
  - **备份日志（建议尽快）：** HDT 只保留最近 2 天加之前 25 个日志，本机正好 26 个，下次启动 HDT 就会开始删最旧的。建议把 `%APPDATA%\HearthstoneDeckTracker\Logs\` 整个复制到别处。
  - **追认数据来源：** 日志分析时额外读取了修改版写的 `C:\Program Files\HDT\对战记录\`（只有英雄名和卡名，不含 BattleTag），仓库里只写了统计数字。
  - **Q-012：** 是否继续用修改版 HDT 作验证环境。
  - Q-008：今后每周大约打几局；数据不够时能否用其他合规数据补充。
  - Q-009：批量模拟可接受的耗时标准。
  - Q-005 后续：是否需要 CI、代码托管在哪里。
  - 可选的早期验证：把 `spikes/hdt-plugin-skeleton` 编译出的 DLL 放进 HDT 插件目录并启用，确认修改版 HDT 能加载插件。
  - Q-002、Q-006、Q-007 实测：P2 原型插件写好后需要所有者打若干局。

## 阻塞 / 需要所有者决定

- [ADR-0004](decisions/0004-capture-light-compute-async.md) 为 `proposed`，P2-T1 设计时细化后确认。
- Q-012（修改版 HDT 是否继续作验证环境）不阻塞 P1，但要在 P2-T5 往返验证之前决定。
