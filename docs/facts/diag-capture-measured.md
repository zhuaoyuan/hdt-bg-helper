# 诊断记录实测：字段可见性、时序与 TagTransfer

> 这份文档回答：官方 HDT 诊断记录里，Bob's Buddy 输入各字段实际能不能从实体快照对上、对手一侧哪些看得到、标签变化动作和插件回调谁先谁后。
> 统计与匿名摘录；不含 BattleTag、完整 Input JSON、`records.jsonl`。

```text
实测环境：官方 HDT 1.58.3.8362 / BobsBuddy 1.78.1.0 / HearthDb 36.6.0 / 炉石 build 56608
插件：HdtDiagLogger 0.1.0
样本：3 局单人酒馆战棋、27 场战斗（20260925_170955_cd944c 9 场、20260925_173911_a8ee8b 8 场、20260926_082753_e07627 10 场）
工具：spikes/hdt-diag-logger/tools/check_capture.py、analyze_fields.py、analyze_timing.py、analyze_q007.py
最后核实：2026-09-26
```

对照脚本必须只用**本场** `TAG_CHANGE GameEntity tag=2022 value=0` 及之后的 `hdt_bb`。后两局开局时 HDT 静态字典里还留着上一局的 invoker，插件会先倒出旧回合的 Input（键仍是 7/8/9）。不按行号过滤会把上一局的血量、等级、计数器当成本场。

## 1. 验收（方案第 5 节）

| 局 | 战斗 | 开战快照 / Input / Output / 战后快照 | 错误 | 匿名化 | 快照最长 | 单行回调最长 |
| --- | --- | --- | --- | --- | --- | --- |
| cd944c | 9/9 | 全有 | 0 | 通过 | 19.3 ms | 43.6 ms |
| a8ee8b | 8/8 | 全有 | 0 | 通过 | 7.7 ms | 27.8 ms |
| e07627 | 10/10 | 全有 | 0 | 通过 | 14.0 ms | 40.8 ms |

- HDT 日志无插件超时警告（`PluginManager.MaxPluginExecutionTime` 2000 ms）。唯一 `2000ms` 命中是启动时 `UpdateManager`，与插件无关。
- 三局都是 `GT_BATTLEGROUNDS`、非双人；`probeInitError` 为空；Q-002 反射继续可用（`_input`、`Output`、`_state`、`_reRunCount`）。
- 原始行对照：第三局与当局 `Power_old.log` 的 `PowerTaskList.DebugPrintPower` 行结构 0 处不一致；前两局各有个位数结构差（对局里，且含匿名化后的 `Entity=` 名），对局结束后炉石多写 10–29 行。
- 体积：`records.jsonl` 约 10–19 MB / 局，`power.log.gz` 0.6–1.0 MB。不入库。
- 不需要修插件，也不需要为完整性重打。覆盖缺口（无畸变、无 Malorne、任务极少、双人 0）见第 6 节。

## 2. Q-006：`OnPowerLogLine` 时 HDT 的更新是否已完成

**已核实：** 标签变化触发的动作（含 `StartCombat` → 同步 `SnapshotBoardState`）在 `PowerHandler.Handle` 末尾 `InvokeQueuedActions`（`PowerHandler.cs:2004–2005`）里跑完，然后才调用 `OnPowerLogLine`（`LogWatcherManager.cs:182–183`）。插件看到触发行时，HDT 该行的更新已经完成。

证据（27/27）：

| 事件 | 行 |
| --- | --- |
| `GameEntity` 标签 `3533` 1→0 | 插件 `combat_phase=true` 与 `entities combat_start` 的同一行 |
| `GameEntity` 标签 `2022` 1→0 | 该回合第一次带 `_input` 的 `hdt_bb` 的同一行 |

