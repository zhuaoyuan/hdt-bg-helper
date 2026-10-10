# 诊断记录：BB 1.88.6 首局（相对 1.85 主队列）

> 这份文档回答：2026-10-07 最新已结束对局相对此前主队列（BB 1.85.0）版本差多少、采集是否完整、Input 反射字段是否仍同构、能否与 1.85 战力池混算。

```text
样本：%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\20261007_210456_177672
对照：同目录 20261006_215623_f41aef（BB 1.85.0.0）
工具：spikes/hdt-diag-logger/tools/check_capture.py；tools/standard_layer/combat.py（extract_input / pick_combat_bb）
最后核实：2026-10-07
```

## 1. 版本

| 组件 | `177672`（新） | `f41aef`（对照） |
| --- | --- | --- |
| HDT | 1.58.9.0，`directory=HDT` | 1.58.6.0，`directory=HDT` |
| BobsBuddy | **1.88.6.0** | 1.85.0.0 |
| HearthDb | 36.6.3 | 36.6.3 |
| hearthstoneBuild | 56608 | 56608 |
| pluginVersion / schemaVersion | 0.2.0 / 1 | 0.2.0 / 1 |

DLL 侧：`C:\Program Files\HDT\BobsBuddy.dll` 文件版本 1.88.6.0；`HearthstoneDeckTracker.exe` 1.58.9.0。  
`%LOCALAPPDATA%\HearthstoneDeckTracker\app-1.58.6` 仍为 BB 1.85.0.0（本局未用该目录）。

## 2. 采集完整度

`check_capture.py --hs-logs none`：

- `endReason=game_end`，solo BG，`probeInitError=null`，`errors=0`，匿名化 OK
- 战斗 **8/8** 完整（startSnap、Combat `hasOutput`、endSnap）
- `hdt_bb` 44 条；标准层抽取路径下 8 场均可 `extract_input` + `extract_output`

## 3. Input 字段同构（反射 dump 键）

对 turn≈5 的 Combat `hdt_bb`（`pick_combat_bb`）：

- Input / Player / Opponent **顶层键相对 `f41aef` 无增减**
- `Side` 仍为 `List<Minion>`，序列化为 `items`（非 `$values`）；随从样本键（前 20 个 plain 名）与对照局一致
- Output 键集一致（含 `winRate` / `simulationCount` 等）

本条只断言**键名同构**，未做 1.88.6 同版本离线 roundtrip（尚未把该版本写入 `bb-dirs.json`）。

## 4. 与既有战力计算的兼容性

| 用途 | 结论 |
| --- | --- |
| 写入标准层 / 复盘导入 | **可以**（插件 schema 未变；字段可抽取） |
| 并入 `data/strength/1.85.0.0` 循环赛 / 分位 | **不可以**（ADR-0011 按 BB 分桶；Q-016：L2 关）。虽 1.85→1.88.6 **同 Input 五率**本批无显著差（`replay-roundtrip.md` §3.2），仍不混参照池 |
| 新桶 `1.88.6.0` 冷启动 | 需攒局至 \(G_\text{min}=6\) 前分位为 `insufficient`；`bb-dirs` 已登记 `1.88.6.0` → `C:\Program Files\HDT` |

核对时尚有未结束局 `20261007_211929_3f32a5`（同 HDT/BB 1.88.6）。
