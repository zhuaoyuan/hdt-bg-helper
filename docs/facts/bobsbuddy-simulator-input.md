# Bob's Buddy 调用方式与输入数据清单

> 这份文档回答：HDT 是怎样调用 Bob's Buddy 的；要重现一场战斗的模拟，模拟器输入里有哪些字段、每个字段从游戏状态的哪里来、什么时候被读取或更新、对手一方能不能看到。
> 这是 **P1 的主交付物**。P1-T1（源码静态分析）已完成；"对手可见性"一列目前只有源码依据，实测确认留给 P1-T3，见文末"待补全"。

```text
基线：HDT v1.58.3 / 509bb0b9
最后核实：2026-09-25
```

文中 `Invoker:N` 表示 `Hearthstone Deck Tracker/BobsBuddy/BobsBuddyInvoker.cs` 第 N 行，`Utils:N` 表示同目录下的 `BobsBuddyUtils.cs`。其他文件写成 `文件名:N`，路径都在 `Hearthstone Deck Tracker/` 下：`TagChangeActions.cs`、`PowerHandler.cs`（`LogReader/Handlers/`）、`GameEventHandler.cs`（根目录）、`BattlegroundsUtils.cs`、`GameV2.cs`、`Player.cs`（`Hearthstone/`）、`LogWatcherManager.cs`（`LogReader/`）。

附表：随从附着附魔的完整映射见 [`bobsbuddy-minion-enchantments.md`](bobsbuddy-minion-enchantments.md)。

"对手可见性"一列的写法：

- **可见** / **不可见**：源码有明确注释或专门处理作为依据。
- **HDT 直接读取**：HDT 从对手实体读取，没有特殊处理、也没有注释。说明 HDT 作者认为能读到，但没有直接证据，需要实测。
- **待实测**：源码看不出。

## 1. 调用方式

- 模拟入口：`new SimulationRunner().SimulateMultiThreaded(_input, Iterations, ThreadCount, timeAlloted)`（`Invoker:1920`）。
  - `Iterations = 10_000`（`Invoker:32`）；`ThreadCount = Environment.ProcessorCount / 2`（`Invoker:41`）。
  - 时间预算：默认 1,500ms；任一方场上随从 ≥ 6 时 3,000ms；四名玩家中任一方有 Leapfrogger 且随从 ≥ 3 时 5,000ms（`Invoker:34–37, 1897–1919`）。
- 实例：每个"对局 id + 回合"一个 `BobsBuddyInvoker`，键为 `"{gameId}_{turn}"`，存在私有静态字典 `_instances` 里，换对局时清空（`Invoker:101–118`）。回合号是 `GameV2.GetTurnNumber()` = `(GameEntity.TURN + 1) / 2`（`GameV2.cs:530–535`）。
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

- 出现不支持的交互时抛 `UnsupportedInteractionException`（包在 `AggregateException` 里），带 `Entity` 与 `Message`。HDT 先显示错误、暂不上报；之后的重跑成功则丢弃，战斗结束时仍未解决才上报（`Invoker:1941–1956, 408–430`）。
- 场上有未知卡时直接中止（`Invoker:474–478`）。

## 2. 大厅 / 对局级字段（`SnapshotBoardState`，`Invoker:885–974`）

| `Input` 字段 | 来源 | 对手可见性 |
| --- | --- | --- |
| `availableRaces` | `BattlegroundsUtils.GetAvailableRaces(gameId)`（`Invoker:906`）。**数据来自游戏进程内存**：`HearthMirror.Reflection.Client.GetAvailableBattlegroundsRaces()`，不是 Power.log；未初始化时只含 `Race.INVALID`，视为 `null`；读到后按对局 id 缓存；请求的对局不是当前对局时返回 `null`（`BattlegroundsUtils.cs:33–77`） | 不涉及 |
| `DamageCap` | `GameEntity` 的 `BACON_COMBAT_DAMAGE_CAP`（2089），仅当 `BACON_COMBAT_DAMAGE_CAP_ENABLED`（3403）> 0（`Invoker:907–908`） | 不涉及 |
| `Anomaly` | `GameEntity` 的 `BACON_GLOBAL_ANOMALY_DBID`（2897），> 0 时有效（`BattlegroundsUtils.cs:95–102`）→ `Database.GetCardFromDbfId` → `AnomalyFactory.Create`（`Invoker:956–959`） | 不涉及 |
| 回合 `turn` | `input.SetTurn(turn)`，`turn` 是 `StartCombat` 时的 `GetTurnNumber()`（`Invoker:209, 225, 961`） | 不涉及 |
| `isDuos`、`PlayerTeammate`、`OpponentTeammate` | 双人模式下另外构造队友（`Invoker:928–949`），见 5.1 | — |
| `Player`、`Opponent` | `SetupInputPlayer`，见第 3 节 | — |

注意：`Invoker:906` 在 `try` 块（`Invoker:910`）之外。`GetAvailableRaces` 返回 `null` 时 `.ToList()` 会抛异常，整个快照失败，由 `StartCombat` 的 `catch` 记日志后退出，这场战斗不模拟（`Invoker:253–260`）。

快照还会设置两个静态标志：`CurrentCombatMayHaveOpponentMalorne`（畸变为 Bring in the Buddies `BG27_Anomaly_810` 时为真，`Invoker:967`），并清空上一场残留的 Auto Assembler / 螃蟹观察标志（`Invoker:970–971`）。

## 3. 玩家级字段（`SetupInputPlayer`，`Invoker:450–883`）

对自己和对手各调用一次（`Invoker:920–921`）；双人模式下队友另调（`Invoker:930–939`）。

### 3.1 英雄与基础状态

| 字段 | 来源 | 对手可见性 |
| --- | --- | --- |
| `Health` | 英雄 `HEALTH - DAMAGE`（`Entity.Health`）+ `ARMOR`（`Invoker:518`） | HDT 直接读取 |
| `DamageTaken` | 英雄 `DAMAGE`（`Invoker:519`） | HDT 直接读取 |
| `Tier` | 英雄 `PLAYER_TECH_LEVEL`（`Invoker:520`） | HDT 直接读取 |
| `HeroIsKelThuzad` | 仅对手：对手玩家实体 `HERO_ENTITY` 指向的英雄是 `TB_BaconShop_HERO_KelThuzad` 时 `SetHeroIsKelThuzad()`（`Invoker:677–678`，`Utils:463–468`） | HDT 直接读取 |

`Invoker:513–516`（对手 `Health <= 0` 时设为 1000）紧接着就被 `Invoker:518` 覆盖，实际不起作用。

