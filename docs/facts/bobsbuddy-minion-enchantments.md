# 随从附着附魔 → Bob's Buddy `Minion` 字段映射

> 这份文档回答：HDT 把随从身上附着的附魔实体转换成 Bob's Buddy `Minion` 的哪些字段；磁力合体、战斗中补录的附魔又是怎样处理的。
> 这是 [`bobsbuddy-simulator-input.md`](bobsbuddy-simulator-input.md) 第 4 节的附表。

```text
基线：HDT v1.58.3 / 509bb0b9
CardId 字符串：用本机 HearthDb.dll 36.6.0、BobsBuddy.dll 1.76.0（C:\Program Files\HDT）反射解析常量得到
最后核实：2026-09-25
```

`Utils:N` 表示 `Hearthstone Deck Tracker/BobsBuddy/BobsBuddyUtils.cs` 第 N 行，`Invoker:N` 表示同目录下的 `BobsBuddyInvoker.cs`。

## 1. 附着实体从哪来

- 取法：`GetAttachedEntities(id)` 取 `_game.Entities` 中 `IsAttachedTo(id)`（即 `ATTACHED == id`）且位于 `PLAY`、`SETASIDE` 或 `GRAVEYARD` 区的实体，**克隆**后返回（`Invoker:1743–1746`）。
- 场上随从调用 `GetMinionFromEntity` 时传入 `_game.Entities` 作为 `allEntities`（`Invoker:640–642`）；手牌随从、Tavish 装填的随从、战斗中补录的随从**不传**（`Invoker:566, 591, 655, 1063, 1123, 1185, 1211, 1259, 1322, 1460, 1721`），所以第 4 节的磁力模块检查对它们不执行（`Utils:209–210, 247–248, 312–313, 345–346` 在 `allEntities == null` 时直接返回）。
- 附魔按 `attachedEntities` 的枚举顺序逐个处理（`Utils:81`），同一个附魔 CardId 出现几次就处理几次。`AdditionalDeathrattles` 的顺序就是模拟器触发这些额外亡语的顺序（`Invoker:1616–1618` 注释）。

## 2. 按 CardId 特殊处理的附魔（`Utils:81–173`）

