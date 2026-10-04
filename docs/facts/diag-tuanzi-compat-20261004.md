# 团子版 HDT 诊断记录兼容性与交叉验证（20261004_200638_13406d）

> 这份文档回答：用「团子版」HDT 跑诊断插件采到的一局，其数据结构是否与官方 HDT 批次兼容；以及能否与团子版对战记录文本交叉对上。

```text
实测环境：团子版 HDT 1.58.6.0（meta.directory=HDT） / BobsBuddy 1.85.0.0 / HearthDb 36.6.3 / 炉石 build 元数据写 56608（不可信，见批评估）
对照官方样本：20261003_105158_c4b8de（官方 HDT 1.58.6.9003，directory=app-1.58.6，同 BB 1.85.0.0）
插件：HdtDiagLogger 0.1.0
样本：data/BgHelperDiag/20261004_200638_13406d（10 场战斗）
对照文本：data/tuanzi/2026年10月04日.txt（团子版对战记录，同日同局）
工具：spikes/hdt-diag-logger/tools/check_capture.py、eval_tuanzi_crosscheck.py
最后核实：2026-10-04
```

不含 BattleTag、完整 Input JSON；统计与英文卡名摘录可入库。原始目录已 gitignore。

## 1. 结论（先看这个）

| 问题 | 结论 |
| --- | --- |
| 与官方 diag 结构兼容？ | **是。** `schemaVersion=1`，记录类型集合相同；归一化匿名化键名后 Input 键集合 **330/330 完全一致**；Output 标量字段集合一致；`Side`/`Minion`/`_data` 形状一致。 |
| 能否当官方数据用？ | **字段级可以。** 需注意 meta 的安装目录名/文件版本号不同，以及本局 `simulationCount=19998`（团子展示与插件 dump 一致；官方样本常见 ~10000）。重放仍按 `meta.bobsBuddy.version` 选 DLL。 |
| 与团子对战记录交叉验证？ | **阵容细节与模拟结论 10/10 一致**；实际战果与 BB 预测在高置信场次一致，低置信场次的偏差符合 RNG，不是采集错误。 |

## 2. 验收与元数据

`check_capture.py`：`complete combats 10/10`，错误 0，匿名化无 BattleTag/账号模式，单行回调最长约 52 ms。

| 项 | 本局（团子） | 对照官方局 |
| --- | --- | --- |
| `hdt.version` / `directory` | `1.58.6.0` / `HDT` | `1.58.6.9003` / `app-1.58.6` |
| `bobsBuddy` | `1.85.0.0` / `HDT` | `1.85.0.0` / `app-1.58.6` |
| `hearthDb` | `36.6.3` | `36.6.3` |
| 记录类型 | event / create_game / combat_tag / combat_phase / entities / hdt_bb / perf | 同左 |
| `Player` 键 | **保留字面 `Player`** | 该官方样本被匿名化改成 `player_ab598ebe`（已知插件缺陷） |
| 本局 `simulationCount` | **19998**（与团子文本一致） | 该样本 10000 |

非破坏性差异只有安装布局与版本后缀；不改变 Input/Output schema。

## 3. 结构对照细节

- Input 顶层：`Player`/`Opponent`/`PlayerTeammate`/`OpponentTeammate`/`Anomaly`/`DamageCap`/`availableRaces`/`isDuos`/`turn`（与官方同 BB 版本一致；含 `DiscardCounter` 等 1.85.0 字段）。
- 场面：`Player.Side` 为 `List<BobsBuddy.Minion>`，序列化为 `{ "$type": "...List<...>", "items": [ ... ] }`。
- 随从战斗数值在 `_data`：`MaxAttack` / `MaxHealth` / `Golden`（`LastKnownAttack/Health` 开战时常为 0，不能当攻血）。
- Output 标量：`winRate`/`tieRate`/`lossRate`/`myDeathRate`/`theirDeathRate`/`avDamage`/`medianDamage`/`simulationCount`/`friendlyHealth`/`opponentHealth`/`myExitCondition` — 与官方样本字段集合相同。
- Invoker `$type` 差异来自本局出现的具体随从子类与官方局不同，以及官方局 `Player` 类型名被匿名化腐蚀；不是 schema 分叉。

## 4. 与团子对战记录交叉验证

团子文本按回合给出：双方英雄中文名、双方随从（名 + 可选「金」+ 攻-血）、模拟五率 + 次数、实际结果与伤害。

对照方法（`eval_tuanzi_crosscheck.py`）：

1. 取每场 `state=Combat` 且 `hasOutput` 的 `hdt_bb`；
2. 阵容：`Side.items[]` → `CardID` / `minionName` / `_data.MaxAttack|MaxHealth|Golden`；实体开战快照 `ZONE=PLAY`+`CARDTYPE=MINION` 的 `ATK`/`HEALTH` 作第二路；
3. 模拟：`winRate` 等 ×100 对比文本百分比；`simulationCount` 对比「模拟 N 次」；
4. 实际战果：文本「赢/平/输」与伤害；并用相邻回合 `Output.friendlyHealth` 差分核对己方掉血。

### 4.1 阵容与模拟（10/10）

| 回合 | 文本对手 | diag 对手英雄 CardId | 双方随从数 | 攻血金多重集 | 五率+次数 |
| --- | --- | --- | --- | --- | --- |
| 1–10 | 德雷阿佳丝 / 特莱斯塔斯… / … / 因葛 | `BG36_HERO_000` 等与文本英雄对应 | 10/10 一致 | **10/10** 与文本一致 | **10/10**（含 19998 次） |

英文 `minionName` 与文本中文名一一可对上（如 Suspicious Prisonguard ↔ 可疑的监狱守卫，Fruit Vendor ↔ 水果商贩）。己方英雄恒为 `BG28_HERO_400` 皮肤（林鬼蛇眼）。

### 4.2 实际战果

| 回合 | 文本实际 | 相邻回合己方血量差 | `medianDamage` | 说明 |
| --- | --- | --- | --- | --- |
| 1–3 | 赢 2/3/4 | 0 | +2/+3/+4 | 高置信，预测伤害=实际 |
| 4 | 平 | 0 | 0 | 一致 |
| 5 | 平 | 0 | +4（67.9% 赢） | **预测≠实际**：RNG，采集与文本都合理 |
| 6 | 赢打 7 | 0 | 0（49.7% 赢） | **预测≠实际**：低置信，实际落在赢分支 |
| 7 | 输挨 10 | **−10** | −10 | 血量差与文本一致 |
| 8 | 输挨 14 | **−14** | −15（cap 15） | 血量差=实际；中位预测差 1 |
| 9 | 赢打 10 | 0 | +10 | 一致 |
| 10 | 输挨 15 抬走 | （终局） | −15；`myDeathRate=99.6%` | 与文本「被抬走」一致 |

**不要**用 `medianDamage` 当「实际结果」的硬验收：它是开战前模拟的典型伤害。本局可验证的实际掉血（T7/T8）与文本完全一致；模拟五率与文本完全一致。

终局：文本第 6 名；diag `endReason=game_end`，10 场完整。

## 5. 对后续工作的含义

- 团子版 + 诊断插件产出的 `records.jsonl` **可与官方批次混用**（按 BB 版本分桶），无需单独 schema。
- 团子对战记录文本适合做**人工/自动交叉验证**（阵容 + BB 展示五率）；不能替代 diag 里的完整 Input（缺计数器/饰品/手牌等）。
- 本局未触发 `Player` 键匿名化腐蚀；官方批里仍有该缺陷，修复优先级不变。