### 3.2 英雄技能（最多 2 个，`Invoker:522–597`）

取该玩家 `Board` 中的英雄技能实体，最多 2 个。每个英雄技能调用 `AddHeroPower(CardId, friendly, 是否已激活, Data, Data2, Data3, 附着随从, 实体 id)`：

| 参数 | 来源 | 对手可见性 |
| --- | --- | --- |
| 是否已激活 | `WasHeroPowerActivated`：`EXHAUSTED` 或 `BACON_HERO_POWER_ACTIVATED`；双人模式下 Embrace Your Rage（`TB_BaconShop_HP_103`）只看 `EXHAUSTED`，因为该技能在双人模式下 `BACON_HERO_POWER_ACTIVATED=1` 会重复出现但战斗中并不触发（`Utils:488–497`） | 待实测 |
| `Data` / `Data2` / `Data3` | `TAG_SCRIPT_DATA_NUM_1/2/3`（`Invoker:526–528`） | HDT 直接读取 |
| 实体 id | 英雄技能实体 id（`Invoker:596`） | — |

特殊处理：

- Teron Gorefiend（Rapid Reanimation，`BG25_HERO_103p`）、Flobbidinous Floop（Glorious Gloop，`BGDUO_HERO_101p`）：在该玩家的实体中找 `BG25_HERO_103pe` / `BGDUO_HERO_101pe2` 附魔，取其 `ATTACHED` 指向的、仍在场上且未被另一个技能认领的随从 id，**覆盖 `Data`**（`Invoker:531–557`）。己方要求附魔 `IsInPlay`，对手不要求（`Invoker:535, 548`）。
- Tavish Stormpike（Lock and Load，`BG22_HERO_000p_Alt`）：技能的 `TAG_SCRIPT_DATA_ENT_1` 指向 `SetAside` 区中被装填的随从，转换后作为附着随从；找不到时，找本回合由该技能创建（`CREATOR == 技能 id`）且位于 `PLAY` / `GRAVEYARD` / `REMOVEDFROMGAME` 的随从：在 `REMOVEDFROMGAME` 区的只记 dbfId 到 `Data3`，否则完整转换（`Invoker:559–594`）。战斗中还有补录，见 5.2。

### 3.3 任务、饰品、目标（`Invoker:599–638`）

| 项 | 来源 | 对手可见性 |
| --- | --- | --- |
| 任务 | 该玩家 `SECRET` 区的任务 / 支线任务实体（`Player.cs:113`）：`QUEST_PROGRESS`、`QUEST_PROGRESS_TOTAL`、`CardId`、`QUEST_REWARD_DATABASE_ID` → 奖励 CardId（`Invoker:599–610`） | 待实测 |
| 任务奖励 | 该玩家 `PLAY` 区的任务奖励实体（`Player.cs:115`）：`LatestCardId`、`TAG_SCRIPT_DATA_NUM_1/2`（`Invoker:612–620`） | 待实测 |
| 饰品 | 该玩家 `PLAY` 区的饰品实体（`Player.cs:114`），经 `GetTrinketFromEntity`（`Utils:439–461`），见下 | HDT 直接读取 |
| 目标对象 | 该玩家 `SECRET` 区的 objective 实体（`Player.cs:117`），经 `GetObjectiveFromEntity`（`Utils:400–408`），见下 | 待实测 |
| 神祇（Deity Sigil） | objective 为 `BG_OldGod` 时额外调用 `GetDeityFromSigil`，赋给 `AttachedMinion`（`Invoker:634–635`），见下 | 待实测 |

`GetTrinketFromEntity`（`Utils:439–461`）：

- 卡牌取 `LatestCardId`（没有才用 `CardId`）。注释说明：Lesser / Greater Crystal Ball 变成复制的饰品后，饰品实体的 `CardId` 不会随 `CHANGE_ENTITY` 更新，只有 `LatestCardId` 是对的。
- `ScriptDataNum1/2` = `TAG_SCRIPT_DATA_NUM_1/2`，**只在 > 0 时赋值**（`SetScriptDataProperties`，`Utils:390–398`）。
- `ContainerCardId` = `CardIdBeforeReveal`（没有则 `CardId`），与实际卡牌不同时才赋值；用于区分饰品来自哪个槽位（Fantastic Treasure、Growing Collection、Lesser / Greater Trinket），决定己方开战触发顺序。
- Replica Cathedral（`BG30_MagicItem_434`）：`ScriptDataNum1` 改用标签 `4696`（HearthDb 36.6.0 中无名）。
- `game_id` = 实体 id。

`GetObjectiveFromEntity`（`Utils:400–408`）：`ObjectiveFactory.Create(CardId)`；`ScriptDataNum1/2/3` = `TAG_SCRIPT_DATA_NUM_1/2/3`，都只在 > 0 时赋值。

`GetDeityFromSigil`（`Utils:415–437`）：神祇在苏醒前没有自己的实体，只以 sigil 上的标签存在。卡牌 = `BACON_EVOLUTION_CARD_ID`（2519）的 dbfId，始终建成非金色（金色只来自 Mask of Ancient Ones，由 BB 的 `DeitySigil` 自行处理）；`baseAttack/maxAttack` = `BACON_EVOLUTION_CARD_OVERWRITE_ATK`（4906），`baseHealth/maxHealth` = `BACON_EVOLUTION_CARD_OVERWRITE_HEALTH`。这是神祇的当前总属性，不是加成。注释说玩家实体上的 `BACON_OLD_GOD_ATTACK/HEALTH` 也有同样的值，但双人模式下只有 sigil 上的值按玩家区分正确。

### 3.4 场面（`Invoker:640–644`）

- 该玩家 `PLAY` 区、`IsMinion`、且 `CONTROLLER` 是该玩家的实体，**克隆**后按 `ZONE_POSITION` 升序排列（`GetOrderedMinions`，`Utils:499–500`），逐个经 `GetMinionFromEntity` 转换（见第 4 节）。**顺序是输入的一部分。**
- 进入 `SetupInputPlayer` 前先检查整块场面：任何卡 `LatestCard` 未知 → 中止；`VerifyCardIsSupported` 为 `UnknownCard`，或为 `TextChanged` 且 BB 有该卡实现 → 中止（`Invoker:466–505`）。
- 对手可见性：**可见**。对手随从在战斗开始时必须全部已知，否则 HDT 进入 `UnknownCards` 错误状态、不模拟（`Invoker:474–478`）。

### 3.5 手牌与奥秘（`Invoker:646–696`）

