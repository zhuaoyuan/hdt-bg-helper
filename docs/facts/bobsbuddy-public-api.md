# Bob's Buddy 公开 API 与独立调用

> 这份文档回答：`BobsBuddy.dll` 里哪些类型是公开的、能否在 HDT 之外自己构造输入并调用模拟、不同版本之间 API 稳定性如何（Q-001）。

```text
实测环境：BobsBuddy.dll 1.76.0.0（C:\Program Files\HDT，随修改版 HDT 1.58.1）
          BobsBuddy.dll 1.78.8.0（https://libs.hearthsim.net/hdt/BobsBuddy.zip，2026-09-25 下载）
          HearthDb.dll 36.6.0（C:\Program Files\HDT）
工具：spikes/bobsbuddy-api/（ApiDump 导出公开签名，MinimalSim 做最小调用）
最后核实：2026-09-25
```

只导出了公开签名（反射元数据），没有反编译方法体。

## 程序集概况

| 项 | 1.76.0 | 1.78.8 |
| --- | --- | --- |
| 目标框架 | .NET Standard 2.0 | 同左 |
| 依赖 | `netstandard 2.0`、`HearthDb 36.6.0.0`、`BobsBuddy.Common` 同版本 | 同左 |
| 强名称 | 无（`PublicKeyToken=null`） | 同左 |
| 类型数（总 / 公开） | 2145 / 1216 | 2134 / 1196 |
| 版权属性 | `Copyright © HearthSim 2023`，`AssemblyCompany = HearthSim` | 同左 |
| 源码版本 | `1.76.0+ef27b90b…` | — |

- `InternalsVisibleTo` 只给了 `BobsBuddy.Test` 和 `BobsBuddy.Benchmark`。
- `BobsBuddy.Common.dll` 只有两个公开类型：`CardData`（`Id`、`Text`）和 `KnownBaconCards`（`Cards` 列表）。
- 注意：官方 zip 当前是 1.78.8，比本机修改版 HDT 自带的 1.76.0 新。
- 2026-09-25 所有者换用官方 HDT 1.58.3.8362，它自带的是 BobsBuddy.dll **1.78.1.0**（`facts/local-environment.md`），也比 zip 里的 1.78.8 旧。所以 zip 的最新版本不等于用户实际运行的版本。本文还没有在 1.78.1 上跑过 ApiDump 和 MinimalSim。

## 核心类型（均为 `public`，1.76.0）

`BobsBuddy.Simulation` 命名空间：

| 类型 | 构造 | 要点 |
| --- | --- | --- |
| `Input` | `Input()` | 字段 `Anomaly`、`isDuos`、`DamageCap`、`turn`、`availableRaces`；属性 `Player`、`Opponent`、`PlayerTeammate`、`OpponentTeammate`（可读写）；方法 `SetTurn`、`SetHealths`、`SetTiers`、`AddSecretFromDbfId` 等 |
| `Player` | `Player(Input)` | `Side`（`List<Minion>`）、`HeroPowers`、`Quests`、`Objectives`、`Trinkets`、`Secrets`、`Hand`，以及 HDT 赋值的全部计数器（见 `bobsbuddy-simulator-input.md` 3.6–3.7 节），另有 `BackToBackAtk/Health/Counter`、`DeepBluesCounter`、`AnySpellCounter` 等；`AddHeroPower(...)`、`SetSecrets(...)` |
| `SimulationRunner` | `SimulationRunner()` | 唯一公开方法 `Task<Output> SimulateMultiThreaded(Input input, int maxIterations, int threadCount, int maxDuration)` |
| `Simulator` | `Simulator()` | 公开只读字段 `MinionFactory`、`TrinketFactory`、`ObjectiveFactory`、`AnomalyFactory`、`EnchantmentFactory`、`questFactory`、`questRewardFactory`；另有单线程入口 `Output SimulateForInput(Input, int iterations, int maxDuration)` |
| `Output` | `Output(IEnumerable<int>, int, int)` | 字段 `winRate`、`tieRate`、`lossRate`、`myDeathRate`、`theirDeathRate`、`damageResults`、`avDamage`、`medianDamage`、`simulationCount`、`myExitCondition` 等 |

其他：

