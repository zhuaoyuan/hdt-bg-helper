# 数据清单 v1（待所有者审阅）

- **状态：** review（P1-T3 标注已写入 facts；本页列出覆盖与缺口，**未**把 P1-T5 标成完成）
- **任务：** P1-T5
- **日期：** 2026-09-26
- **相关：** [`facts/bobsbuddy-simulator-input.md`](../facts/bobsbuddy-simulator-input.md)、[`facts/diag-capture-measured.md`](../facts/diag-capture-measured.md)

## 1. 清单在哪

完整字段表仍是 `facts/bobsbuddy-simulator-input.md`（源码 + 采集时机 + 对手可见性）。本批 3 局 / 27 场单人官方 HDT 的统计在 `facts/diag-capture-measured.md`。

要重现 HDT 当场那次模拟，开战时必须能拿到：

| 层 | 字段 | 本批 |
| --- | --- | --- |
| 对局 | `availableRaces`、`DamageCap`、`turn`、`isDuos` | 有；`Anomaly` 本批为空 |
| 双方英雄 | `Health`、`DamageTaken`、`Tier`、英雄技能 CardId / 激活 / Data | 有；与 2022 行 Input 27/27 对上 |
| 双方场面 | 按 `ZONE_POSITION` 的随从及第 4 节标签、附魔 | 随从数 27/27 对上 |
| 饰品 / 目标 / 神祇 | `PLAY` / `SECRET` 区实体 | 饰品、神祇有；任务极少 |
| 己方手牌与奥秘 | 完整转换 | 有 |
| 对手手牌与奥秘 | 已知 CardId 或 `Unknown` / `null` | 本批手牌全已知（不能当常态）；奥秘几乎没有 |
| 对手整局计数器 | TagTransfer 上的 3.7 标签 | 多数对得上；**`2717` 对不上**；花费恒为 0 |
| 玩家附魔计数器 | 3.6 附魔 CardId | 见过永恒骑士 / 亡灵 / 血宝石 / 甲虫 |
| 战斗中补录 | 第 5.2 节 | 本批几乎没有，不能宣布已覆盖 |

HDT 从未赋值的 BB 字段（第 7 节）本批 Input 全为 0。会不会影响结果还没做独立进程实验（Q-013），**不写入「必须采集」**，只标为已知未知。

## 2. 已知覆盖缺口（会让快照变成 `partial` 或偏差）

1. **对手 `ResourcesSpentThisGame`**：27/27 为 0，无 Malorne 反推。
2. **对手 `FriendlyMinionsDeadLastCombatCounter`**：TF 从不带 `2717`，Input 恒 0；9/27 场玩家实体有 1–9。采集应两处都记。
3. **对手奥秘 / 未知手牌**：本批几乎测不到缺口比例。
4. **5.2 战斗中补录**：重跑 1 次，公开奥秘事件 0 次。Tavish 装填、手牌附魔、亡语对账未覆盖。
5. **双人、畸变、任务奖励、`4803` / Volumizer / 元素额外攻血的对手正例**：0。
6. **插件实体快照偏早**：现在拍在 `3533=0`，BB 快照在约 80 行之后的 `2022=0`。本批数字仍一致；P2 应改到 `2022` 再拍或只信那一次。
7. **上一局 invoker 残留**：新对局开头会倒出旧回合 Input。分析必须按 `2022=0` 行号过滤；P2 应按对局 id 丢弃旧键。

## 3. 请所有者审阅

- 第 1 节「必须采集」是否有漏、有多余。
- 第 2 节缺口里，哪些可以接受为 v1 的 `partial`，哪些要再打几局补样本（建议：有任务、有对手奥秘、有 Malorne / 畸变的对局；双人可后置）。
- Q-008 / Q-009 仍要你拍板：今后大约每周几局；批量模拟可接受的耗时。

Q-013 / Q-009 / Q-011 的独立进程实验不阻塞本清单，登记在 `status.md` 下一步。