手牌排序：`GetOrderedHandEntities` 按 `ZONE_POSITION` 升序，**不克隆**（`Utils:502–503`）。

- 己方：
  - 奥秘：`Secrets`（`SECRET` 区且是奥秘）的 `LatestCard.DbfId` 列表（`Invoker:648`）。
  - 手牌：随从（完整转换，`CanSummon = !LITERALLY_UNPLAYABLE`）、血宝石 `BG20_GEM`、Lockbox `BG36_520t`（`ScriptDataNum1` = `TAG_SCRIPT_DATA_NUM_1`，距开启的回合数）、法术（泛化为 `SpellCardEntity`）、其他牌按 `CardId` 建 `CardEntity`（`Invoker:650–673`）。
- 对手：
  - 奥秘：`CardId` 已知的给 `DbfId`，未知的为 `null`；去重时 `null` 互不相等，所以未知奥秘各占一个（`Invoker:680–687, 2146–2170`）。快照保存的是**实体引用列表** `_opponentSecrets`，战斗中奥秘触发、`CardId` 被揭示后重新读取（见 5.2）。
  - 手牌：转换规则同己方，另外 `CardId` 为空的牌建为 `UnknownCardEntity`（`Invoker:1713–1741`）。快照保存的也是实体引用列表 `_opponentHand` / `_opponentTeammateHand`（`Invoker:689–693`）。
  - 对手可见性：奥秘和手牌**默认不可见**，只有战斗中被揭示的部分可以补上（`Invoker:1005–1048`）。

### 3.6 玩家级附魔计数器（附着在玩家实体上，`Invoker:706–882`）

- 取玩家实体上的附着实体；双人模式下只取 `IsInPlay` 的。注释（`Invoker:698–705`，称已对照 276 场双人战斗核实）：每名玩家的附魔只挂在两个玩家实体（Player、Opponent）上；换成队友战团时，游戏为队友新建一份附魔挂在同一玩家实体的 `PLAY` 区，把原来的移到 `SETASIDE`。
- 下表"对手可见性"统一为：**HDT 直接读取**（从对手玩家实体取附魔，无特殊处理）。每种附魔是否都会为对手下发，待实测。

| `Input.Player` 字段 | 来源附魔（CardId）/ 标签 | 行号 |
| --- | --- | --- |
| `EternalKnightCounter` / `EternalLegionCounter` | `BG25_008pe` 的 `NUM_1` / `NUM_3`；Legion 为 0 时改读 `BG36_MagicItem_216pe` 的 `NUM_1`；仍为 0 时读场上任一随从身上 `BG36_MagicItem_216e` 的 `NUM_1 / 4` | `Invoker:724–756` |
| `SanlaynScribeCounter` | `BGDUO31_208pe` 的 `NUM_1` | `Invoker:731–733` |
| `UndeadAttackBonus` / `UndeadHealthBonus` | `BG25_011pe` 的 `NUM_1` / `NUM_2` | `Invoker:758–764` |
| `BeastAttackBonus` / `BeastHealthBonus` | `BG34_Giant_362pe` 的 `NUM_1` / `NUM_2`，加上所有 `IsInPlay` 的 `BGS_018pe` 的 `NUM_1` / `NUM_2` 之和 | `Invoker:766–792` |
| `AncestralAutomatonCounter` | `BG_TTN_401pe` 的 `NUM_1` | `Invoker:794–796` |
| `BeetlesAtkBuff` / `BeetlesHealthBuff` | `BG31_808pe` 的 `NUM_1` / `NUM_2` | `Invoker:797–803` |
| `WhelpAttackBonus` / `WhelpHealthBonus` | `BG34_402pe` 的 `NUM_1` / `NUM_2` | `Invoker:804–811` |
| `BloodGemAtkBuff` / `BloodGemHealthBuff` | `max(BG26_159pe 的 NUM_1/2, 玩家实体 BACON_BLOODGEMBUFFATKVALUE / HEALTHVALUE)`；注释：两处各有已测到的少算情形，都只增不减，所以取最大值 | `Invoker:848–856` |
| `HauntedAtkBuff` / `HauntedHealthBuff` | `BG33_112pe` 的 `NUM_1` / `NUM_2` | `Invoker:876–882` |

血宝石加成的对手可见性另见 3.7 末尾（标签部分有跨对手残留问题）。

### 3.7 玩家级标签计数器（`Invoker:813–874`）

读取规则 `ReadPlayerCounter`：非双人模式下、对手玩家实体上附有 `IsInPlay` 的 `Bacon_TagTransferPlayerE` 时读该附魔，否则读玩家实体本身（`Invoker:715–722`）。注释：每场战斗游戏会给**对手**玩家实体挂一个 TagTransfer 附魔，用同样的标签 id 携带对手的整局计数器；对手是"鬼魂"时，对手玩家实体上的旧值可能还停留在上一场战斗。

| 字段 | 标签 | 对手可见性 |
| --- | --- | --- |
| `ElementalPlayCounter` | `2878`（`BACON_ELEMENTAL_PLAY_COUNTER`） | 可见（TagTransfer） |
| `ElementalsGiveExtraAttack` / `Health` | `BACON_ELEMENTAL_BUFFATKVALUE`（4002）/ `BACON_ELEMENTAL_BUFFHEALTHVALUE` | 可见（TagTransfer） |
| `PiratesSummonCounter` | `2358` | 可见（TagTransfer） |
| `MagnetizeCounter` | `3670` | 可见（TagTransfer） |
| `BeastsSummonCounter` | `3962` | 可见（TagTransfer） |
| `TastyLobsterCounter` | `4803` | 可见（TagTransfer） |
| `GoldenMinionsPlayedCounter` | `4799` | 可见（TagTransfer） |
| `FriendlyMinionsDeadLastCombatCounter` | `2717` | 可见（TagTransfer） |
| `BattlecryCounter` | `3236` | 可见（TagTransfer） |
| `TavernSpellCounter` | `3088` | 可见（TagTransfer） |
| `DeathrattleCounter` | `4639` | 可见（TagTransfer） |
| `VolumizerAtkBuff` / `HealthBuff` | `4468` / `4469` | 可见（TagTransfer） |
| `TavernSpellAtkBuff` / `HealthBuff` | `TAVERN_SPELL_ATTACK_INCREASE`（3989）/ `TAVERN_SPELL_HEALTH_INCREASE`：先读玩家实体（注释：游戏在 TagTransfer 之后会再把这两个值写到玩家实体上），没有再读 TagTransfer 附魔（`Invoker:860–867`） | 可见，有残留风险（见下） |
| `ResourcesSpentThisGame` | `NUM_RESOURCES_SPENT_THIS_GAME`（418），直接读玩家实体（`Invoker:825`） | **不可见**：注释"对手从不下发该标签"（`Invoker:827`，`Utils:470`）。对手场上有 Malorne 时反推，见下 |

