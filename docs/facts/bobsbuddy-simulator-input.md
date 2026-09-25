# Bob's Buddy 调用方式与输入数据清单（草稿）

> 这份文档回答：HDT 是怎样调用 Bob's Buddy 的；要重现一场战斗的模拟，模拟器输入里有哪些字段、每个字段从游戏状态的哪里来。
> 这是 **P1 的主交付物**，目前是 P0 摸底阶段的草稿，**不完整**。未覆盖的部分见文末"待补全"。

```text
基线：HDT v1.58.3 / 509bb0b9
最后核实：2026-09-25
```

文中 `Invoker:N` 表示 `Hearthstone Deck Tracker/BobsBuddy/BobsBuddyInvoker.cs` 第 N 行，`Utils:N` 表示同目录下的 `BobsBuddyUtils.cs`。

## 1. 调用方式

- 模拟入口：`new SimulationRunner().SimulateMultiThreaded(_input, Iterations, ThreadCount, timeAlloted)`（`Invoker:1920`）。
  - `Iterations = 10_000`（`Invoker:32`）；`ThreadCount = Environment.ProcessorCount / 2`（`Invoker:41`）。
  - 时间预算：默认 1,500ms；任一方场上随从 ≥ 6 时 3,000ms；有 Leapfrogger 且随从 ≥ 3 时 5,000ms（`Invoker:34–37, 1897–1919`）。
- 用到的 Bob's Buddy 命名空间：`BobsBuddy`、`BobsBuddy.Simulation`（`Simulator`、`Input`、`Player`、`SimulationRunner`）、`BobsBuddy.Enchantments`、`BobsBuddy.Minions.*`、`BobsBuddy.Trinkets`、`BobsBuddy.Utils`（`Invoker:14–26`）。
- 工厂：`simulator.MinionFactory.CreateFromCardId`、`TrinketFactory`、`ObjectiveFactory`、`AnomalyFactory.Create`、`EnchantmentFactory.Create`。
- 支持性校验：`SupportedCards.VerifyCardIsSupported(card.Data)`，返回 `UnknownCard` 或（对已有实现的卡）`TextChanged` 时不模拟（`Invoker:480–504`）。

### 输出字段

`Output` 中被 HDT 使用的字段（`Invoker:319–351, 1929–1936`）：

| 字段 | 含义 |
| --- | --- |
| `winRate` / `tieRate` / `lossRate` | 胜 / 平 / 负概率 |
| `theirDeathRate` / `myDeathRate` | 对手 / 我方被这场战斗打死的概率 |
| `damageResults` | 伤害结果分布 |
| `simulationCount` | 实际完成的模拟次数 |
| `myExitCondition` | 结束原因（如 `Simulator.ExitConditions.Time`） |

模拟次数 ≤ 500 且因超时结束时，HDT 视为数据不足，不显示结果（`Invoker:319–324`）。

### 异常

- 出现不支持的交互时抛 `UnsupportedInteractionException`（包在 `AggregateException` 里），带 `Entity` 与 `Message`（`Invoker:1941–1956`）。
- 场上有未知卡时直接中止（`Invoker:474–478`）。

## 2. 大厅 / 对局级字段（`SnapshotBoardState`，`Invoker:885–975`）

| `Input` 字段 | 来源 |
| --- | --- |
| `availableRaces` | `BattlegroundsUtils.GetAvailableRaces(gameId)`（`Invoker:906`） |
| `DamageCap` | `GameEntity` 的 `BACON_COMBAT_DAMAGE_CAP`，仅当 `BACON_COMBAT_DAMAGE_CAP_ENABLED > 0`（`Invoker:907–908`） |
| `Anomaly` | `BattlegroundsUtils.GetBattlegroundsAnomalyDbfId(GameEntity)` → `AnomalyFactory.Create`（`Invoker:956–959`） |
| 回合 | `input.SetTurn(turn)`（`Invoker:961`） |
| `isDuos`、`PlayerTeammate`、`OpponentTeammate` | 双人模式下另外构造队友（`Invoker:928–949`） |
| `Player`、`Opponent` | `SetupInputPlayer`，见第 3 节 |