- `3533=0` 比 `2022=0` 早 54–105 行（中位 81 行，墙钟约 2.5 秒）。`3533` 置 `IsBattlegroundsCombatPhase` 并做 HDT 自己的场面快照；`2022` 才启动 Bob's Buddy（`TagChangeActions.cs:199–224, 226–245`）。
- 两行之间本批随从数量不变：实体快照（`3533`）与 HDT Input（`2022`）的双方随从数 27/27 一致；过滤残留 invoker 后己方英雄 `Health` / `Tier` 也 27/27 一致。
- 开战快照里 `HasOutstandingTagChanges` 始终为 0。
- 战斗中重跑本批很少：第一局回合 6 在 `2022=0` 之后第 43 行因随从 `TAG_CHANGE` 出现 `reRunCount=1`，与 5.2 的补录入口相符。`opponent_secret_triggered` 公开事件 0 次。
- **[推断]** `creationTag` 行不调用 `InvokeQueuedActions`（源码已写，`PowerHandler.cs:2004`）。本批没有单独对照这类行。

标签含义（本批）：`2022` 与 `3533` 都打在 `GameEntity` 上，每场战斗各出现一次 1 和一次 0。单人模式 Bob's Buddy 跟 `2022` 1→0，不是 `3533`。

## 3. Q-007：TagTransfer 实际带了哪些标签

每场战斗对手玩家实体 `PLAY` 区都有一张 `Bacon_TagTransferPlayerE`（27/27）。上一场的附魔留在 `REMOVEDFROMGAME`（区 5），不再参与读取。己方玩家实体上也常挂一张，HDT 只对对手走 TagTransfer（`Invoker:719–722`）。

`ReadPlayerCounter` 字段：HDT Input 对手值与「TagTransfer 标签，缺省当 0」27/27 一致（`TAVERN_SPELL_*` 除外，见下）。

| 字段 | 标签 | TF 出现（非零 / 27） | Input 对手非零 | 结论 |
| --- | --- | --- | --- | --- |
| `PiratesSummonCounter` | `2358` | 11 | 11 | TF 携带，可见 |
| `TavernSpellCounter` | `3088` | 19 | 19 | TF 携带，可见 |
| `BattlecryCounter` | `3236` | 16 | 16 | TF 携带，可见 |
| `DeathrattleCounter` | `4639` | 15 | 15 | TF 携带，可见 |
| `GoldenMinionsPlayedCounter` | `4799` | 9 | 9 | TF 携带，可见 |
| `BeastsSummonCounter` | `3962` | 8 | 8 | TF 携带，可见 |
| `ElementalPlayCounter` | `BACON_ELEMENTAL_PLAY_COUNTER`（2878） | 6 | 6 | TF 携带（快照里是名字不是数字） |
| `MagnetizeCounter` | `3670` | 2 | 2 | TF 携带，可见 |
| `TavernSpellAtkBuff` / `HealthBuff` | `TAVERN_SPELL_*_INCREASE` | 3 / 2 | 4 / 4 | HDT 先读对手玩家实体（26–27/27 对上），TF 只是后备；与源码 `Invoker:860–867` 一致 |
| `FriendlyMinionsDeadLastCombatCounter` | `2717` | **0** | **0** | TF **从不带**。对手玩家实体 9/27 场有非零 1–9，HDT 读 TF 得到 0 |
| `ResourcesSpentThisGame` | `NUM_RESOURCES_SPENT_THIS_GAME` | 0 | **0**（己方 26/27 非零） | 对手实体与 TF 都不下发。本批无 Malorne，无法测反推 |
| `TastyLobsterCounter` | `4803` | 0 | 0 | 本批双方都是 0，不能区分「不传输」和「没打出」 |
| `VolumizerAtkBuff` / `HealthBuff` | `4468` / `4469` | 0 | 0 | 对手 0；己方各有 2、3 场非零。对手是否传输未测到正例 |
| `ElementalsGiveExtraAttack` / `Health` | `4002` 等 | 0 | 0 | 本批双方都是 0 |

TF 上还常见、但 HDT 不按 3.7 去读的标签：`PLAYER_TECH_LEVEL`、`4212`、`2245`、`2336`、`2753`、`3809`、`3927`、`4640` 等。英雄等级 HDT 读英雄 / 玩家实体，不靠这些。

`2717` 缺口：9/27（33%）场对手玩家实体有值、TF 没有、Input 为 0。无法从本批区分「游戏不传输该标签」还是「玩家实体是上一场残留」（HDT 换对手时只清酒馆法术和血宝石四个标签，`TagChangeActions.cs:1684–1699`）。采集应同时记下 TF 与玩家实体，标为已知偏差风险。