- 上表数字标签除 2878 外在 HearthDb 36.6.0 中都没有名字，含义以 `Invoker` 中赋给的字段名为准。
- "可见（TagTransfer）"的依据是 `Invoker:715–718` 的注释。注释没有逐个标签列出，**哪些标签确实由 TagTransfer 携带，待实测**。双人模式下 HDT 不用 TagTransfer，直接读对手玩家实体（`Invoker:720`）。
- 残留风险：`TagChangeActions.cs:1684–1699` 注释说，对手的 `TAVERN_SPELL_*_INCREASE` 可能从高值降下来，而降为 0 时游戏不发更新；血宝石的 `BACON_BLOODGEMBUFF*VALUE` 也会从上一个对手残留，因为"揭示时只写非零值"。所以 HDT 在 `NEXT_OPPONENT_PLAYER_ID` 变化时把对手玩家实体上这四个标签清零，等揭示时重新写入。
- `ResourcesSpentThisGame` 的对手值（`Utils:471–486`，`Invoker:828–834`）：对手场上有 Malorne（`BG32_HERO_001_Buddy` / 金色 `_G`）时，`光环 = min(ATK − 卡面攻击 − 附魔 NUM_1 之和, HEALTH − 卡面生命 − 附魔 NUM_2 之和)`（排除 Power of Ancients 附魔 `BG32_HERO_001_Buddye`），金色再除以 2，结果 × 3。战斗中召唤出的 Malorne 另有推算，见 5.2 的 `UpdateOpponentResourcesSpentThisGame`。

## 4. 随从级字段（`GetMinionFromEntity`，`Utils:35–202`）

卡牌取 `entity.Info.LatestCardId`（原地变形后取最新卡；为空时 `"Unknown"`），经 `MinionFactory.CreateFromCardId(cardId, player)` 创建（`Utils:37–38`）。

| 字段 | 来源 | 行号 |
| --- | --- | --- |
| `PrimaryRace` | `CARDRACE` | `Utils:40` |
| `baseAttack` / `maxAttack` | `ATK` | `Utils:41, 43` |
| `baseHealth` / `maxHealth` | `HEALTH − DAMAGE` / `HEALTH` | `Utils:42, 44` |
| `taunt` | `TAUNT` | `Utils:45` |
| `div` | `DIVINE_SHIELD` 存在时为 1，否则 0 | `Utils:46` |
| `cleave` | 卡牌在 `MinionFactory.cardIDsWithCleave` 中 | `Utils:47` |
| `poisonous` / `venomous` | `POISONOUS` / `VENOMOUS` | `Utils:48–49` |
| `windfury` | `WINDFURY` | `Utils:50` |
| `megaWindfury` | `MEGA_WINDFURY`，或卡牌在 `MinionFactory.cardIdsWithMegaWindfury` 中 | `Utils:51` |
| `stealth` | `STEALTH` | `Utils:52` |
| `golden` | `PREMIUM` | `Utils:53` |
| `tier` | `TECH_LEVEL` | `Utils:54` |
| `reborn` | `REBORN` | `Utils:55` |
| `ScriptDataNum1..4` | `TAG_SCRIPT_DATA_NUM_1..4` | `Utils:56–59` |
| `EclipsionIllidari.ScoreValue2` | `SCORE_VALUE_2`（本回合剩余的"攻击时免疫"次数），仅该随从类型且标签存在 | `Utils:61–63` |
| `AttachedModularEntity` | `MODULAR_ENTITY_PART_1/2`（模块化合体的另一半） | `Utils:67–79` |
| `AdditionalDeathrattles`、`AdditionalRallies`、`HasWingmen`、血宝石属性、`Enchantments` | 附着附魔，完整映射见 [`bobsbuddy-minion-enchantments.md`](bobsbuddy-minion-enchantments.md) | `Utils:81–186` |
| 磁力合体的隐藏亡语、黑暗赐福 | 见附表第 4 节 | `Utils:189–197` |
| `game_id` | 实体 id；战斗中的补录都靠它找回对应随从 | `Utils:199` |

- 对手可见性：随从本体标签——**可见**（3.4 的依据）。附着附魔——HDT 直接读取；例外是依赖对手手牌的几种附魔，只能在战斗中补录（附表第 6 节）。
- 磁力合体后的 Auto Assembler / 螃蟹亡语，对双方都可能"藏起来"（`Utils:204–205, 238–244` 注释），HDT 在战斗中通过观察召唤结果对账（5.2）。

## 5. 触发时序

### 5.1 快照与模拟开始

**单人模式**：

1. 日志中某实体的标签 `2022`（HearthDb 中无名）由 1 变为 0（`TagChangeActions.cs:175–176, 199–224`）：
   - 置 `game.IsBattlegroundsCombatPhase = true`；
   - 若 `GameEntity.TURN` ≤ 购物阶段开始时记录的 `TURN`，判定为"购物回合里多出来的假战斗"，不启动 Bob's Buddy（`TagChangeActions.cs:206–218`）；
   - 否则 `GetInstance(gameId, 当前回合).StartCombat()`（`TagChangeActions.cs:220–221`）。
2. `StartCombat`（`Invoker:191–261`）：
   1. 清空 `_opponentHand` / `_opponentSecrets`（`Invoker:195–200`）；
   2. `ShouldRun()`：配置开关、远程禁用、最低版本（`Invoker:167–189`）；
   3. 已经处于 `Combat` 或之后的状态则退出（`Invoker:220–224`），否则**同步调用 `SnapshotBoardState`**——快照就发生在处理这一行日志的时刻（`Invoker:225`）；
   4. `State = Combat`，然后**等待 500ms 墙钟时间**（`StateChangeDelay`，`Invoker:228–235`），期间状态变了就退出；
   5. 任一方已激活 Reborn Rite（Lich King 英雄技能 `TB_BaconShop_HP_024`）时再等 2000ms（`Invoker:245–249`）；
   6. `RunAndDisplaySimulationAsync` → `RunSimulation` → `SimulateMultiThreaded`（`Invoker:251, 302–352, 1748–1920`）。

另外，标签 `3533`（无名）由 1 变为 0 时，单人和双人模式都会调用 `game.SnapshotBattlegroundsBoardState()`（`TagChangeActions.cs:231–238`）。这是 HDT 自己记录"上一次看到的对手场面"的功能（`GameV2.cs:546–550`），**不是** Bob's Buddy 的快照。

