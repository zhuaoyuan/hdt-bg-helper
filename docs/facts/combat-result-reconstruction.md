# 每场战斗实际战果的还原（含拔线回合）

> 这份文档回答：不看团子文本，能否从诊断记录还原每场战斗的实际胜/平/负和伤害？拔线回合靠什么还原、准确率多少？（Q-014）

```text
实测环境：官方 HDT 1.58.3–1.58.6 与团子版 HDT 1.58.6.0 / BobsBuddy 1.78.1–1.85.0 / 插件 HdtDiagLogger 0.1.0
样本：data/BgHelperDiag 49 局 + %APPDATA%/HearthstoneDeckTracker/BgHelperDiag 6 局（去重后 55 局 / 609 场战斗，09-27~10-05）
团子对照：data/tuanzi/2026年10月04日.txt、2026年10月05日.txt（与 diag 配对 5 局）
工具：spikes/hdt-diag-logger/tools/eval_q014_reconstruct.py、power_replay.py
HDT 源码基线：v1.58.3 / 509bb0b9
最后核实：2026-10-05
证据：docs/worklog/2026-10-05-q014-result-reconstruction.md
```

## 1. 结论（先看这个）

| 问题 | 结论 |
| --- | --- |
| 正常回合能否还原？ | **能。** 两个独立信号：HDT invoker 转储里的 `LastAttackingHero` / `LastAttackingHeroAttack`，以及排行榜英雄实体的有效血量差。609 场中 598 场无重连，其中 594 场有 HDT 字段，两者 577 场胜负+伤害完全一致；其余 17 场里 16 场是对手为"幽灵"，1 场原因不明（见第 5 节）。 |
| 拔线回合能否还原？ | **能（对手不是幽灵时）。** 团子拔线会触发重连，服务器在战斗结束时重发一整块 `FULL_ENTITY - Updating`，其中带有战后的 `DAMAGE` / `ARMOR`。取这块转储结束时的排行榜血量差，就是本场战果。 |
| 准确率 | 团子有实际战果的 47 回合：推荐流程 **47/47** 胜负与伤害全对。只用排行榜差分（假装拿不到 HDT 字段）：**46/46** 全对，另 1 回合对手是幽灵只能判"非负"（与实际一致）。 |
| 拔线回合的旁证 | 团子"不知道结果"7 回合 + "直接拔线"2 回合，排行榜差分都给出了结果。7 个有 BB 预测的回合里，BB 方向置信度都 ≥ 93%，还原方向 **7/7** 与之一致；重连回合用"转储结束时"和"下一场开战时"两个时刻算出的差分 11/11 相同。 |
| HDT 自己的字段在拔线回合能用吗？ | **不能。** 重连回合里 HDT 看不到英雄攻击，`LastAttackingHero` 为空，按字面会被判成"平"（9/9 次错误）；"直接拔线"回合没有 combat_end 转储。必须按重连标记跳过它。 |

## 2. 信号一：HDT invoker 的战果字段

- HDT 在战斗中把最后一次英雄攻击记在 `LastAttackingHero` / `LastAttackingHeroAttack`（`Hearthstone Deck Tracker/BobsBuddy/BobsBuddyInvoker.cs:1969-1997`）。为空且 `DidReconnect` 时返回 `CombatResult.Reconnect`，否则为空即判平。
- 诊断插件在 `combat_end` / `game_end` 时转储整个 invoker（`records.jsonl` 的 `hdt_bb`），能直接看到这些字段，还有 `_attackingHero`、`_defendingHero`、`_reconnectCounterAtSnapshot`、中文英雄名 `_playerHeroName` / `_opponentHeroName`。
- 判定：`LastAttackingHero.$entity` 等于本场我方英雄 id → 胜，伤害 = `LastAttackingHeroAttack`；是别的英雄 → 负；为空 → 平。必须取 `_turn` 等于本场回合的那条转储。
- 团子 47 回合中 46 回合有该字段，46/46 全对；缺的 1 回合（`3a513e` T10）没有本回合的 combat_end 转储。

## 3. 信号二：排行榜英雄的有效血量差

- 每个玩家有一个带 `PLAYER_LEADERBOARD_PLACE` 的英雄实体，`CARDTYPE=HERO`；我方的就是开战快照里的 `context.player.hero`，对手的 CardId 与开战快照里 `context.opponent.hero` 的 CardId 相同（含皮肤后缀），控制者不是我方。
- 有效血量 = `HEALTH - DAMAGE + ARMOR`。护甲先扣，所以只看 `DAMAGE` 会漏掉被护甲吸收的伤害。
- 正常回合：本场所有英雄扣血在 `combat_phase=false`（END）那一行之前已经写入。
- 重连回合：END 由重连后的 `FULL_ENTITY - Updating` 全量转储触发，战后血量在 END **之后**的转储行里（例：`c88ca9` T8，END 在第 56324 行，我方 `DAMAGE=5` 在第 56396 行）。取"END 后连续的 `FULL_ENTITY - Updating` / `tag=` 行结束处"为战后时刻。
- 终局那场没有 END，用日志末尾状态；致命一击时 `DAMAGE` 会超过剩余血量，差值等于实际攻击值（例：`62725a` T15 剩 14 血，差值 42，团子写"被对面打 42"）。
- 判定：我方掉血 > 0 且对手不掉 → 负；对手掉血 > 0 且我方不掉 → 胜；都不变 → 平。
- 不要用"开战 → 下一场开战"的长窗口：商店阶段也会改血量（英雄技能、护甲获取等），47 回合里这样有 2 回合判错、2 回合双方都掉血判不出。

## 4. 推荐的还原顺序（P2-T3 用）

1. 团子文本有"实际结果"→ 直接用（来源 `tuanzi`）。
2. 本场窗口内**没有**额外 `CREATE_GAME`，且有本回合的 combat_end 转储 → HDT 字段（来源 `hdt`）。
3. 否则 → 排行榜差分（来源 `lb`）。对手是幽灵（CardId 含 `KelThuzad`）时，我方掉血判负，否则只能记 `win_or_tie`。
4. 都没有 → `unknown`。

本批 609 场按此流程：594 场来源 `hdt`，15 场来源 `lb`（11 场有重连，4 场无重连但缺本回合的 combat_end 转储）。

## 5. 限制与已知异常

| 情况 | 影响 | 本批出现 |
| --- | --- | --- |
| 对手是幽灵（`TB_BaconShop_HERO_KelThuzad`） | 排行榜上没有对应实体；胜和平无法区分，伤害未知。正常回合有 HDT 字段，不受影响 | 16/609 场（2.6%），均在后期 |
| 插件中途启用（`enabled_mid_game`） | 没有 power 日志，无法还原 | `bdd811` 一局 |
| `2c27fa` T9 | HDT 记我方英雄攻击 15，但排行榜上对手（德雷阿佳丝 `BG36_HERO_000`，剩 4 血）没掉血；对手战斗英雄副本带 12 护甲。原因不明 | 1/594 |
| 双打 | 未验证 | 0 |
| 重连发生在商店阶段而非战斗中 | **[推断]** 不影响（战后血量已经写入）；本批未出现 | 0 |