## 4. 其他字段实测

| 项 | 结果 |
| --- | --- |
| `availableRaces` | 27/27 有 5 个种族。三局集合：机械、海盗、畸变、野兽、鱼人、亡灵、元素、野猪人、恶魔、龙 |
| `Anomaly` | 27/27 `anomalyDbfId` 为空，Input `Anomaly` 为 null |
| `DamageCap` | 出现 5 / 10 / 15 |
| `isDuos` | 恒为 false |
| 场面顺序 | 双方随从数与 Input `Side` 27/27 一致 |
| 饰品 | 双方开战快照与 Input 都有（本批约 19 种 CardId，含 `BG30_MagicItem_*`、`BG32_MagicItem_*`、`BG35_MagicItem_*`、`BG36_MagicItem_*`） |
| 任务 | 仅 1 条 `BG24_Quest_123`；任务奖励区本批为空 |
| 目标 / 神祇 | 27/27 双方 Input 各有 1 个 `DeitySigil`；`SECRET` 区常是目标实体，不是战斗奥秘 |
| 己方奥秘 | Input 有 `Redemption`、`PackTactics`、`VenomstrikeTrap` 等 |
| 对手奥秘 | 27 场里 Input 非空只有 1 次（`PackTactics`） |
| 对手手牌 | 本批 Input 27 张全是已知 `CardId`，0 张 `UnknownCardEntity`（偏战斗可见牌，不能外推到所有隐藏手牌） |
| 英雄技能 | 双方都有 CardId；对手 `EXHAUSTED` / `BACON_HERO_POWER_ACTIVATED` 在已使用时会出现（可见） |
| 3.6 玩家附魔 | 对手 `PLAY` 区见过 `BG25_008pe`（永恒骑士）、`BG25_011pe`（亡灵加成）、`BG26_159pe`（血宝石）；Input 对应 `EternalKnightCounter`、`UndeadAttackBonus`、`BloodGem*` 非零。己方见过甲虫、血宝石 |
| 第 7 节未赋值字段 | `DeepBluesCounter`、`AnySpellCounter`、`BackToBackCounter` / `Atk` / `Health` 在 HDT Input 上 27/27 为 0。会不会被 BB 读取仍要独立进程实验（Q-013） |
| 输出 | 凡有 Output 的 dump，`simulationCount=9996` 且 `myExitCondition=CompletedSimulations` |

HDT 日志里这三局 `Duration=`（进程内、6 线程、1 万次）约 74–854 ms，全部跑完迭代。这是 HDT 当场耗时，不是独立进程的 Q-009。

## 5. 采集时机（按本批）

| 时机 | 什么时候 | 本批是否够用 |
| --- | --- | --- |
| 对局级 | 开局读 `availableRaces`（内存）、`Anomaly`、`DamageCap` | 种族有；畸变为空 |
| 战斗开始（BB 快照） | `2022` 1→0 同一行，HDT 已写好 `_input` | 27/27 对得上 |
| 战斗开始（插件实体快照） | 目前在 `3533` 1→0，比 BB 快照早约 80 行 | 本批随从 / 血量 / 等级仍一致；P2 应在 `2022` 再拍一次或只信这一次 |
| 战斗中揭示 | 改 `_input` 并 `TryRerun` | 本批几乎没有（1 次重跑，0 次对手奥秘公开事件） |
| 派生 | 对手 `ResourcesSpentThisGame` 靠 Malorne | 本批 0 次 |

## 6. 仍待实测

- 双人模式（不用 TagTransfer）。
- 畸变非空、`Bring in the Buddies`、Malorne 反推花费。
- 对手 Tavish 装填、Sandy / Floop / 召唤法球、Choral / Dramaloc 等手牌附魔补录。
- `4803`、`4468`/`4469`、元素额外攻血的对手正例。
- 对手未知手牌 / 未知奥秘占 `partial` 的长期比例（本批手牌全已知、奥秘几乎没有，不能当基准）。
- `2717` 是「不传输」还是「玩家实体残留」。
- 第 7 节未赋值字段对 BB 结果的影响（Q-013）；独立进程耗时与跨 BB 版本偏差（Q-009、Q-011）。