**双人模式**：

1. 标签 `3533` 由 0 变 1 时重置英雄追踪（`TagChangeActions.cs:228–229`）；由 1 变 0 时调用 `StartCombat()`（`TagChangeActions.cs:240–244`）。
2. 双人模式下每次 `StartCombat` 都会 `SnapshotBoardState`（`Invoker:207–219`）：第一次建 `Player` / `Opponent`；之后若检测到玩家实体的 `HERO_ENTITY` 变了（换成队友，`TagChangeActions.cs:259–271`，`GameV2.cs:868–883`），再建 `PlayerTeammate` / `OpponentTeammate`（`Invoker:928–940`）。队友还没齐就停在 `WaitingForTeammates`，不模拟（`Invoker:211–218`）。
3. 部分战斗：任一英雄成为 `PROPOSED_ATTACKER`（英雄攻击，意味着一方已被打完）时调用 `MaybeRunDuosPartialCombat`（`TagChangeActions.cs:789–797`），把没快照到的队友置空后模拟（`Invoker:263–300`）。

### 5.2 战斗中的更新与重跑

战斗开始后，HDT 收到以下信息时修改 `_input` 并调用 `TryRerun()`。除 `UpdateOpponentSecret` 外，都要求状态为 `Initial`、`Combat` 或 `CombatPartial`（`Invoker:165`）；`_input` 为空时一律忽略。**这意味着只在战斗开始瞬间拍快照是不完整的**，采集工具也要捕获这些更新。

`TryRerun`（`Invoker:978–1003`）：状态为 `Initial` 时不跑（双人模式下第一场战斗可能在任何状态设置前就解析完了）；否则最多重跑 11 次（`_reRunCount++ <= 10`）。它不检查初次模拟是否已经开始：`State` 在 500ms 等待之前就设为 `Combat`（`Invoker:228`），所以等待期间到达的更新会立刻启动一次模拟，等待结束后初次模拟仍会再跑一次。

下表中"PowerHandler BLOCK_END"指 `PowerHandler.cs:1782` 起处理 `BLOCK_END` 行的分支，读的是刚结束的 `CurrentBlock`；`PowerHandler.cs:1829` 起的一组只处理 `Type == "TRIGGER"` 的块。

| 方法（`Invoker` 行） | 触发位置 | 触发条件 | 读取 / 写入的数据 |
| --- | --- | --- | --- |
| `UpdateCardOpponentHand`（1005） | `TagChangeActions.cs:1252–1261`（`ZONE` 变化） | 对手控制的实体从 `SETASIDE` 进入 `PLAY`，其 `COPIED_FROM_ENTITY_ID` 指向对手手牌里一张 `CardId` 为空的牌 | 记录"隐藏手牌 → 揭示的副本"映射；用快照时的手牌实体列表重建对手手牌，只有 `MinionCardEntity` 数量增加时才替换（`Invoker:1010–1032`）。双人模式按实体所在列表区分对手和对手队友 |
| `UpdateOpponentSecret`（1035） | `GameEventHandler.cs:2932–2934` ← `PowerHandler.cs:1151–1164`（`BLOCK_START`） | `TRIGGER` 块、`triggerKeyword == "SECRET"`、来源实体属于对手；仅 `State == Combat` 且非双人模式 | 按快照时的奥秘实体列表（此时已被揭示 `CardId`）重设对手奥秘 |
| `UpdateLockAndLoadHeroPower`（1050） | ① `TagChangeActions.cs:354–365`（`COPIED_FROM_ENTITY_ID` 变化）；② `PowerHandler.cs:1923–1942`（BLOCK_END） | ① 当前块是 Lock and Load、实体是 `PLAY` 区随从且 `CREATOR` = 块来源；② Lock and Load 的 `TRIGGER_VISUAL` 块结束，找 `CREATOR` = 技能、在 `PLAY` 或 `GRAVEYARD` 的随从 | 单人模式只处理**对手**：技能的 `AttachedMinion` 和 `Data3` 都为空时，把该随从转换后挂上，`AttachedMinionCapturedDuringCombat = true`。双人模式、或对手没有该技能时转给下一行 |
| `UpdateDuosLockAndLoadHeroPower`（1074） | 仅由 `UpdateLockAndLoadHeroPower` 调用（`Invoker:1068–1069`） | 同上 | 在四名玩家中按 `game_id == CREATOR` 找技能（找不到则取第一个 Lock and Load）；随从 `DAMAGE == 0` 且在 `PLAY` 时完整转换，否则只记 dbfId 到 `Data3`（注释：BLOCK_END 时随从可能已经开过火、受伤或死亡） |
| `UpdateBackToBackSpellBonus`（1134） | `PowerHandler.cs:1982–1998`（BLOCK_END） | `POWER` 块、`CardId == BG35_952`（Back to Back） | 找 `CREATOR` = 该法术的 `BG35_952e` 附魔，`BackToBackAtk/Health` = 其 `NUM_1/2`；已有值时不覆盖 |
| `UpdateSandyTransformDuos`（1162） | `TagChangeActions.cs:367–384`（`COPIED_FROM_ENTITY_ID` 变化） | 当前块卡牌是 Sandy（`BGDUO_125` / `_G`），块来源就是该实体，实体在 `PLAY`，值非 0 | 在四名玩家场上找 `game_id` 相同的 `Sandy`，把变形后的随从挂到 `AttachedMinion`。注释：对手 Sandy 的 `SETASIDE` 复制源是隐藏创建的，不能用 |
| `UpdateFlobbidinousFloopTransformDuos`（1192） | `TagChangeActions.cs:386–399`（`COPIED_FROM_ENTITY_ID` 变化） | 当前块是 Glorious Gloop，实体是 `PLAY` 区随从，复制源在 `SETASIDE` | 技能的 `AttachedMinion` = 变形后的随从 |
| `UpdateFlobbidinousFloopConfirmedNoTransformDuos`（1218） | `PowerHandler.cs:1943–1960`（BLOCK_END） | Glorious Gloop 块结束时，`BGDUO_HERO_101pe2` 附魔仍在场上且附着的随从仍在场上（说明没有变形） | `AttachedMinionCapturedDuringCombat = true`，让模拟器不再抛"不支持的交互" |
| `UpdateSummoningSphereDuos`（1238） | `TagChangeActions.cs:401–413`（`COPIED_FROM_ENTITY_ID` 变化） | 当前块是 Summoning Sphere（`BGDUO_MagicItem_003`）或 Lesser Trinket（`BG30_Trinket_1st`），随从 `CREATOR` = 块来源，在 `SETASIDE` 或 `PLAY` | 饰品的 `AttachedMinion` = 该随从 |
| `UpdateSummoningSphereConfirmedNoSummonDuos`（1264） | `PowerHandler.cs:1961–1980`（BLOCK_END） | 上述饰品的 `TRIGGER_VISUAL` 块结束时，没有 `CREATOR` = 饰品的随从在 `PLAY` | `TrinketUpdatedDuringCombat = true` |
| `UpdateMagnanimooseSummonPoolDuos`（1285） | `PowerHandler.cs:1905–1922`（BLOCK_END） | Magnanimoose（`BGDUO_105` / `_G`）的 `DEATHRATTLE` 块结束 | `CREATOR` = 该随从、在 `PLAY` 或 `SETASIDE` 的随从列表；没放下而留在 `SETASIDE` 的副本改读复制源的属性；追加到所属玩家的 `MagnanimooseSummonPoolDuos` |
| `UpdateMinionEnchantment`（1366） | `PowerHandler.cs:1843–1856`（BLOCK_END） | `TRIGGER` 块卡牌在映射表中（Choral Mrrrglr、Costume Enthusiast、Dramaloc 等），来源属于**对手** | 找 `ATTACHED` 与 `CREATOR` 都是来源随从的附魔，挂到对手对应随从上（附表第 6 节） |
| `UpdateTrinketEnchantment`（1393） | `PowerHandler.cs:1857–1866`（BLOCK_END） | 同上但附魔没有挂在来源上（来源是饰品 Dramaloc Sticker） | 挂到对手对应饰品上 |
| `UpdateOpponentResourcesSpentThisGame`（1420） | `TagChangeActions.cs:131–133, 314–328`（`ATK` 变化） | 仅当本场畸变是 Bring in the Buddies；实体是对手的 Malorne | 对手值仍为 0、`prevAtk > 0`、Malorne 已附 Power of Ancients 时，`(新 ATK − 旧 ATK)`（金色 ÷ 2）× 3 |
| `UpdateTimewarpedMagnanimoose`（1444） | `PowerHandler.cs:1869–1886`（BLOCK_END） | Timewarped Magnanimoose（`BG34_Giant_619` / `_G`）的 `DEATHRATTLE` 块结束 | 召唤物转换后放进 BB 合成附魔 `BACON_FAKE_Magnanimoose_Enchantment` |
| `UpdateNelliesShipEnchantment`（1471） | `PowerHandler.cs:1887–1904`（BLOCK_END） | Timewarped Nellie's Ship（`BG34_Giant_074t` / `_G`）的 `DEATHRATTLE` 块结束 | 召唤物的 `Card.DbfId`（注意不是 `LatestCard`）放进合成附魔 `BACON_FAKE_NelliesShip_Enchantment` 的 `ScriptDataNum1/2` |
| Auto Assembler 亡语对账（1505–1629） | 观察：`PowerHandler.cs:262–291`（`FULL_ENTITY` 创建 Ancestral Automaton `BG_TTN_401` / `_G`，所在块是来源为已进坟场机械的 `DEATHRATTLE` 块）、`PowerHandler.cs:711–729`（`SUB_SPELL_START`，特效前缀 `ReuseFX_Mech_OverrideSpawn_Gears_Super`）；结算：`TagChangeActions.cs:775–780`（下一个 `PROPOSED_ATTACKER`）或 `StartShoppingAsync`（`Invoker:372–373`） | 见左 | 用观察到的亡语次数、召唤物金色状态和 `EXTRA_DEATHRATTLES_ADDITIONAL`（1131）推出真实顺序，替换 `AdditionalDeathrattles` 中的 Auto Assembler 条目 |
| Surf n' Surf 螃蟹亡语对账（1631–1711） | 观察：`PowerHandler.cs:293–316`（`FULL_ENTITY` 创建螃蟹 `BG27_004t2` / `BG27_004_Gt2`，块同上）；结算：`TagChangeActions.cs:782–787` 或 `Invoker:374–375` | 见左 | 同上，替换螃蟹条目 |