- `BobsBuddy.Factory.MinionFactory`：`CreateFromCardId(string cardId, bool controlledByPlayer)`、`CreateFromCard(Card, bool)`、`HasImplementationFor(string)`，静态列表 `cardIDsWithCleave`、`cardIdsWithMegaWindfury`。
- `BobsBuddy.Minion`：`Minion(string cardId, bool controlledByPlayer, Simulator)`；HDT 用到的属性（`baseAttack`、`maxAttack`、`baseHealth`、`maxHealth`、`taunt`、`div`、`poisonous`、`venomous`、`windfury`、`megaWindfury`、`stealth`、`golden`、`tier`、`reborn`、`ScriptDataNum1..4`、`game_id`、`PrimaryRace` 等）都有公开 setter。
- 手牌实体：`CardEntity`、`MinionCardEntity`、`SpellCardEntity`、`LockboxCardEntity`、`RandomMinionCardEntity`、`UnknownCardEntity`，均为公开类。
- `BobsBuddy.Utils.SupportedCards.VerifyCardIsSupported(HearthDb.Card)`，返回 `SupportedCards.Result`（3 个值）。
- `BobsBuddy.UnsupportedInteractionException(string, Entity)`。
- 1,000 多个具体随从 / 附魔 / 饰品类（如 `BobsBuddy.Minions.Aberration.AbyssalEnvoy`）都是公开类，并带有公开静态字段 `CardId`、`Text`、`GoldenText`。

## 独立调用实测

`spikes/bobsbuddy-api/MinimalSim`（net472、x64 控制台程序），照 HDT 的方式构造输入：`new Simulator()`、`new Input()`、`MinionFactory.CreateFromCardId`，设置属性后加入 `Player.Side`，再调用 `new SimulationRunner().SimulateMultiThreaded(input, 10000, 6, 1500)`。机器 12 个逻辑核心，用 6 个线程。

| 场面（全部用 `CFM_315t` 虎斑猫，属性手动覆盖） | 1.76.0 | 1.78.8 |
| --- | --- | --- |
| A：10/10 对 1/1 | 胜 100%，9996 次，152 ms | 胜 100%，9996 次，154 ms |
| B：3/3 对 3/3 | 平 100%，9996 次，33 ms | 平 100%，9996 次，25 ms |
| C：7 对 7 不对称白板 | 胜 7.0% / 平 14.1% / 负 78.9%，9996 次，147 ms | 胜 7.0% / 平 14.3% / 负 78.7%，9996 次，157 ms |

结论：

- **可以在 HDT 进程之外自行构造 `Input` 并调用模拟**，不需要 HDT 的任何代码，也不需要反射。
- 三个场面都以 `CompletedSimulations` 结束，结果符合预期。
- `SupportedCards.VerifyCardIsSupported` 对 `CFM_315t` 返回 `UnknownCard`，但照样能模拟。HDT 源码注释说这个校验只对 `TECH_LEVEL > 0` 的卡有效（`BobsBuddyInvoker.cs:480`）。
- **[推断]** 白板场面的耗时不代表真实对局。真实场面有大量触发效果，HDT 给的时间预算是 1.5–5 秒（`bobsbuddy-simulator-input.md` 第 1 节）。Q-009 需要用真实场面测。

## 版本间差异（1.76.0 → 1.78.8）

- 核心类型（`Input`、`Player`、`Output`、`SimulationRunner`、`Simulator`、`Minion`、各工厂）只有一处签名变化：`Player.MagnetizeCounter` 从 `int?` 改为 `int`。
- 类型层面删除 24 个、新增 4 个，全部是具体卡牌实现：
  - 删除了 `BobsBuddy.Minions.Aberration.*` 下 13 个随从，以及 `DarkParadox`、`AutoReveille`、`ResourcefulRobot`、`SewerEscapee`、`GreedyConniver`、`VictoriousGeomant` 等随从和若干饰品、附魔；
  - 新增 `AnnoyOModuleEnchantment`、`TrousersOff`、`MaskOfAncientOnes`、接口 `IDeity`。
- 同一份 MinimalSim 源码对两个版本都能编译，运行结果一致。
- **[推断]** Bob's Buddy 会随补丁删除下架卡牌的实现，新版 DLL 可能无法正确模拟旧补丁的场面（登记为 Q-011）。
- **[推断]** 程序集没有强名称，插件在 HDT 进程内会绑定到 HDT 已加载的那份 `BobsBuddy.dll`，不管编译时引用的是哪个版本。如果代码用到了签名已变化的成员（如 `MagnetizeCounter`），运行时会抛 `MissingMethodException` 之类的异常。待插件原型实测。

## 卡牌数据依赖

- Bob's Buddy 通过 `HearthDb.Cards` 读取卡牌数据（`BobsBuddy.HearthdbUtil.CardFromID` 等公开方法；`SupportedCards.VerifyCardIsSupported` 的参数是 `HearthDb.Card`）。
- HDT 启动时从 `hearthstonejson` 下载最新的 `CardDefs.*.xml`，缓存到 `%APPDATA%\HearthstoneDeckTracker\CardDefs`，再调用 `Cards.LoadBaseData` 替换 HearthDb 自带的数据（`Hearthstone Deck Tracker/Utility/Assets/CardDefsManager.cs:24–36, 63, 87`，基线 `509bb0b9`）。
- MinimalSim 没有加载下载的 CardDefs，用的是 `HearthDb.dll` 自带的数据。在 HDT 之外离线模拟时，需要自己加载对应版本的 CardDefs（Q-011）。
