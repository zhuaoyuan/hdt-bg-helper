# HDT「上次对手阵容」叠加层与离线渲染可行性

> 这份文档回答：HDT 悬停排行榜头像时展示的「上次对战阵容图」如何实现？我们诊断记录里的原始数据，是否足以复现等价画面？还缺哪些外部资源？

```text
基线：HDT v1.58.3 / 509bb0b9
实测样本：BgHelperDiag 20261005_104908_ed11e0（插件 0.2.0，records.jsonl.gz）
最后核实：2026-10-05
```

## 1. HDT 功能链路（已核实）

悬停排行榜对手头像 → 显示该对手**上一场被我方打到时**的场面，控件为 `BattlegroundsOpponentInfo`。

| 步骤 | 位置 | 行为 |
| --- | --- | --- |
| 快照触发 | `TagChangeActions.cs:231–241` | 标签 `3533` 1→0 时调用 `game.SnapshotBattlegroundsBoardState()`（双人模式同分支；单人也走这条）。**不是** Bob's Buddy 的 `SnapshotBoardState` |
| 快照内容 | `BattlegroundsBoardState.cs:19–34` | 取对手控制、`ZONE=PLAY` 的**随从**实体 `Clone()`，按对手英雄 `PLAYER_ID` 存入 `LastKnownBoardState`，附带当时 `GetTurnNumber()` |
| 悬停读取 | `OverlayWindow.Update.cs:442–474` | `_leaderboardHoveredEntityId` → `GetBattlegroundsBoardStateFor(heroEntityId)` → `BgsOpponentInfo.Update`；悬停己方/队友时隐藏 |
| 单随从控件 | `BattlegroundsMinion.xaml.cs:18–33` + `BattlegroundsMinion.xaml` | 从 `Entity` 读：`POISONOUS`/`VENOMOUS`/`DIVINE_SHIELD`/`DEATHRATTLE`/`REBORN`/`PREMIUM`/`TAUNT`、`Attack`/`Health`、`Card`；肖像用 `CardAssetType.Portrait` |
| 肖像下载 | `AssetDownloaders.cs:27–34` | `https://art.hearthstonejson.com/v1/256x/{card.Id}.jpg`，缓存 `%APPDATA%\HearthstoneDeckTracker\Images\CardPortraits` |
| 边框/关键词贴图 | `App.xaml:47–59` | `Resources/Minion/*.png`（嘲讽、圣盾、亡语、复生、剧毒、边框、攻血底座等），作为 WPF `StaticResource` 打进 HDT |

同面板还有神祇（`GetBattlegroundsDeityFor`）与三连/升级回合（`GetBattlegroundsHeroTriplesByTier` / `GetBattlegroundsHeroLatestTavernUpTurn`），**不属于**「阵容条」本身。

### 关于「略去状态信息」

**已核实：** 当前基线的上次阵容条**会**绘制关键词角标与攻血数字（见上表）。它相对游戏内完整场面省略的主要是：附魔列表/光环细则、风怒角标（控件未绑 `WINDFURY`）、以及战斗临时态。若记忆中是「完全无关键词的纯立绘条」，与当前源码不符。

## 2. 我们原始层里已有的等价数据（已核实）

诊断插件每场 `combat_start` 写 `type=entities`；Combat 态写 `type=hdt_bb`（含完整 `invoker._input`）。

### 2.1 `entities`（`reason=combat_start`）——与 HDT 快照同构

- 每实体：`cardId`、`tags`（枚举名或数字键）、`info`（含 `LatestCardId`、`BoardOrder` 等）。
- `context.opponent.board` / `player.board` 给出场面实体 id 列表；筛 `CARDTYPE=MINION`（值为 4）且 `ZONE=1` 即开战随从。
- 本机样本回合 5：对手 4 随从的 `CardId` / `ATK` / `HEALTH` / `TAUNT` / `PREMIUM` / `DEATH_RATTLE` 与同回合 `invoker._input.Opponent.Side.items` 的 `CardID` / `MaxAttack` / `MaxHealth` / `Taunt` / `Golden` **一一对齐**（金色实体 `cardId` 为 `…_G`，BB 侧为基卡 id + `_data.Golden=true`）。

→ **仅用 entities 即可复现 HDT `BoardSnapshot` 所用字段**（含亡语标签 `DEATH_RATTLE`）。

### 2.2 `invoker._input` 场面——阵容条足够，亡语需补

`Opponent`/`Player` → `Side.items[]`：

| 渲染所需 | BB 字段 | 备注 |
| --- | --- | --- |
| 卡图 id | `CardID`；金色时常无 `_G` 后缀 | 取肖像时若 `Golden` 需映射到 `CardID_G` 或 HSJSON 金色资源 |
| 攻 / 血 | `_data.MaxAttack` / `MaxHealth` | 勿用开战时常为 0 的 `LastKnownAttack/Health` |
| 金色 | `_data.Golden` | |
| 嘲讽 / 圣盾 / 剧毒 / 毒液 / 复生 / 潜行 / 风怒 | `_data.Taunt` / `Div` / `Poisonous` / `Venomous` / `Reborn` / `Stealth` / `Windfury` | `Div` 为 0/1 |
| 亡语角标 | **无**独立 bool | 先天亡语在卡牌定义；额外亡语在 `AdditionalDeathrattles`。要对齐 HDT 角标应读 entities 的 `DEATH_RATTLE`，或查 CardDefs |
| 场上顺序 | `items` 列表顺序 | 与 entities 的 `ZONE_POSITION` 一致（样本已对） |

## 3. 外部资源可达性（已核实）

| 资源 | 可达？ | 证据 |
| --- | --- | --- |
| 随从圆形肖像 | 是 | HSJSON `HEAD https://art.hearthstonejson.com/v1/256x/BGS_119.jpg` → 200；本机 CardPortraits 缓存约 222 张 |
| 卡牌定义（名、基础攻血、稀有度等） | 是 | HDT 从 hearthstonejson 拉 `CardDefs`（见 `bobsbuddy-public-api.md` / `CardDefsManager`）；亦可用公开 JSON |
| 关键词/边框 PNG | HDT 安装内可用，**非**独立开放资源 | 源码 `App.xaml` 引用 `Resources/Minion/*.png`；本机源码检出中该目录为空（资源随构建嵌入 exe）。再分发受 HDT 专有条款约束（`licensing.md`） |
| 直接离线调用 `BattlegroundsOpponentInfo` | **否** | 控件绑定 `Core.Game`、实时 `Entity`、Overlay 缩放；没有「传入 JSON → 出图」的公共 API |

## 4. 结论

**数据足够。** 用诊断记录的 `entities@combat_start`（首选）或 `invoker._input` 场面（次选，亡语需补），加上 HSJSON 肖像（及可选 CardDefs），可以离线画出与 HDT 上次对手阵容条同信息量的局面图。

**不能**指望「打开 HDT 控件、喂我们的 dump」一条龙；需要自建渲染（或仅在 HDT 进程内插件里复用 `BattlegroundsMinion`）。边框/角标贴图要么本机从 HDT 资源取用（个人、不分发），要么用简化自绘替代。

神祇条、三连/升级回合统计**不在**上述场面 dump 的完备范围内；若产品只要「随从横排阵容图」，可忽略。