补充：

- 所有补录都只作用于快照里已有的对象（按 `game_id` 找随从 / 饰品 / 技能），找不到就忽略。`UpdateMinionEnchantment`、`UpdateTrinketEnchantment` 和两种亡语对账遇到已标记 `MinionUpdatedDuringCombat` / `TrinketUpdatedDuringCombat` 的对象时不再修改（`Invoker:1374, 1401, 1556, 1670`）；Timewarped Magnanimoose / Nellie 改为检查是否已挂合成附魔（`Invoker:1455, 1482`）。
- 单人模式下**己方** Tavish 的装填随从不在战斗中补录：`UpdateLockAndLoadHeroPower` 在 `isOpponent == false` 且非双人时什么也不做（`Invoker:1055–1071`），己方只靠快照时的查找（`Invoker:559–594`）。

### 5.3 战斗结束

- `StartShoppingAsync()` 的调用：玩家回合开始（购物阶段开始）时对**上一回合**的实例调用（`GameEventHandler.cs:512–520`，`turn.Item2 − 1`）；对局结束时以 `isGameOver = true` 调用（`GameEventHandler.cs:804–807`）；国服模块 HDTTools 成功后也会调用（`ChinaModuleViewModel.cs:276–282`）。
- 它依次：上报未解决的不支持交互（`Invoker:359`）；结算残留的 Auto Assembler / 螃蟹观察（`Invoker:372–375`）；切换状态；`ValidateSimulationResultAsync`（`Invoker:354–406`）。
- 购物阶段开始时 `IsBattlegroundsCombatPhase = false`（`GameEventHandler.cs:514`）。
- 断线重连：`LoadingScreenHandler.cs:157` 调 `OnGameReconnect()` 使计数器加 1；快照时记下计数器，验证时不一致就不判定结果（`Invoker:68–75`）。

## 6. 战斗结果（HDT 用于验证模拟）

