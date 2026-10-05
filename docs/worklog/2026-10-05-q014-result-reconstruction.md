# 2026-10-05 Q-014 拔线回合战果还原

## 做了什么

- 从 HDT 安装目录刷新团子对战记录到 `data/tuanzi/`（10-04 文件变大：当晚又打了 2 局，对应 `62725a`、`3a513e`）。
- 新增 `spikes/hdt-diag-logger/tools/power_replay.py`：从 `power.log.gz` 重放实体标签（`FULL_ENTITY` / `SHOW_ENTITY` / `CHANGE_ENTITY` / `TAG_CHANGE`、`CREATE_GAME` 内的 GameEntity / Player 块）。
- 新增 `eval_q014_reconstruct.py`：对 55 局 / 609 场战斗算两路战果信号，按 `_playerHeroName` + 每回合 `_opponentHeroName` 与团子文本自动配对（5 局，对手名逐回合全部对上），统计准确率。全量跑一次约 45 秒。

## 过程中的发现

1. **invoker 转储里本来就有 HDT 的战果判定。** combat_end 的 `hdt_bb` 带 `LastAttackingHero` / `LastAttackingHeroAttack`、`_attackingHero` / `_defendingHero`、`_reconnectCounterAtSnapshot`，还有中文英雄名，可直接和团子配对。
2. **排行榜英雄实体是独立的第二路信号。** 每个玩家一个带 `PLAYER_LEADERBOARD_PLACE` 的英雄实体，`HEALTH - DAMAGE + ARMOR` 的变化就是战斗伤害；护甲必须算进去（本局多数前期伤害都打在护甲上）。
3. **第一版在拔线回合全判成"平"。** 重连回合 END 那一行正是重连后 `FULL_ENTITY - Updating` 全量转储的第一行，战后血量在后面几十行才出现。改成"取 END 后这段转储结束处"后，9 个拔线回合全部给出结果。
4. **长窗口不可用。** "开战 → 下一场开战"会混入商店阶段的血量变化，47 回合里 2 回合判错、2 回合判不出。
5. **幽灵对手。** 对手 CardId 为 `TB_BaconShop_HERO_KelThuzad` 的 16 场，排行榜没有对应实体；正常回合 HDT 字段能补上，拔线时只能判"非负"。
6. **HDT 字段在重连回合不可信。** 9/9 次 `LastAttackingHero` 为空 → 字面判"平"，实际有胜有负。官方批里也有 1 次重连（`aab96c` T9，HDT 判平，排行榜显示负 15）。
7. 一个未解释的孤例：`2c27fa` T9 HDT 记我方攻击 15，排行榜上对手（德雷阿佳丝）没掉血，对手战斗英雄副本带 12 护甲。

## 结果

| 指标 | 值 |
| --- | --- |
| HDT 字段 vs 排行榜差分（无重连 594 场） | 577 一致；16 场幽灵对手；1 场孤例 |
| 团子有实际结果的 47 回合，推荐流程 | 47/47 胜负 + 伤害 |
| 同上，只用排行榜差分 | 46/46，另 1 回合幽灵判"非负"（一致） |
| 团子"不知结果"7 回合 | 全部还原；与 BB ≥ 93% 置信的预测方向 7/7 一致 |
| 团子"直接拔线"2 回合 | 全部还原（负 15、负 9），无独立对照 |

## 留下什么

- 事实：[`facts/combat-result-reconstruction.md`](../facts/combat-result-reconstruction.md)
- Q-014 关闭；还原流程写进事实文档第 4 节，P2-T3 导入时照此实现。
- 工具：`spikes/hdt-diag-logger/tools/power_replay.py`、`eval_q014_reconstruct.py`（可加 `--csv` 导出每场一行）。
