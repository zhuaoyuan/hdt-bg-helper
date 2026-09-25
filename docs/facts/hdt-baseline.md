# HDT 基线事实

> 这份文档回答：我们依赖的 HDT 是哪个版本、怎么构建、插件能拿到什么、酒馆战棋战斗在代码里什么时候开始。

```text
基线：HDT v1.58.3 / 509bb0b9660759c049e8ed3f59043e9e4f9fe1e5（2026-09-24）
本地路径：C:\projects\github\Hearthstone-Deck-Tracker
最后核实：2026-09-25
```

以下路径均相对于 HDT 仓库根目录。

## 构建与目标平台

- 主项目 `Hearthstone Deck Tracker/Hearthstone Deck Tracker.csproj`：`TargetFramework` 为 `net472`，`PlatformTarget` 为 `x64`，`LangVersion` 为 `10`（csproj 第 7、22、33 行）。
- 闭源依赖不在仓库里，由 `Bootstrap/Bootstrap.csproj` 在构建时下载到 `lib/`（第 19–22、40、55–57 行）：
  - `HearthDb`：`https://libs.hearthsim.net/hdt/HearthDb.zip`
  - `HearthMirror`：`https://libs.hearthsim.net/hdt/HearthMirror.x64.zip`
  - `HSReplay`：`https://libs.hearthsim.net/hdt/HSReplay.dll`
  - `BobsBuddy`：`https://libs.hearthsim.net/hdt/BobsBuddy.zip`
- 入口脚本 `bootstrap.ps1`：`nuget restore`，再 `msbuild` 构建 Bootstrap 项目和主项目。
- 克隆后的 `lib/` 里只有 `De.TorstenMandelkow.MetroChart.dll`，上述 DLL 需要跑 bootstrap 或从已安装的 HDT 目录获取。

## 插件接口

`Hearthstone Deck Tracker/Plugins/IPlugin.cs`：插件实现 `IPlugin`，成员如下。

| 成员 | 说明 |
| --- | --- |
| `Name` / `Description` / `ButtonText` / `Author` / `Version` | 元数据 |
| `MenuItem` | 添加到 "Plugins" 主菜单的 WPF `MenuItem`，可为 `null` |
| `OnLoad()` / `OnUnload()` | 插件被启用 / 停用时调用 |
| `OnButtonPress()` | 在"选项 > 追踪器 > 插件"中点击按钮时调用 |
| `OnUpdate()` | 约每 100ms 调用一次 |

## 插件加载

`Hearthstone Deck Tracker/Plugins/PluginManager.cs`、`PluginWrapper.cs`：

- 安装位置是 `%APPDATA%\HearthstoneDeckTracker\Plugins`（`PluginManager.cs:25`）。启动时 HDT 把它同步到自己工作目录下的 `Plugins`：新增或更新的文件复制过去，源目录里没有的文件和子目录删掉（`PluginManager.cs:79–153`）。直接放进安装目录 `Plugins` 的插件会被删除（`READ THIS.txt` 提示，`PluginManager.cs:60–71`）。
- 加载方式：对每个 `.dll` 调用 `Assembly.LoadFrom`，把其中非抽象、`public`、实现了 `IPlugin` 的类型用 `Activator.CreateInstance` 实例化（`PluginManager.cs:213–250`）。插件和 HDT 在同一个进程、同一个 AppDomain 里。
- 拒绝加载：名称为 Reconnector 类的插件（`PluginManager.cs:179–199`），以及任何方法 `DllImport` 了 `iphlpapi` / `lovepapi` 的程序集（`PluginManager.cs:208–223`）。
- 启用状态保存在 `%APPDATA%\HearthstoneDeckTracker\plugins.xml`（`PluginManager.cs:161, 280–317`）。
- `OnUpdate()` 由一个约 100 ms 的循环调用（`PluginManager.cs:266–276`）。抛出的异常累计超过 `MaxExceptions = 100` 次时插件被停用（`PluginWrapper.cs:121–129`）。单次 `OnUpdate` 超过 2000 ms 只记警告，停用的代码被注释掉了（`PluginWrapper.cs:131–137`）。

## 插件构建