- 攻防记录：`ATTACKING` / `DEFENDING` 标签变化（`TagChangeActions.cs:751–763`）→ `GameEventHandler.OnAttackEvent`（`GameEventHandler.cs:307–342`）→ `UpdateAttackingEntities`，只记英雄对英雄（`Invoker:441–448`）。
- 最后一次英雄攻击者：`PROPOSED_ATTACKER` 变化（`TagChangeActions.cs:767–800`）→ `HandleProposedAttackerChange`（`GameEventHandler.cs:380–386`）→ `HandleNewAttackingEntity` 记录 `LastAttackingHero` 及其攻击力（`Invoker:1969–1976`）。
- 胜负判定：没有英雄攻击 → 平局（或断线重连）；攻击英雄属于己方 → 胜，否则 → 负（`Invoker:1985–1997`）。
- 是否致死：攻击者攻击力 ≥ 防守英雄 `Health + ARMOR`；双人模式改用 `Simulator.GetDuosStartingHealth`（`Invoker:1999–2023`）。
- 验证前等 50ms，因为标签变化有时会稍晚被解析到（`Invoker:2056–2059`）；模拟次数 < 2500 不验证（`Invoker:2040–2044`）；第 5 回合及之前的"漏判致死"视为 bug，不上报（`Invoker:2083–2087`）。

## 7. HDT 从未赋值的 Bob's Buddy 公开可写成员

对照 `spikes/bobsbuddy-api/out/BobsBuddy-1.76.0.txt`（BB 1.76.0 公开签名，见 [`bobsbuddy-public-api.md`](bobsbuddy-public-api.md)），并在 HDT 源码中搜索成员名的赋值（2026-09-25）。

**`Input`**：公开可写的 `Anomaly`、`isDuos`、`DamageCap`、`turn`（经 `SetTurn`）、`availableRaces`、`Player`、`Opponent`、`PlayerTeammate`、`OpponentTeammate` 全部有赋值。HDT 没有调用 `SetHealths`、`SetTiers`、`SetTeammateTiers`、`AddCardsToHand`、`AddSecretFromDbfId*`（它直接设 `Player.Health` / `Tier`，奥秘用 `Player.SetSecrets`）。

**`Player`**：

| 成员 | 情况 |
| --- | --- |
| `DeepBluesCounter` | 从未赋值 |
| `AnySpellCounter` | 从未赋值 |
| `BackToBackCounter` | 从未赋值 |
| `BackToBackAtk` / `BackToBackHealth` | 快照不赋值，只在战斗中由 `UpdateBackToBackSpellBonus` 赋值（`Invoker:1134–1160`） |
| `MagnanimooseSummonPoolDuos` | 快照不赋值，只在战斗中追加（`Invoker:1343`） |
| `SetSecretsHstracker` | 未调用 |

其余计数器属性全部在 3.6–3.7 中有赋值。

**`Minion`**（HDT 赋值的见第 4 节；以下公开可写成员在 HDT 源码中没有任何赋值）：

| 成员 | 备注 |
| --- | --- |
| `SecondaryRace` | 只设 `PrimaryRace`（`CARDRACE`）。**[推断]** 由工厂按卡牌数据设置 |
| `AvengeCounter` | **[推断]** 复仇按单场战斗计数，开战时为 0 |
| `StegodonRalliesGranted` / `StegodonGoldenRalliesGranted` | — |
| `TimesTakenDamage` | — |
| `ImmuneWhileAttacking` / `ImmuneWhileAttackingCount` | Eclipsion Illidari 另用子类的 `ScoreValue2` |
| `cannotAttack`、`receivesLichKingPower` | — |
| `IsBuddy`、`IsWhelp`、`IsDeity` | **[推断]** 由子类或工厂设置 |
| `vanillaAttack` / `vanillaHealth`、`DamageMultiplier` | — |
| `InnateDeathrattleResolvesLast`（字段） | — |
| `minionName`、`attackStatus`、`LastKnownPosition`、`LastKnownNeighbors`、`LethalDamageEventId`、`LastKnownAttack`、`LastKnownHealth`、`KilledBy` | **[推断]** 模拟运行时状态 |
| `StatsFromBloodGems` | 不直接赋值，经 `SetBloodGemStats` 设置（`Utils:151`） |
| `MinionUpdatedDuringCombat` | 只在战斗中补录时置 `true` |

**`HeroPowerData`**、**`Trinket`**、**`Objective`**：公开可写成员都有赋值（`Trinket.TrinketUpdatedDuringCombat`、`HeroPowerData.AttachedMinionCapturedDuringCombat` 只在战斗中设置）。

**[推断]** 这些未赋值成员里，哪些会被 BB 在开战时读取、从而影响结果，只能通过 BB 行为实验判断（例如给 `DeepBluesCounter` 设不同值看结果是否变化）。

## 8. Q-006 的源码层结论：插件能否在同一时机拿到战斗中揭示的信息

1. HDT 没有为 Bob's Buddy 的任何更新提供公开事件。`BobsBuddyInvoker` 是 `internal`，`_input` 是私有字段，实例存在私有静态字典 `_instances`，键为 `"{gameId}_{turn}"`（`Invoker:30, 57, 94, 101–118`）。直接拿 HDT 构造好的输入只能用反射（Q-002）。
2. `LogEvents.OnPowerLogLine`（`API/LogEvents.cs:9`）把 Power.log 的每一行交给插件，调用点紧跟在 HDT 自己的 `PowerHandler.Handle` 之后、同一线程同步执行（`LogWatcherManager.cs:180–185`）。所以插件拿到每一行时，HDT 已经处理完这一行、实体状态已更新，Bob's Buddy 更新方法（BLOCK_END、标签变化触发的那些）也已被调用。**不经过**这个事件的行：以 `GameState.` 开头的行（另存入公开的 `GameV2.PowerLog`，`LogWatcherManager.cs:150–152`，`GameV2.cs:120`）、`PowerProcessor.EndCurrentTaskList`、`ChoiceCardMgr.`（`LogWatcherManager.cs:169–179`），以及被判定为回放（rewind）时间段内的行（`LogWatcherManager.cs:133–140`）。
3. HDT 的解析上下文（当前 `BLOCK` 的类型、卡牌、来源、触发关键字）在 `HsGameState` 里，而 `HsGameState` 实例是 `LogWatcherManager` 的私有字段 `_gameState`（`LogWatcherManager.cs:32, 119`），插件拿不到。5.2 表中大多数触发条件依赖 `CurrentBlock`，插件要复现就得**自己从 `OnPowerLogLine` 的行里跟踪 `BLOCK_START` / `BLOCK_END`**。
4. 实体模型是公开的：`Core.Game`（`API/Core.cs:13`）→ `GameV2.Entities`（`GameV2.cs:150`）、`Player.Board/Hand/Secrets/Trinkets/Quests/Objectives/SetAside/PlayerEntities`（`Player.cs:90–118`）、`Entity` 与 `EntityInfo`（`Entity.cs:18, 253`）都是 `public`。插件可以在 `OnPowerLogLine` 回调里读到与 HDT 相同的实体状态。注意 `PlayerEntities` 会过滤掉 `HasOutstandingTagChanges` 的实体（`Player.cs:90`）。
5. 没有"战斗开始 / 结束"事件。插件可以在日志行中自己识别标签 `2022`（单人）/ `3533`（双人）的 1→0，或在 `OnUpdate`（约 100ms）中轮询公开属性 `GameV2.IsBattlegroundsCombatPhase`（`GameV2.cs:140`；置真：`TagChangeActions.cs:203, 233`；置假：`GameEventHandler.cs:514`）。轮询有最多约 100ms 的延迟，并且会错过 HDT"假战斗"过滤（`TagChangeActions.cs:213–218`）的结果。
6. 少数公开 `GameEvents` 与 Bob's Buddy 更新同时发生：`OnOpponentSecretTriggered` 在同一处理函数里、紧挨在 `UpdateOpponentSecret` 之前（`GameEventHandler.cs:2929–2934`）；`OnPlayerMinionAttack` / `OnOpponentMinionAttack` 与 `UpdateAttackingEntities` 在同一个 `OnAttackEvent` 里（`GameEventHandler.cs:332–341`）。其余补录（手牌揭示、Tavish、Sandy、Floop、召唤法球、Magnanimoose、手牌相关附魔、Malorne、Nellie、亡语对账）没有对应的公开事件。
7. `availableRaces` 不在 Power.log 里，来自 HearthMirror 读内存；`BattlegroundsUtils` 是 `public static class`，插件可以直接调用 `GetAvailableRaces()`（`BattlegroundsUtils.cs:12, 28–31`）。离线重放日志时要另找来源。
8. **[推断]** `TagChangeActions` 的动作是排队后由 `InvokeQueuedActions` 执行的（`PowerHandler.cs:322–323, 2003–2005`），创建标签行（`creationTag`）不会触发执行。所以个别由标签变化触发的更新，在插件看到的"那一行"上可能还没执行。需要实测确认。

