# 诊断记录批评估：2026-09-27 ~ 2026-10-03

> 这份文档回答：异地/后续采集带回的 `data/BgHelperDiag` 有多少可用对局、跨 HDT/BB/炉石版本后完整度如何、相对 P1 基线补上了哪些覆盖、还有哪些质量问题。
> 只含统计与匿名摘录；原始 `records.jsonl` / `power.log.gz` / `salt.txt` 不入库（见 `.gitignore` 的 `data/`）。

```text
样本根目录：仓库 data/BgHelperDiag（所有者 2026-10-04 放入）
插件：HdtDiagLogger 0.1.0
对局目录：48（另有 salt.txt）
日期跨度：2026-09-27 ~ 2026-10-03
工具：spikes/hdt-diag-logger/tools/check_capture.py、eval_dataset.py、eval_fields.py、eval_anon_corruption.py
对照基线：facts/diag-capture-measured.md（3 局 / 27 场，HDT 1.58.3 / BB 1.78.1）
最后核实：2026-10-04
```

## 1. 版本队列

| 日期 | 局数 | HDT | BobsBuddy | HearthDb | 备注 |
| --- | ---: | --- | --- | --- | --- |
| 09-27 | 8 | 1.58.3.8362 | 1.78.1.0 | 36.6.0 | 与 P1 基线同 BB |
| 09-28 | 6 | 1.58.4.9001 | 1.80.1.0 | 36.6.0 | Input 顶层字段相对 1.78.1 无增减 |
| 09-29 ~ 10-01 | 18 | 1.58.5.9002 | 1.81.2.0 | 36.6.0 | |
| 10-02 ~ 10-03 | 16 | 1.58.6.9003 | 1.85.0.0 | 36.6.3 | Player 侧新增 `DiscardCounter`（本批值多为 0） |

`meta.hearthstoneBuild` 在同一 HDT 进程内会在 `56608` 与 `253216` 间翻转：新进程第一局常写 `56608`，随后对局写 `253216`。**不能用该字段做补丁分桶**；真实炉石 build 需另核（游戏客户端或 CREATE_GAME 后再读）。

本机 `%APPDATA%\...\BgHelperDiag` 仍只有 P1 的 3 局（09-25/26），与本批是两套目录。

## 2. 验收（与 check_capture 同口径）

| 指标 | 结果 |
| --- | --- |
| 对局目录 | 48 |
| `endReason=game_end` 且有实质战斗 | 46（另：`20261002_224445` 为 `next_game_start` 空局；`20261003_102720` lines=0） |
| 战斗场次 | 539 |
| 完整（开战快照 + 本回合 Input + Output + 结束快照） | **537 / 539（99.6%）** |
| 缺 Output | 2 场：`20261001_153442` 回合 9；`20261003_092954` 回合 1 |
| `meta.errors` / `writerErrors` / `probeInitError` | 全样本 0 / 0 / null |
| 匿名化扫描（BattleTag / account id 模式） | 48/48 通过 |
| 双人 | 0 |
| `records.jsonl` 体积 | 合计约 1.34 GB（均值约 27.9 MB/局）；`power.log.gz` 约 65.6 MB |

插件回调耗时：`line` max 约 80–194 ms，`entities` max 约 29–134 ms，均远低于 HDT 插件 2000 ms 上限。

## 3. 相对 P1 清单的覆盖

| 项 | P1（27 场） | 本批 | 结论 |
| --- | --- | --- | --- |
| 单人完整战斗 | 27 | 537 | 足够支撑 P2-T0 / P3-T0 起步 |
| `Anomaly` | 全 null | 538/538 null | 仍无畸变正例 |
| 对手奥秘非空 | 1 | 9 场战斗 | 仍偏少，P2-T6 继续记 |
| 任务 | 1 条 | 11 场战斗 | 有所改善 |
| 对手 `ResourcesSpentThisGame` | 0 | 538/538 为 0 | 缺口再现确认 |
| 对手 `FriendlyMinionsDeadLastCombatCounter` | Input 恒 0 | 538/538 为 0 | 缺口再现确认 |
| 战斗中 `reRunCount>0` | 1 | 39 次 dump | 可做 5.2 补录分析 |
| 饰品 | ~19 CardId | 129 种（含 `BG30_Trinket_1st/2nd` 槽位名） | 多样性足够 |
| `DamageCap` | 5/10/15 | 另见 **0**（39 场，多为回合 11–17） | 晚期/特殊规则需在重放时保留原值 |
| 对手手牌 | 本批早期曾见全已知 | 本批 Combat Input 中大量 `MinionCardEntity` / `SpellCardEntity` 等，经 `$type`/Data 可还原标识 | 与「Unknown 占位」不是同一问题 |

种族组合：39 种五种族集合；畸变（`ABERRATION`）频繁入池，但 Input.`Anomaly` 仍为空。

## 4. 质量问题（已核实）

### 4.1 匿名化误替换 `Player` 标识符

`Anonymizer.Apply` 对已知玩家名做**无词边界**的 `string.Replace`。当某对手显示名恰好为 `Player`（或与 JSON 中 `Player` 标识符碰撞）时，会把：

- 属性名 `Player` → `player_<hash>`
- `$type` 中的 `BobsBuddy.Simulation.Player` → `BobsBuddy.Simulation.player_<hash>`

本批命中 **10 局**（同 hash `player_ab598ebe`）：

`20260930_222717`，`20261001_201133` ~ `215123`（5 局），`20261003_102720` / `102801` / `105158`。

已知名在插件进程内跨对局累积，HDT 重启后清空。数据未丢，导入时把该占位键/`$type` 映射回 `Player` 即可（`spikes/replay-harness/tools/roundtrip.py` 的 `fix_anon`）。**已在插件 0.2.0（P2-T2，2026-10-05）修复**：词边界 + 结构保留名；新采集不应再腐蚀。本批 0.1.0 旧数据导入侧仍需修复。

### 4.2 上一局 invoker 残留

40/48 局在第一场 `combat_phase=true` 之前已有带 Input 的 `hdt_bb`（通常 2 条）。与 P1 结论一致；`meta.hdtBobsBuddyDumps` 是探针累计值，可大于本局 `hdt_bb` 条数。

### 4.3 BB 模式演进

相对 1.78.1，1.85.0 的 Input 侧至少多了各方 `DiscardCounter`。跨版本重放必须对齐 DLL（强化 Q-011）。

## 5. 对后续任务的含义

1. **P2-T0**：样本足够；解析需版本路由 + invoker 过滤 + 匿名化键修复。
2. **P3-T0**：建议先在单一队列（例如 BB 1.85.0 的 ~16 局）做交叉模拟，再扩到全量。
3. **P2-T1 / 插件**：修匿名化；`hearthstoneBuild` 推迟到对局元数据稳定后写入；按对局 id 丢弃旧 invoker。
4. **P2-T6**：继续盯畸变、双人、Malorne/花费、对手奥秘比例。

## 6. 工具

复现本批统计：

```text
python spikes/hdt-diag-logger/tools/check_capture.py --all --root data/BgHelperDiag --hs-logs none
python spikes/hdt-diag-logger/tools/eval_fields.py data/BgHelperDiag
python spikes/hdt-diag-logger/tools/eval_anon_corruption.py data/BgHelperDiag
```