| 附魔 CardId | HearthDb / BB 常量名 | 写入的 `Minion` 字段 | 行号 |
| --- | --- | --- | --- |
| `BG_BOT_312e` | `ReplicatingMenace_ReplicatingMenaceEnchantmentBATTLEGROUNDS` | `AdditionalDeathrattles += ReplicatingMenace.Deathrattle(false)` | `Utils:85–87` |
| `TB_BaconUps_032e` | `ReplicatingMenace_ReplicatingMenaceEnchantmentTavernBrawl`（金色） | `AdditionalDeathrattles += ReplicatingMenace.Deathrattle(true)` | `Utils:88–90` |
| `BG33_807e` | `WhirringProtector_WhirringProtectorEnchantment` | `AdditionalRallies += WhirringProtector.Rally(false)` | `Utils:91–93` |
| `BG33_807_Ge` | `WhirringProtector_WhirringProtector2`（金色） | `AdditionalRallies += WhirringProtector.Rally(true)` | `Utils:94–96` |
| `UNG_999t2e` | `LivingSporesToken2` | `AdditionalDeathrattles += GenericDeathrattles.Plants` | `Utils:97–99` |
| `BG21_HERO_030pe` | `Sneed_Replicate`（Sneed 英雄技能） | `AdditionalDeathrattles += GenericDeathrattles.SneedHeroPower` | `Utils:100–102` |
| `BG22_HERO_001p_t1e` | `Brukan_ElementEarth` | `AdditionalDeathrattles += GenericDeathrattles.EarthInvocationDeathrattle` | `Utils:103–105` |
| `BG27_004e` | `SurfnSurf_CrabRidingEnchantment` | `AdditionalDeathrattles += GenericDeathrattles.Crab` | `Utils:106–108` |
| `BG27_004_Ge` | `SurfnSurf_CrabRiding`（金色） | `AdditionalDeathrattles += GenericDeathrattles.CrabGolden` | `Utils:109–111` |
| `BG22_HERO_001_Buddy_e1` | `Brukan_EarthRecollection` | `AdditionalDeathrattles += BrukanInvocationDeathrattles.Earth` | `Utils:112–114` |
| `BG22_HERO_001_Buddy_e2` | `Brukan_FireRecollection` | `AdditionalDeathrattles += BrukanInvocationDeathrattles.Fire` | `Utils:115–117` |
| `BG22_HERO_001_Buddy_e3` | `Brukan_WaterRecollection` | `AdditionalDeathrattles += BrukanInvocationDeathrattles.Water` | `Utils:118–120` |
| `BG22_HERO_001_Buddy_e4` | `Brukan_LightningRecollection` | `AdditionalDeathrattles += BrukanInvocationDeathrattles.Lightning` | `Utils:121–123` |
| `TB_BaconShop_HP_069e` | `Wingmen_WingmenEnchantmentTavernBrawl` | `HasWingmen = true` | `Utils:124–126` |
| `BG30_119e` | `SkyPirateFlagbearer_FlagbearingEnchantment` | `AdditionalDeathrattles += Scallywag.Deathrattle(false)` | `Utils:127–129` |
| `BG30_119_Ge` | `SkyPirateFlagbearer_Flagbearing`（金色） | `AdditionalDeathrattles += Scallywag.Deathrattle(true)` | `Utils:130–132` |
| `BG21_000e` | `Leapfrogger_LeapfrogginEnchantment` | `AdditionalDeathrattles += Leapfrogger.Deathrattle(false)` | `Utils:133–135` |
| `BG21_000_Ge` | `Leapfrogger_Leapfroggin`（金色） | `AdditionalDeathrattles += Leapfrogger.Deathrattle(true)` | `Utils:136–138` |
| `BG30_MagicItem_917e` | `RustyTrident_TridentsTreasureEnchantment` | `AdditionalDeathrattles += RustyTrident.Deathrattle()` | `Utils:139–141` |
| `BG30_MagicItem_411e` | `HoggyBank_GemInTheBankEnchantment` | `AdditionalDeathrattles += HoggyBank.Deathrattle()` | `Utils:142–144` |
| `BG30_MagicItem_952e` | `JarredFrostling_FrostyGlobeEnchantment` | `AdditionalDeathrattles += JarredFrostling.Deathrattle()` | `Utils:145–147` |
| `BG20_GEMe2` | `BloodGems` | `SetBloodGemStats(附魔 NUM_1, 附魔 NUM_2)`（血宝石累计加成） | `Utils:148–152` |
| `BG36_MidGameEffect_000t15e` | BB `TorethsBlessing.CardId` | `EnchantmentFactory.Create` 后 `ScriptDataNum1 = 宿主随从的 DIVINE_SHIELD 标签值`（剩余可挡次数，不一定是 3），再 `AttachEnchantment` | `Utils:153–163` |
| `BG31_176e2` | BB `BoomingEnchantment.CardId` | 需要同一宿主上还有 `BG31_176e`（`DrBoomsMonster_DrBoomsMonsterEnchantment`）；`ScriptDataNum1/2` 取自后者的 `NUM_1/2`，再 `AttachEnchantment`；找不到后者则丢弃 | `Utils:164–173` |

## 3. 其余附魔（通用分支，`Utils:174–185`）

- 条件：附着实体的 `LatestCard` 类型是 `ENCHANTMENT`，且 `LatestCardId` 非空。
- 处理：`EnchantmentFactory.Create(LatestCardId, ControlledByPlayer)`；返回非 `null`（即 BB 有这个附魔的实现）时，`ScriptDataNum1/2 = 附魔 NUM_1/2`，`AttachEnchantment`。
- 返回 `null` 的附魔**被静默丢弃**，不报错。**[推断]** 纯属性附魔的效果已经体现在随从的 `ATK`/`HEALTH` 标签里，BB 不需要它们；哪些附魔有实现要看 `BobsBuddy.Enchantments.*` 的公开类型列表（`spikes/bobsbuddy-api/out/`）。
- 通过这条分支进入的、HDT 源码中有显式引用的 BB 附魔类：`AutoAssemblerEnchantment`（`BG32_172e`）、`AutoAssemblerEnchantmentGolden`（`BG32_172_Ge`）（`Utils:295–297` 的计数依赖它们已被当作附魔挂上）。

## 4. 磁力合体的额外处理（`Utils:189–197`）

只要附着实体中有任何一个带 `MAGNETIC` 标签，就执行：

