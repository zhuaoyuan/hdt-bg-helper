# 2026-09-25 P1-T1 源码静态分析与本机日志分析

## 做了什么

两项并行：

1. **P1-T1 源码静态分析**（HDT 基线 `509bb0b9`，结束时确认 HDT 仓库无改动）
   - 重写 `facts/bobsbuddy-simulator-input.md`：补全 `BobsBuddyUtils` 全部函数；补全快照与模拟开始的触发时序、每个战斗中更新的触发位置和条件、HDT 从未赋值的 BB 字段；每个字段加了对手可见性列。
   - 新增 `facts/bobsbuddy-minion-enchantments.md`：附魔 CardId 到 `Minion` 字段的全表。
2. **本机日志分析**（`spikes/hdt-log-analysis/`，原始输出在被忽略的 `out/`）
   - 新增 `facts/hdt-log-simulation-input.md`（Q-004、Q-010）和 `research/q008-personal-data-volume.md`（Q-008）。

主 agent 抽查：`LogWatcherManager.cs` 中 `OnPowerLogLine` 在 `PowerHandler.Handle` 之后调用；日志第 2 行的 HDT 版本；日志文件数量；对战记录中的拔线行数；入库文件中没有 BattleTag。

## 发现了什么

- Q-004：日志 Input 段落是 HDT 逐项拼出来的，缺英雄血量/等级、饰品、目标、畸变、可用种族和约一半计数器，只能近似重建。重跑也打印完整 Input。Output 可作胜/平/负对照，同一输入两次模拟差 0–1 个百分点。
- Q-006：没有公开事件对应 BB 的战斗中更新；`OnPowerLogLine` 在 HDT 处理完同一行后同步回调，但插件需要自己跟踪 BLOCK 和战斗开始标签。
- Q-007：对手 `ResourcesSpentThisGame`、未知手牌/奥秘、依赖手牌的附魔数值拿不到或只能推算；13 个整局计数器依赖 TagTransfer 附魔。
- Q-008：个人数据严格分桶只够回合 ≤12、每桶约 30 个样本，P3 需要放宽分桶。
- Q-010：修改版为第三方"团子版"，只插入日志行、没改原有格式；带拔线功能，对战记录有 372 场战斗因拔线无结果。
- 修正了两处旧文档：
  - `local-environment.md`：现有日志都来自 1.57.12 及更早版本，不是 1.58.1；
  - `hdt-baseline.md`：`SnapshotBattlegroundsBoardState` 是 HDT 自己记录对手场面的功能，单人模式也会调用。
- HDT 只保留最近 2 天加之前 25 个日志，本机日志即将开始被删。

## 留下什么

- Q-004 关闭；Q-006、Q-007、Q-008、Q-010 转为 `investigating`；新增 Q-012（修改版作验证环境是否合适）、Q-013（未赋值 BB 字段的影响）。
- 需要所有者：备份日志；追认读取对战记录目录；决定 Q-012。
- 下一步：日志近似重建场面的原型，用于 Q-009、Q-011、Q-013。