## 9. Q-007 的源码层结论：对手玩家级数据哪些拿不到或只能推算

| 数据 | 对手可见性 | 源码依据 |
| --- | --- | --- |
| `ResourcesSpentThisGame` | **不可见，只能推算** | 注释"对手从不下发 `NUM_RESOURCES_SPENT_THIS_GAME`"（`Invoker:827`，`Utils:470`）。只在对手场上有 Malorne 时从其光环反推（`Utils:471–486`），或 Bring in the Buddies 畸变下从战斗中 Malorne 的 `ATK` 变化推算（`Invoker:1420–1442`）；否则为 0 |
| 对手手牌 | **不可见**，战斗中部分揭示 | 未知牌建为 `UnknownCardEntity`（`Invoker:1738–1739`）；只有从手牌召唤到场上的牌能补上（5.2） |
| 对手奥秘 | **不可见**，触发时揭示 | 未知为 `null`（`Invoker:684`）；奥秘触发后补上（`Invoker:1035–1048`），双人模式不补 |
| 手牌相关附魔的数值（Choral Mrrrglr、Costume Enthusiast、Dramaloc、Dramaloc Sticker） | **只在战斗中触发时可得** | 专门只对对手来源在战斗中补录（`PowerHandler.cs:1843–1866`）。**[推断]** 数值取决于对手手牌 |
| 对手 Tavish 装填的随从 | 快照时可能拿不到，战斗中补录 | 单人模式只为对手补录（`Invoker:1057–1066`）。**[推断]** `SETASIDE` 中的装填随从对对手不可见 |
| 对手 Sandy 的复制源 | 不可用 | 注释：对手一侧的 `SETASIDE` 复制源是隐藏创建的，揭示时已在 `REMOVEDFROMGAME`（`TagChangeActions.cs:367–370`） |
| 3.7 中 13 个整局标签计数器 | **可见，但要读 TagTransfer 附魔** | 注释：每场战斗给对手玩家实体挂 `Bacon_TagTransferPlayerE`，携带对手的整局计数器；鬼魂对手的玩家实体可能是旧值（`Invoker:715–722`）。逐个标签是否都在其中，待实测 |
| `TavernSpellAtkBuff` / `HealthBuff`、血宝石加成标签部分 | 可见，**有跨对手残留风险** | 揭示时只写非零值，HDT 在换对手时清零（`TagChangeActions.cs:1684–1699`）；酒馆法术加成先读玩家实体、再读 TagTransfer（`Invoker:860–867`） |
| 3.6 中的玩家附魔计数器 | HDT 直接读取 | 注释：每名玩家的附魔挂在各自玩家实体上（`Invoker:698–705`）；没有针对对手的特殊处理。待实测 |
| `DeepBluesCounter`、`AnySpellCounter`、`BackToBackCounter` | 双方都没有 | HDT 从未赋值（第 7 节） |
| `BackToBackAtk` / `Health` | 双方都只在战斗中可得 | 只由 `UpdateBackToBackSpellBonus` 赋值 |
| 英雄技能是否已激活、任务、目标、神祇 | 待实测 | HDT 读取方式对双方相同，源码没有说明对手是否可见 |

## 待补全

- [x] ~~`Utils:160` 之后的附着附魔映射全表，以及 `GetMinionFromEntity` 的剩余逻辑~~ → 第 4 节与 [`bobsbuddy-minion-enchantments.md`](bobsbuddy-minion-enchantments.md)
- [x] ~~`GetTrinketFromEntity`、`GetObjectiveFromEntity`、`GetOrderedMinions`、`GetOrderedHandEntities`、`WasHeroPowerActivated`、`GetDeityFromSigil`、`GetResourcesSpentThisGameFromMalorne`~~ → 3.2–3.5、3.7
- [x] ~~`BattlegroundsUtils.GetAvailableRaces`、`GetBattlegroundsAnomalyDbfId`~~ → 第 2 节
- [x] ~~`TagChangeActions.cs` / `PowerHandler.cs` 中每个战斗中更新的触发条件~~ → 第 5 节
- [x] ~~`Input`、`Player`、`Minion` 中 HDT 没有赋值的字段~~ → 第 7 节
- [ ] 每个字段的采集时机、对手可见性（实测确认）、版本敏感度标注（P1-T3）。重点：3.7 各标签是否都由 TagTransfer 携带；3.6 各玩家附魔、英雄技能激活状态、任务 / 目标 / 神祇对对手是否可见；标签 `2022` / `3533` 的实际含义。
- [ ] 第 7 节未赋值成员中，哪些会被 BB 读取、影响结果（需要 BB 行为实验）。
- [ ] 第 8 节第 8 条（排队的标签变化动作与 `OnPowerLogLine` 的先后）需要实测。