## 3. 玩家级字段（`SetupInputPlayer`，`Invoker:450–883`）

### 3.1 英雄与基础状态

| 字段 | 来源 |
| --- | --- |
| `Health` | 英雄 `Health + ARMOR`（`Invoker:518`） |
| `DamageTaken` | 英雄 `DAMAGE`（`Invoker:519`） |
| `Tier` | 英雄 `PLAYER_TECH_LEVEL`（`Invoker:520`） |

### 3.2 英雄技能（最多 2 个，`Invoker:522–597`）

每个英雄技能：`CardId`、是否已激活（`WasHeroPowerActivated`）、`TAG_SCRIPT_DATA_NUM_1/2/3`、实体 id、可选的附着随从。以下英雄技能有特殊处理：

- Teron Gorefiend（Rapid Reanimation）、Flobbidinous Floop（Glorious Gloop）：通过 `ATTACHED` 找到附着的场上随从。
- Tavish Stormpike（Lock and Load）：从 `SetAside` 区或本回合由该技能创建的随从中找到被装填的随从。

### 3.3 任务、饰品、目标（`Invoker:599–638`）

- 任务：`QUEST_PROGRESS`、`QUEST_PROGRESS_TOTAL`、任务 `CardId`、`QUEST_REWARD_DATABASE_ID`。
- 任务奖励：`LatestCardId`、`TAG_SCRIPT_DATA_NUM_1/2`。
- 饰品：`GetTrinketFromEntity`（`Utils:439`，**待展开**）。
- 目标对象：`GetObjectiveFromEntity`（`Utils:400`，**待展开**）；Deity Sigil 需要额外取出将要召唤的神祇（`Invoker:633–635`）。

### 3.4 场面（`Invoker:640–644`）

- 按 `GetOrderedMinions`（`Utils:499`）排序的、受该玩家控制的场上随从，逐个经 `GetMinionFromEntity` 转换（见第 4 节）。**顺序是输入的一部分。**

### 3.5 手牌与奥秘（`Invoker:646–696`）

- 己方：
  - 奥秘：`Secrets` 的 `DbfId` 列表。
  - 手牌：随从（完整转换，`CanSummon = !LITERALLY_UNPLAYABLE`）、血宝石、Lockbox（带 `TAG_SCRIPT_DATA_NUM_1`）、法术（泛化为 `SpellCardEntity`）、其他牌按 `CardId`。
- 对手：
  - 是否 Kel'Thuzad 英雄。
  - 奥秘：已知的给 `DbfId`，未知的为 `null`（未知奥秘不去重）。
  - 手牌：已知实体按类型转换，未知的为 `UnknownCardEntity`。战斗中揭示后会更新（见第 5 节）。

### 3.6 玩家级附魔计数器（附着在玩家实体上，`Invoker:706–882`）

双人模式下只取 `IsInPlay` 的附魔（`Invoker:706–708`）。

| `Input.Player` 字段 | 来源附魔 / 标签 |
| --- | --- |
| `EternalKnightCounter` / `EternalLegionCounter` | Eternal Knight 玩家附魔 `NUM_1` / `NUM_3`；备选 Greater Eternal Portrait 玩家附魔 `NUM_1`；再备选场上 Eternal Knight 身上的 Legion 附魔 `NUM_1 / 4` |
| `SanlaynScribeCounter` | Sanlayn Scribe 玩家附魔 `NUM_1` |
| `UndeadAttackBonus` / `UndeadHealthBonus` | Nerubian Deathswarmer 玩家附魔 `NUM_1` / `NUM_2` |
| `BeastAttackBonus` / `BeastHealthBonus` | Timewarped Goldrinn 玩家附魔 + 所有在场 Goldrinn 玩家附魔之和 |
| `AncestralAutomatonCounter` | Ancestral Automaton 玩家附魔 `NUM_1` |
| `BeetlesAtkBuff` / `BeetlesHealthBuff` | Runed Progenitor Beetle Army 玩家附魔 `NUM_1` / `NUM_2` |
| `WhelpAttackBonus` / `WhelpHealthBonus` | Burgeoning Whelp 玩家附魔 `NUM_1` / `NUM_2` |
| `BloodGemAtkBuff` / `BloodGemHealthBuff` | `max(Moon-Bacon Jazzer 玩家附魔, BACON_BLOODGEMBUFFATKVALUE / HEALTHVALUE 标签)` |
| `HauntedAtkBuff` / `HauntedHealthBuff` | Haunted Carapace 玩家附魔 `NUM_1` / `NUM_2` |