- 官方 wiki "Creating Plugins"：建一个面向 .NET Framework 4.7.2 的类库，引用 `Hearthstone Deck Tracker.exe`，实现 `Plugins.IPlugin`；HDT 已带的依赖不要随插件分发。
- 实测（2026-09-25，`spikes/hdt-plugin-skeleton`）：不装 Visual Studio，用 .NET SDK 9.0.200 的 SDK 风格项目就能编译 net472 x64 插件。以 `Private=false` 引用安装目录中的 `HearthstoneDeckTracker.exe`、`BobsBuddy.dll`、`HearthDb.dll`，再加上 `PresentationCore`、`PresentationFramework`、`WindowsBase`、`System.Xaml`、`netstandard` 即可。产物只有插件自身的 DLL。
- 社区插件 HDT_BGrank（MIT）的做法是把 `HearthstoneDeckTracker.exe`、`HearthMirror.dll` 等二进制文件直接提交到仓库的 `Reference/` 目录（GitHub `IBM5100o/HDT_BGrank`，2026-09-25 查看）。
- HDT 的 GitHub Releases 最新一版是 v1.55.6（2026-08-13），附件是 `Hearthstone.Deck.Tracker-v1.55.6.zip`；更新的版本（源码 1.58.3）没有发布在 GitHub 上。CI 如果需要 HDT 二进制文件，只能从旧 Release、自行构建 HDT 或其他渠道获取。

## 公开游戏事件

`Hearthstone Deck Tracker/API/GameEvents.cs` 提供静态 `ActionList` 事件，包括：

- 对局：`OnGameStart`、`OnGameEnd`、`OnGameWon`、`OnGameLost`、`OnGameTied`、`OnInMenu`、`OnTurnStart(ActivePlayer)`、`OnModeChanged(Mode)`
- 玩家/对手：抽牌、打出、弃牌、英雄技能、随从攻击（`OnPlayerMinionAttack` / `OnOpponentMinionAttack`，参数 `AttackInfo`）等
- `OnEntityWillTakeDamage(PredamageInfo)`

**没有**专门的"酒馆战棋战斗开始 / 战斗结束"公开事件。

## 酒馆战棋战斗的开始时机

- 单人模式：`Hearthstone Deck Tracker/LogReader/Handlers/TagChangeActions.cs` 中 `OnBattlegroundsSetupChange`（第 199 行起），某个标签由 1 变为 0 时置 `game.IsBattlegroundsCombatPhase = true`，然后调用 `BobsBuddyInvoker.GetInstance(gameId, turn).StartCombat()`（第 220–221 行）。
  - 会用 `GameEntity` 的 `TURN` 过滤掉假战斗：战斗应出现在购物阶段之后的 `TURN` 上（第 206–218 行）。
- 双人模式：`OnBattlegroundsCombatSetupChange`（第 226 行起），1→0 时先 `game.SnapshotBattlegroundsBoardState()`，再 `StartCombat()`（第 237–243 行）。
- 此外，`TagChangeActions.cs` 与 `PowerHandler.cs` 在战斗过程中多处调用 `BobsBuddyInvoker` 的更新方法（见 [`bobsbuddy-simulator-input.md`](bobsbuddy-simulator-input.md) 的"战斗中揭示"部分）。

## 可见性限制

- `BobsBuddyInvoker`（`internal class`）与 `BobsBuddyUtils`（`internal static` 方法）都不对外公开，插件**不能直接调用** HDT 的"实体 → 模拟器输入"转换逻辑。但 `BobsBuddy.dll` 本身的类型都是公开的，插件可以自己构造输入并调用模拟（见 [`bobsbuddy-public-api.md`](bobsbuddy-public-api.md)）。
- `BobsBuddyInvoker.SnapshotBoardState` 里有注释提到"第三方插件在战斗中保存/恢复 input"（`BobsBuddyInvoker.cs:914–916`）。**[推断]** 已有插件通过反射访问 `_input`，这是一条可参考的技术路径（登记为 Q-002）。

## 许可证

- HDT 和 `BobsBuddy.dll` 都是保留全部权利的专有软件，没有开源许可证。条款原文和官方表态见 [`licensing.md`](licensing.md)。
