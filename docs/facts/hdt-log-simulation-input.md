# HDT 日志中的模拟输入/输出与本机修改版 HDT

> 这份文档回答：HDT 日志里 Bob's Buddy 的 `Simulation Input` / `Output` 段落写了什么、够不够重建模拟器输入、能不能当对照基准（Q-004）；本机装的修改版 HDT 相对上游改了什么（Q-010）。

```text
源码基线：HDT v1.58.3 / 509bb0b9（日志语句与日志实际来源版本 1.57.12 / bb3493f2 相同，见 1.1）
实测环境：Windows 10 19045；日志来自修改版 HDT 1.49.2 – 1.57.12（2026-02-08 至 2026-09-24，共 26 个日志文件）；
          安装目录现为修改版 HDT 1.58.1.0（2026-09-23 替换）、BobsBuddy.dll 1.76.0.0
最后核实：2026-09-25
分析脚本：spikes/hdt-log-analysis/（原始输出在 out/，不入库）
```

文中 `Invoker:N` 指基线 `Hearthstone Deck Tracker/BobsBuddy/BobsBuddyInvoker.cs` 第 N 行；日志位置写作 `<文件名>:<行号>`，文件都在 `%APPDATA%\HearthstoneDeckTracker\Logs\`。日志摘录中的对手英雄名、中文卡名已替换为占位符。

## 1. 日志从哪来

### 1.1 版本对应

- 每个日志文件第 2 行是 `Core.Initialize >> HDT: <版本>`。26 个文件分别来自 1.49.2、1.49.7、1.49.10、1.49.15、1.50.6、1.57.12。**没有任何日志来自 1.58.1**：安装目录的 exe 在 2026-09-23 被替换，而最后一个带模拟的日志（`hdt_log_1790253677.txt`，最后写入 2026-09-24 20:41）第 2 行仍是 1.57.12。
- 上游仓库里 1.57.12 对应提交 `bb3493f2`（2026-09-17，无标签），1.58.1 对应 `ef8ab6e8`（2026-09-22）。`git diff bb3493f2 509bb0b9` 中 `BobsBuddyInvoker.cs` 的日志语句**没有变化**，所以下文引用基线行号即可。
- 1.49.x / 1.50.6 的日志格式与基线有差异，例如计数器行是 `pEternal=N, pUndead=N, pElemental=N, friendly=...`（没有 `pEternalLegion`、`pElementalExtraAtk/Health`，也没有 `pTavernSpell` 行），法术手牌打印为 `Spell` 而不是 `SpellCardEntity`。
- 日志文件第 1–2 行的时间戳可能是 12 小时制（`8:43:59 PM|...`，见 `hdt_log_1770617014.txt:1–2`），之后才变成 24 小时制。时间戳只有时分秒，没有日期。

### 1.2 HDT 日志机制（基线 `Utility/Logging/Log.cs`）

- `DebugLog` 就是 `Log.Info`，调用方方法名作为来源（`Invoker:120–123`），所以日志来源写成 `BobsBuddyInvoker.<方法名>`。
- `Log.Debug` 在发布版且 `LogLevel == 0` 时不输出（`Log.cs:103–106`）。`Invoker:105` 的 `New GameId. Clearing instances...` 因此从未出现。
- **连续完全相同的日志行会被折叠**成一行 `... N duplicate messages`（`Log.cs:108–117`）。上游版本里，两个属性完全相同、相邻的随从会被折成一行加一条折叠提示。本机日志的随从行之间插着修改版的额外行（见 3.2），实测 Input 段落内没有出现折叠（0 次）。
- 文件命名与保留：启动时把上一次的 `hdt_log.txt` 改名为 `hdt_log_<当前 Unix 秒>.txt`（`Log.cs:48`），所以**文件名时间戳是下一次会话的开始时间**，不是本文件的。保留"最近 2 天 + 之前 25 个"，更早的删除（`Log.cs:20–21, 49–58`）。本机现在正好有 26 个旧文件，最早的是 2026-02-08；**下次启动 HDT 就会开始删最旧的日志**。

## 2. 源码中写日志的语句

### 2.1 快照阶段（`SetupInputPlayer`，每个玩家各一组）

| 语句 | 位置 | 输出条件 |
| --- | --- | --- |
| `pEternal=…, pEternalLegion=…, pUndead=…, pElemental=…, pElementalExtraAtk=…, pElementalExtraHealth=…, friendly=…` | `Invoker:818` | 总是 |
| `pPirates=…, pBeasts=…, pDeadLastCombat=…, pBattlecry=…, friendly=…` | `Invoker:846` | 总是 |
| `pBloodGem=+…/+…, friendly=…` | `Invoker:858` | 总是 |
| `pTavernSpell=+…/+… (opponentTransferEnchant=…), friendly=…` | `Invoker:867` | 总是 |
| `pBeastAttack=…, pBeastHealth=…` | `Invoker:771` | 有 Timewarped Goldrinn 玩家附魔时 |
| `pGoldrinnBeastAttack=…, pGoldrinnBeastHealth=…` | `Invoker:791` | Goldrinn 玩家附魔加成 > 0 时 |
| `pBeetleAtk=…, pBeetleHealth=…` | `Invoker:802` | 有 Beetle Army 玩家附魔时 |
| `pWhelpAttack=…, pWhelpHealth=…` | `Invoker:810` | 有 Whelp 玩家附魔时 |
| `pHauntedAtk=…, pHauntedHealth=…` | `Invoker:881` | 有 Haunted Carapace 玩家附魔时 |

实测样例（`hdt_log_1789998252.txt:101–108`）：

```text
15:08:22|Info|BobsBuddyInvoker.SetupInputPlayer >> pEternal=0, pEternalLegion=0, pUndead=0, pElemental=0, pElementalExtraAtk=0, pElementalExtraHealth=0, friendly=True
15:08:22|Info|BobsBuddyInvoker.SetupInputPlayer >> pPirates=0, pBeasts=0, pDeadLastCombat=0, pBattlecry=0, friendly=True
15:08:22|Info|BobsBuddyInvoker.SetupInputPlayer >> pBloodGem=+0/+0, friendly=True
15:08:22|Info|BobsBuddyInvoker.SetupInputPlayer >> pTavernSpell=+0/+0 (opponentTransferEnchant=False), friendly=True
（friendly=False 的同样四行）
```

### 2.2 模拟阶段（`RunSimulation`，`Invoker:1750–1937`）

`Input` 段落**不是** Bob's Buddy 自带的整体打印，而是 HDT 逐项拼出来的；只有随从和手牌项用了 BB 对象的 `ToString()`。

| 内容 | 位置 |
| --- | --- |
| `Running simulations...`、`----- Simulation Input -----` | `Invoker:1750, 1759` |
| `Player: heroPower=<CardId>, used=<bool>, data=<int>`，第二个技能为 `extraHeroPower=` | `Invoker:1762–1766` |
| `Hand: <逐项 ToString，逗号分隔>` | `Invoker:1769` |
| 每个随从一行 `minion.ToString()` | `Invoker:1771–1772` |
| 每个任务一行 `[<任务CardId> (<进度>/<总数>): <奖励CardId>, <NUM_1>, <NUM_2>]` | `Invoker:1774–1775` |
| `---`，然后对手的同样四类 | `Invoker:1777–1792` |
| 双人模式：队友段落，或 `PlayerTeammate: null` / `OpponentTeammate: null` | `Invoker:1794–1857` |
| `---`，然后 `Detected the following player S.` / `opponent S.`（及双人的队友）+ 每个奥秘 `ToString()` | `Invoker:1859–1889` |
| `----- End of Input -----`、`Running simulations with MaxIterations=10000 and ThreadCount=<n>...` | `Invoker:1891–1893` |
| `----- Simulation Output -----` | `Invoker:1928` |
| `Duration=<ms>ms, ExitCondition=<枚举>, Iterations=<simulationCount>` | `Invoker:1929–1931` |
| `WinRate=<%> (Lethal=<theirDeathRate%>), TieRate=<%>, LossRate=<%> (Lethal=<myDeathRate%>)` | `Invoker:1932–1936` |
| `----- End of Output -----` | `Invoker:1937` |
| 异常：`Unsupported interaction: <实体>: <消息>` | `Invoker:1945` |

相关的其他语句：战斗实例键 `<gameId>_<回合>`（`Invoker:110`，由 `StartCombat` 打印，`Invoker:206`）；`Input changed, re-running simulation! (#n)`（`Invoker:987`）；战后校验 `result=<Win|Loss|Tie|Reconnect>, lethalResult=<…>`（`Invoker:2063`）；`Updating entities with attacker=<英雄名>, defender=<英雄名>`（`Invoker:445`）。

实测样例（`hdt_log_1789998252.txt:116–131`，第 1 回合，修改版额外行已标出）：

```text
BobsBuddyInvoker.RunSimulation >> ----- Simulation Input -----
BobsBuddyInvoker.RunSimulation >> Player: heroPower=BG31_HERO_005p, used=False, data=0
BobsBuddyInvoker.RunSimulation >> Hand: [Southsea Busker 3/1]
BobsBuddyInvoker.RunSimulation >> ---
BobsBuddyInvoker.RunSimulation >> Opponent: heroPower=TB_BaconShop_HP_075, used=True, data=0
BobsBuddyInvoker.RunSimulation >> Hand: 
BobsBuddyInvoker.RunSimulation >> 【团子专属】模拟对战，对手：<英雄名>                         ← 修改版
BobsBuddyInvoker.RunSimulation >> [Suspicious Prisonguard 3/3, ScriptDataNum1=3, ScriptDataNum2=3, ScriptDataNum3=1]
BobsBuddyInvoker.RunSimulation >> 【团子专属】模拟对战，对方随从1：<中文卡名>（BG36_345）     ← 修改版
BobsBuddyInvoker.RunSimulation >> ---
BobsBuddyInvoker.RunSimulation >> ----- End of Input -----
BobsBuddyInvoker.RunSimulation >> Running simulations with MaxIterations=10000 and ThreadCount=6...
BobsBuddyInvoker.RunSimulation >> ----- Simulation Output -----
BobsBuddyInvoker.RunSimulation >> Duration=152.1738ms, ExitCondition=CompletedSimulations, Iterations=19998
BobsBuddyInvoker.RunSimulation >> WinRate=0% (Lethal=0%), TieRate=0%, LossRate=100% (Lethal=0%)
BobsBuddyInvoker.RunSimulation >> ----- End of Output -----
```

随从行在全部日志里出现过的形式（`[名字 攻/血, 标记..., 键=值..., Enchantments=[...]]`）：

- 标记：`G`（金色）、`Taunt`、`Div`、`Reborn`、`Windfury`、`Venomous`、`Poison`、`Stealth`、`Cleave`。
- 键值：`ScriptDataNum1..4`（为 0 时不打印）、`Deathrattles=[GenericDeathrattles.Crab, AutoAssembler.Deathrattle, ...]`、`AttachedModularEntity=...`、`Enchantments=[<名字>(<a>, <b>), ...]`（出现过 27 种，如 `BlueVolumizerEnchantment`、`Admiration`、`DefensiveSacrifice`）。
- 名字是**英文卡名**，没有 CardId。
- 手牌项：随从同上格式；法术打印为 `SpellCardEntity`（1.49.x 为 `Spell`）；另有 `LockboxCardEntity`、`BloodGem`、`BG20_GEM`。
- 奥秘打印为名字，如 `Redemption`、`VenomStrikeTrap`、`PackTactics`（`hdt_log_1789998252.txt:532–533`）。

## 3. 本机日志统计（26 个文件，全部）

| 项目 | 数值 |
| --- | --- |
| 快照尝试（`Snapshotting board state...`） | 944 |
| 不同的战斗实例键（`<gameId>_<回合>`） | 921 |
| `Simulation Input` 段落 | 968 = 921 次首跑 + 42 次 `TryRerun` 重跑 + 5 次修改版"重新模拟"（`DoSimulation`） |
| 有完整 `Output` 的段落 | 947（21 个段落因并发重跑，`Output` 与 `Input` 无法一一配对） |
| `ExitCondition` | `CompletedSimulations` 516、`Time` 431 |
| `Iterations` | 完成时恒为 19,998（`MaxIterations` 打印为 10000、`ThreadCount=6`）；超时时中位 14,693，P10 6,265 |
| `Duration` | P50 2,348 ms、P90 3,004 ms、最大 3,236 ms |
| 校验结果（`result=`） | Win 373、Loss 349、Tie 185、Reconnect 4 |
| 错误 | `ArgumentNullException`（在 `StartCombat` 中）28 次、`ErrorState=UnknownCards` 16 次、`Board has cards with changed text` 8 次 |
| 双人模式段落 | 0（没有任何 `Teammate` 行） |

- **重跑也会打印完整的 Input 段落**（`hdt_log_1789998252.txt:542–545`）。42 次 `TryRerun` 中，26 次重跑的 Input 与前一次**逐行相同**，8 次对手随从行变化，1 次己方随从行变化。逐行相同说明触发重跑的改动发生在日志不打印的字段上（如奥秘以外的揭示信息、附魔计数器）。
- `TryRerun` 可能在 `StartCombat` 的状态等待期间触发，这时重跑段落会出现在首跑段落**之前**（`hdt_log_1770617014.txt` 1189–1191 行附近）；两次模拟可能并发，`Output` 段落顺序与 `Input` 不一致。
- 同一份日志输入模拟两次（13 对有完整输出），胜/平/负的最大差值为 0–1.0 个百分点。
- 把每场战斗最后一次模拟和 HDT 校验结果对照：实际赢的战斗平均预测胜率 87.8%，实际输的平均预测负率 88.4%，实际平的平均预测平率 42.2%；三分类 Brier 分数 0.276（907 场）。

## 4. 逐项核对：日志能否重建 `Input`

字段清单来自 [`bobsbuddy-simulator-input.md`](bobsbuddy-simulator-input.md)。"有" = 日志能直接读出；"部分" = 只有部分信息或需要推导；"没有" = 日志里不打印。

### 4.1 大厅 / 对局级

| 字段 | 日志 | 说明 |
| --- | --- | --- |
| `availableRaces` | 没有 | `Invoker:906` 赋值，不打印 |
| `DamageCap` | 没有 | `Invoker:907–908` |
| `Anomaly` | 没有 | `Invoker:956–959` |
| 回合 `SetTurn` | 部分 | 不在 Input 段落里，但实例键 `<gameId>_<回合>` 的后缀就是 `SetTurn` 的参数（`Invoker:110, 209, 225`） |
| `isDuos` / 队友 | 有 | 双人模式会打印队友段落；本机没有双人样本，未实测 |

### 4.2 玩家级

| 字段 | 日志 | 说明 |
| --- | --- | --- |
| `Health`（含护甲）、`DamageTaken`、`Tier` | 没有 | `Invoker:518–520`。修改版在战斗结束时额外打印了**防守方**的血量+护甲（见 5.2），但只有一方、而且是战斗后 |
| 英雄技能 `CardId`、是否已用 | 有 | 最多 2 个 |
| 英雄技能 `Data` | 部分 | 只打印一个 `data=` 整数；`TAG_SCRIPT_DATA_NUM_1/2/3` 三个值不能分开 |
| 英雄技能附着随从（Teron、Floop、Tavish） | 没有 | `Invoker:522–597` |
| 任务（进度、总数、任务/奖励 CardId、奖励 NUM_1/2） | 有 | 78 行；只完成奖励时任务 CardId 为空 |
| 饰品 | 没有 | `Invoker:599–638` 中的 `GetTrinketFromEntity` 结果不打印 |
| 目标（Objective）、Deity Sigil 神祇 | 没有 | 同上 |
| 奥秘 | 部分 | 打印名字，无 DbfId；对手未知奥秘是否打印未能确认 |
| 己方手牌 | 部分 | 随从完整（同随从格式，但看不到 `CanSummon`）；法术只有类型 `SpellCardEntity`；Lockbox 看不到 `NUM_1` |
| 对手手牌 | 部分 | 同上；未知手牌项在日志中无法区分（空行 `Hand: ` 出现 394 次） |
| 对手是否 Kel'Thuzad | 没有（可推导） | 可从对手英雄技能 CardId 推导 |

### 4.3 玩家级计数器

| 字段 | 日志 |
| --- | --- |
| `EternalKnightCounter`、`UndeadAttackBonus`、`ElementalPlayCounter`、`PiratesSummonCounter`、`BeastsSummonCounter`、`FriendlyMinionsDeadLastCombatCounter`、`BattlecryCounter`、`BloodGemAtkBuff/HealthBuff` | 有（所有版本） |
| `EternalLegionCounter`、`ElementalsGiveExtraAttack/Health`、`TavernSpellAtkBuff/HealthBuff` | 有（1.57.12；1.49.x/1.50.6 的格式里没有） |
| `BeastAttackBonus/HealthBonus`、`BeetlesAtkBuff/HealthBuff`、`WhelpAttackBonus/HealthBonus`、`HauntedAtkBuff/HealthBuff` | 部分（只在对应附魔存在时打印；不打印即为 0） |
| `UndeadHealthBonus`（`Invoker:763`）、`SanlaynScribeCounter`（731–733）、`AncestralAutomatonCounter`（794–796）、`MagnetizeCounter`（823）、`ResourcesSpentThisGame`（825–834）、`TastyLobsterCounter`（838）、`GoldenMinionsPlayedCounter`（840）、`TavernSpellCounter`（869）、`DeathrattleCounter`（871）、`VolumizerAtkBuff/HealthBuff`（873–874） | 没有 |

### 4.4 随从级

| 字段 | 日志 | 说明 |
| --- | --- | --- |
| 卡牌 | 部分 | 上游格式只有英文名。本机修改版在每个随从后多打一行 CardId（9,612 个随从全部配上），所以**本机日志**可以直接拿到 CardId |
| 顺序 | 有 | 按打印顺序 |
| 攻 / 血 | 部分 | 只打印一对 `攻/血`，`baseHealth`（扣伤害后）与 `maxHealth` 分不开 |
| 关键词 | 有 | 见 2.2；`MEGA_WINDFURY` 从未出现，打印形式未知 |
| `golden` | 有 | `G` |
| `tier`、`PrimaryRace` | 没有（可推导） | 可由 CardId 查卡牌数据，但被改过种族的随从会错 |
| `ScriptDataNum1..4` | 有 | 值为 0 时不打印 |
| 附着附魔映射（额外亡语、集结、Wingmen 等） | 部分 | 只看到 `Deathrattles=[...]`、`AttachedModularEntity=`、`Enchantments=[名字(a, b)]` 三种形式；这些形式覆盖了哪些映射项未核对 |
| Eclipsion Illidari 的 `SCORE_VALUE_2` | 未能确认 | 可能落在 `ScriptDataNum` 或不打印 |

### 4.5 战斗中揭示的更新

重跑会重新打印 Input，所以对手手牌、对手随从等**打印字段**的变化能从后一个段落看到；更新了**不打印字段**（奥秘之外的附魔、计数器、Tavish 装填、Malorne 推算资源等）时，日志里只多出一行 `Input changed, re-running simulation!` 和一个内容相同的段落。

### 4.6 Output 能否作对照基准（P2-T5）

- 日志的 `Output` 只有：胜率、平率、负率、双方致死率、`simulationCount`、`myExitCondition`、耗时。**没有 `damageResults` 伤害分布。**
- 45% 的模拟因时间预算结束（`ExitCondition=Time`），次数少于满额。
- 同一日志输入两次模拟的差值 ≤ 1 个百分点，可以作为比较容差的参考下限。
- 致死率依赖英雄血量和酒馆等级，而日志不打印这两项。

## 5. 修改版 HDT（Q-010）

### 5.1 身份

- 安装目录 exe 的用户字符串里有窗口标题 `Hearthstone Deck Tracker-团子版`、更新提示 `HDT团子版更新提醒（本插件完全免费）`（元数据扫描，`MainWindow::.ctor`、`Updater+<ShowNewUpdateMessage>`）。这是第三方中文修改版，不是 HearthSim 官方构建。
- 修改版在所有日志版本（1.49.2 起）中都存在：26 个日志中带模拟的都有 `【团子专属】` 行。
- 程序集元数据：`HearthstoneDeckTracker, Version=1.58.1.0`，4,263 个类型。

### 5.2 日志中多出来的行（上游源码中没有）

所有额外行都以 `【团子专属】` 开头。按来源方法统计（全部 26 个日志）：

| 来源 | 模板（已匿名化） | 次数 |
| --- | --- | --- |
| `BobsBuddyInvoker.RunSimulation` | `模拟对战，我方随从N：<中文卡名>（<CardId>）`，紧跟在每个己方随从行之后 | 4,883 |
| `BobsBuddyInvoker.RunSimulation` | `模拟对战，对方随从N：<中文卡名>（<CardId>）`，紧跟在每个对方随从行之后 | 4,729 |
| `BobsBuddyInvoker.RunSimulation` | `模拟对战，对手：<英雄名>`，在对手 `Hand:` 行之后 | 968 |
| `BobsBuddyInvoker.UpdateAttackingEntities` | `设置_totalDefenderHealth：N，_attackingHeroAttack：N` | 746 |
| `BobsBuddyInvoker.DoSimulation` | `重新模拟对战`（之后跟一个完整 Input 段落） | 5 |
| `GameEventHandler.HandleTurnsInPlayChange` | `回合变化：第N回合，player（Player/Opponent）,_lastTurnStart（N）` | 3,978 |
| `GameEventHandler.HandleGameEnd` | `游戏结束，是否重连：<bool>` | 120 |
| `LoadingScreenHandler.Handle` | `ReconnectCount：N`、`游戏开始，是否重连：<bool>`、`重连成功，跳过重置状态` | 552 |
| `HearthstoneHandler.Handle` | `RemoteAddr：<IP>，RemotePort：N` | 219 |
| `MyPanel.GetTcpRow` / `DoReconnect` / `DisconnectedTimeout` | `TcpRow：<IP>-<IP>`、`开始拔线：…`、`等待拔线N秒`、`IsReconnect：True`、`NeedChangeToPlayer（True）`、`拔线超时。` | 653 |

### 5.3 源码有、日志没出现的语句

对照每个日志所属版本的上游源码：没出现的都是条件分支（错误、双人、`Log.Debug`、超过 10 次重跑、对应附魔不存在等），例如 `Invoker:105`（Debug 级）、`Invoker:216/267`（双人）、`Invoker:321`（模拟次数不足）、`Invoker:791/881`（Goldrinn / Haunted 计数器）、`Invoker:1945`（不支持的交互）、`Invoker:1799–1855`（队友段落）。没有发现"应该每次都打印却缺失"的语句。

### 5.4 程序集元数据对比（`MetadataProbe` + `compare_types.py`，对照上游 `ef8ab6e8`）

只读元数据（类型名、方法名、用户字符串），没有反编译方法体。

- `BobsBuddyInvoker` 有 72 个方法，比上游源码多 `DoSimulation`、`RecordResult`（及一个 lambda）；上游的方法全部存在。
- 上游源码里找不到声明的类型：`Controls.Overlay.MyPanel`（一键拔线面板）、`Iphlpapi` 及其 `MIB_TCPROW` 等结构（Windows TCP 表操作）、`Reconnector`、`LogReader.Handlers.HearthstoneHandler`、`Windows.DonateWindow`、`Utility.Updating.VersionInfo`。其余几个差异项是委托、编译器生成的类型或资源类，不是修改。
- 含中文用户字符串的方法（节选）：`BobsBuddyInvoker+<RunSimulation>`（5.2 的日志行，以及 `第{0}回合，{1} VS {2}`、`我方随从：{0}` 等对战记录文本）、`<RunAndDisplaySimulationAsync>`（`模拟结果（模拟{5}次）：…`）、`RecordResult`（`实际结果：{0}，{1}` 和一批调侃文案）、`<ValidateSimulationResultAsync>`（`第{0}回合，我直接拔线~`）、`BattlegroundsBoardState::SnapshotCurrentBoard`（`记录阵容：跳过记录阵容，状态：{0}`）、`MainWindowMenuViewModel`（`启用144帧` / `启用240帧`，改炉石客户端帧率配置）、`MyPanel::ShowBan`（`获取禁用种族中`）、`Config::.cctor`（目录名 `对战记录`、日期格式 `yyyy年MM月dd日`）。
- 修改版写入每日对战记录：`C:\Program Files\HDT\对战记录\<yyyy年MM月dd日>.txt`，55 个文件，2025-10-07 至 2026-09-21。每场战斗记录双方英雄中文名、双方随从中文名与攻血、模拟结果、实际结果（或 `我拔线了，插件并不知道结果~`），每局结束记录名次和分数变化。内容不含 BattleTag。55 个文件中共有 372 行以 `我拔线了` 开头，即 372 场战斗因拔线没有记录实际结果（2026-09-25 用 `Select-String -Pattern "^我拔线了"` 统计）。
- 上游的插件黑名单仍在：`PluginManager::.ctor` 里有 `Reconnector`、`HDT-Reconnector`、`iphlpapi` 等字符串，`LoadPlugins` 里有 `Refusing to load plugin: `（上游对应 `PluginManager.cs:179–210`，注释写明 "Blizzard has kindly asked us to stop supporting reconnector plugins"）。修改版把拔线功能直接编进了主程序。

### 5.5 结论（能判断的范围）

| 方面 | 判断 |
| --- | --- |
| 日志格式 | **改了。** 在 `RunSimulation` 的 Input 段落里插入了额外行（每个随从后一行 CardId、对手英雄名），在战斗、回合、重连、拔线处加了日志。上游原有的行格式没有变化，按版本逐条匹配上游模板全部命中 |
| 模拟输入构造（`SnapshotBoardState` / `SetupInputPlayer` / `GetMinionFromEntity`） | **没有发现修改的证据，但不能排除。** 这些方法里没有修改版字符串，计数器日志格式与上游一致；没有上游 1.58.1 二进制可做方法体对比 |
| 模拟调用 | 多了 `DoSimulation`（手动"重新模拟"，5 次）；`MaxIterations=10000`、`ThreadCount` 与上游一致 |
| 插件接口 | **没有发现修改的证据。** 插件相关类型都能在上游源码里找到声明，黑名单逻辑还在；未做成员级签名对比 |
| 其他 | 拔线（操作本机 TCP 连接断开游戏连接）、帧率修改、对战记录、禁用种族显示、自带更新器与捐赠窗口 |

[推断] 修改版的 `RecordResult`、对战记录与上游的战后校验共用 `BobsBuddyInvoker` 的状态；它对实时插件的影响需要在 P2 原型中实测。