### 3.7 玩家级标签计数器（`Invoker:813–874`）

读取规则 `ReadPlayerCounter`：非双人模式下、对手身上附有 `TagTransferPlayerEnchant` 时读该附魔，否则读玩家实体本身（`Invoker:715–722`）。原因是对手为"鬼魂"时，玩家实体上的旧值可能还停留在上一场战斗。

| 字段 | 标签 |
| --- | --- |
| `ElementalPlayCounter` | `2878` |
| `ElementalsGiveExtraAttack` / `Health` | `BACON_ELEMENTAL_BUFFATKVALUE` / `BACON_ELEMENTAL_BUFFHEALTHVALUE` |
| `PiratesSummonCounter` | `2358` |
| `MagnetizeCounter` | `3670` |
| `BeastsSummonCounter` | `3962` |
| `TastyLobsterCounter` | `4803` |
| `GoldenMinionsPlayedCounter` | `4799` |
| `FriendlyMinionsDeadLastCombatCounter` | `2717` |
| `BattlecryCounter` | `3236` |
| `TavernSpellCounter` | `3088` |
| `DeathrattleCounter` | `4639` |
| `VolumizerAtkBuff` / `HealthBuff` | `4468` / `4469` |
| `TavernSpellAtkBuff` / `HealthBuff` | `TAVERN_SPELL_ATTACK_INCREASE` / `TAVERN_SPELL_HEALTH_INCREASE`，先读玩家实体，没有再读 TagTransfer 附魔 |
| `ResourcesSpentThisGame` | `NUM_RESOURCES_SPENT_THIS_GAME`；**对手从不下发该标签**，只能从对手场上的 Malorne 反推（`Invoker:825–834`），或战斗中从 Malorne 的攻击力变化推算（`Invoker:1420–1442`） |

## 4. 随从级字段（`GetMinionFromEntity`，`Utils:35` 起）

已读部分（`Utils:35–160`）：

| 字段 | 来源 |
| --- | --- |
| 卡牌 | `entity.Info.LatestCardId`（原地变形后取最新卡） |
| `PrimaryRace` | `CARDRACE` |
| `baseAttack` / `maxAttack` | `ATK` |
| `baseHealth` / `maxHealth` | `HEALTH - DAMAGE` / `HEALTH` |
| 关键词 | `TAUNT`、`DIVINE_SHIELD`、`POISONOUS`、`VENOMOUS`、`WINDFURY`、`MEGA_WINDFURY`（另有卡牌列表）、`STEALTH`、`REBORN`；`cleave` 来自卡牌列表 |
| `golden` | `PREMIUM` |
| `tier` | `TECH_LEVEL` |
| `ScriptDataNum1..4` | `TAG_SCRIPT_DATA_NUM_1..4` |
| Eclipsion Illidari | `SCORE_VALUE_2` |
| 磁力 / 模块化合体 | `MODULAR_ENTITY_PART_1/2` |
| 附着附魔 | 按附魔 `CardId` 映射为额外亡语、额外集结（Rally）、Wingmen、血宝石属性、Toreth's Blessing 等，**列表很长，待逐条整理** |

附着实体的取法：`IsAttachedTo(entityId)` 且位于 `PLAY`、`SETASIDE` 或 `GRAVEYARD` 区（`Invoker:1743–1746`）。

## 5. 战斗中揭示、会触发重新模拟的信息