| 函数 | 适用 | 做什么 | 行号 |
| --- | --- | --- | --- |
| `CheckForMagnetizedDeathrattles` | 仅机械 | 对每个带 `MAGNETIC` 的附魔，取其 `CREATOR`（产生它的磁力随从，排除宿主自身），数该磁力随从身上附着的 `BG32_172e` / `BG32_172_Ge` 个数，按个数追加 `AutoAssembler.Deathrattle()` / `GoldenDeathrattle()` | `Utils:206–236` |
| `CheckForSurfnSurfFromMagnetizedModules` | 所有种族（Technical Element 可磁吸到元素） | 找 `NUM_1 == 宿主 id`、带 `MAGNETIC`、类型为随从的模块，把模块身上的 `BG27_004e` / `BG27_004_Ge` 转成螃蟹亡语 | `Utils:310–339` |
| `CheckForRepeatedMagnetizedAutoAssemblers` | 所有 | 数融入宿主的 Auto Assembler 模块：①宿主上带 `MAGNETIC` 的附魔，`CREATOR_DBID` 是 `BG32_172` / `BG32_172_G` 时以其 `CREATOR` 为模块；②`REMOVEDFROMGAME` 区、`NUM_1 == 宿主 id` 的 Auto Assembler 实体。扣掉宿主已带的 `BG32_172e` 个数（宿主本身是 Auto Assembler 再扣 1），按实体 id 顺序追加亡语 | `Utils:245–305` |
| `CheckForDarkGiftsOnMagnetizedModules` | 所有 | 对磁力附魔的 `CREATOR` 实体，查其附着的黑暗赐福：`JawsOfDeath`（`BG36_MidGameEffect_000t16e`，仅当宿主 `START_OF_COMBAT != 0`）、`OffensiveSacrifice`（`…000te2`）、`DefensiveSacrifice`（`…000t2e2`）、`Invulnerability`（`…000t60e`），分别 `AttachEnchantment` | `Utils:343–388` |

源码注释说明了原因：Auto Assembler 的附魔 `NUM_1` 累计的是属性而不是次数，一次次磁吸会合并进同一个附魔，所以只能靠 `REMOVEDFROMGAME` 区的模块实体来计数（`Utils:238–244`）。

## 5. 非附魔来源的随从字段

| 字段 | 来源 | 行号 |
| --- | --- | --- |
| `AttachedModularEntity` / 模块的 `AttachedTo` | `MODULAR_ENTITY_PART_1/2` 两个都 > 0 且其中之一等于自身 `LatestCard.DbfId` 时，另一个 dbfId 建成模块随从 | `Utils:67–79` |
| `EclipsionIllidari.ScoreValue2` | `SCORE_VALUE_2`（本回合剩余的"攻击时免疫"次数）；仅当该标签存在 | `Utils:61–63` |

## 6. 战斗中补录到随从 / 饰品上的附魔

这些不经过 `GetMinionFromEntity`，而是战斗开始后由 `Invoker` 的更新方法直接修改 `_input` 中的对象（触发条件见主文档第 5 节）。

| 方法 | 写入 | 行号 |
| --- | --- | --- |
| `UpdateMinionEnchantment` | 对手随从：`EnchantmentFactory.Create(附魔 LatestCardId)`，`ScriptDataNum1/2` 取附魔 `NUM_1/2`，`AttachEnchantment`，置 `MinionUpdatedDuringCombat = true`（之后同一随从不再接受补录） | `Invoker:1366–1391` |
| `UpdateTrinketEnchantment` | 对手饰品：同上，置 `TrinketUpdatedDuringCombat = true` | `Invoker:1393–1418` |
| `UpdateTimewarpedMagnanimoose` | 创建 BB 合成附魔 `BACON_FAKE_Magnanimoose_Enchantment`（游戏里不存在此实体），`SummonedMinions` = 观察到的召唤物 | `Invoker:1444–1469` |
| `UpdateNelliesShipEnchantment` | 创建 BB 合成附魔 `BACON_FAKE_NelliesShip_Enchantment`，`ScriptDataNum1/2` = 召唤物的前两个 dbfId | `Invoker:1471–1495` |
| Auto Assembler / 螃蟹亡语对账 | 用观察到的召唤顺序和金色状态**替换** `AdditionalDeathrattles` 中已有的对应条目 | `Invoker:1552–1629, 1666–1711` |

`UpdateMinionEnchantment` 会补录的附魔（来源映射在 `PowerHandler.cs:1832–1841`）：

| 来源随从 / 饰品 | 补录的附魔 |
| --- | --- |
| `BG26_354` Choral Mrrrglr（含金色）、`BG34_Giant_321` Timewarped Mrrrglr | `BG26_354e` |
| `BG34_142` Costume Enthusiast（含金色） | `BG34_142e` |
| `BG34_143` Dramaloc | `BG34_143e` |
| `BG35_MagicItem_754` Dramaloc Sticker（饰品，走 `UpdateTrinketEnchantment`） | `BG35_MagicItem_754e` |

**[推断]** 这几张卡的附魔数值取决于对手手牌，快照时对手手牌不可见，所以只能在战斗中触发时从新建的附魔上读。
