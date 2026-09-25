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

- `BobsBuddyInvoker`（`internal class`）与 `BobsBuddyUtils`（`internal static` 方法）都不对外公开，插件**不能直接调用** HDT 的"实体 → 模拟器输入"转换逻辑。
- `BobsBuddyInvoker.SnapshotBoardState` 里有注释提到"第三方插件在战斗中保存/恢复 input"（`BobsBuddyInvoker.cs:914–916`）。**[推断]** 已有插件通过反射访问 `_input`，这是一条可参考的技术路径（登记为 Q-002）。

## 许可证

- 仓库根目录下没有找到 LICENSE 文件；`licenses/` 目录里只有第三方组件的许可证。HDT 自身及 `BobsBuddy.dll` 的许可条款还没确认（Q-003）。