HDT 在战斗开始后收到以下信息时更新 `_input` 并调用 `TryRerun()`（每场战斗最多约 11 次，`Invoker:978–1003`）。**这意味着只在战斗开始瞬间拍快照是不完整的**，采集工具也要捕获这些更新。

| 方法 | 更新内容 | 位置 |
| --- | --- | --- |
| `UpdateCardOpponentHand` | 对手手牌揭示 | `Invoker:1005` |
| `UpdateOpponentSecret` | 对手奥秘（仅单人模式） | `Invoker:1035` |
| `UpdateLockAndLoadHeroPower` / `UpdateDuosLockAndLoadHeroPower` | Tavish 装填的随从 | `Invoker:1050, 1074` |
| `UpdateBackToBackSpellBonus` | 连续法术加成 | `Invoker:1134` |
| `UpdateSandyTransformDuos` | Sandy 变形（双人） | `Invoker:1162` |
| `UpdateFlobbidinousFloopTransformDuos` / `...ConfirmedNoTransformDuos` | Floop 变形 | `Invoker:1192, 1218` |
| `UpdateSummoningSphereDuos` / `...ConfirmedNoSummonDuos` | 召唤法球饰品 | `Invoker:1238, 1264` |
| `UpdateMagnanimooseSummonPoolDuos` | Magnanimoose 召唤池 | `Invoker:1285` |
| `UpdateMinionEnchantment` | 随从附魔 | `Invoker:1366` |
| `UpdateTrinketEnchantment` | 饰品附魔 | `Invoker:1393` |
| `UpdateOpponentResourcesSpentThisGame` | 对手本局花费资源（由 Malorne 推算） | `Invoker:1420` |
| `UpdateTimewarpedMagnanimoose` | 时空 Magnanimoose 召唤列表 | `Invoker:1444` |
| `UpdateNelliesShipEnchantment` | Nellie 船上的卡 | `Invoker:1471` |
| Auto Assembler 亡语对账 | 磁力后 Auto Assembler 额外亡语的真实顺序与金色状态 | `Invoker:1505–1629` |
| Surf n' Surf 螃蟹亡语对账 | 获得的螃蟹亡语顺序与金色状态 | `Invoker:1636–1711` |

## 6. 战斗结果（HDT 用于验证模拟）

- 最后一次英雄攻击者：`HandleNewAttackingEntity` 记录 `LastAttackingHero` 及其攻击力（`Invoker:1969–1976`）。
- 胜负判定：没有英雄攻击 → 平局（或断线重连）；攻击英雄属于己方 → 胜，否则 → 负（`Invoker:1985–1997`）。
- 是否致死：攻击者攻击力 ≥ 防守英雄 `Health + ARMOR`（`Invoker:1999–2023`）。

## 待补全（P1-T1）

- [ ] `Utils:160` 之后的附着附魔映射全表，以及 `GetMinionFromEntity` 的剩余逻辑
- [ ] `GetTrinketFromEntity`、`GetObjectiveFromEntity`、`GetOrderedMinions`、`GetOrderedHandEntities`、`WasHeroPowerActivated`、`GetDeityFromSigil`、`GetResourcesSpentThisGameFromMalorne`
- [ ] `BattlegroundsUtils.GetAvailableRaces`、`GetBattlegroundsAnomalyDbfId`
- [ ] `TagChangeActions.cs` / `PowerHandler.cs` 中每个战斗中更新的触发条件
- [ ] `Input`、`Player`、`Minion` 中 HDT **没有**赋值、但 Bob's Buddy 可能会读的字段（P1-T2 已导出公开签名，见 [`bobsbuddy-public-api.md`](bobsbuddy-public-api.md)）。已确认的：`Player.DeepBluesCounter`、`Player.AnySpellCounter`、`Player.BackToBackCounter` 在 BB 1.76.0 中是公开可写属性，HDT 源码（基线）里没有任何地方赋值；`BackToBackAtk/Health` 只在战斗中由 `UpdateBackToBackSpellBonus` 赋值（`Invoker:1134–1155`）。`Minion` 的剩余字段还没逐一对照。
- [ ] 每个字段的采集时机、可见性、版本敏感度标注（P1-T3）
