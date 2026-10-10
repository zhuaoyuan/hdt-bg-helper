# 2026-10-07 最新对局版本与兼容性核对

## 目标

核对刚结束的一盘诊断对局：HDT/BB 是否相对此前主队列升级；采集是否完整；能否并入既有 `1.85.0.0` 战力计算。

## 做了什么

1. 定位最新**已结束**局：`%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\20261007_210456_177672`（相对上一复盘局 `20261006_215623_f41aef`）。
2. `check_capture.py`：solo BG，`probeInitError` 空，匿名化 OK，**8/8** 战斗完整（startSnap + Combat `hasOutput` + endSnap）。
3. 用 `standard_layer.combat` 抽 mid-turn Input：与 `f41aef` 比对 Input / Player / Opponent 顶层键及 `Side.items` 随从键样本——**无增减**。
4. 扫本机 diag 根目录 BB 版本计数；确认 `bb-dirs.json` 尚无 `1.88.6.0`；团子目录已有 `2026年10月07日.txt`（未同步进仓库 `data/tuanzi`）。

## 发现

| 项 | 上一局 `f41aef` | 本局 `177672` |
| --- | --- | --- |
| HDT | 1.58.6.0（`directory=HDT`） | **1.58.9.0**（`directory=HDT`） |
| BobsBuddy | 1.85.0.0 | **1.88.6.0** |
| HearthDb | 36.6.3 | 36.6.3（同） |
| hearthstoneBuild | 56608 | 56608（同） |
| plugin / schema | 0.2.0 / 1 | 0.2.0 / 1（同） |
| 战斗 | 16 | 8（约 21:04–21:17） |

- 本机 `%LOCALAPPDATA%\HearthstoneDeckTracker` 仍停在 `app-1.58.6`（BB 1.85）；本局实际跑在 **团子 `C:\Program Files\HDT`**（HDT 1.58.9 + BB 1.88.6）。
- 核对时尚有进行中局 `20261007_211929_3f32a5`（同 BB 1.88.6，meta 未 `endedAt`）。
- **战力：** 不可并入 `data/strength/1.85.0.0`（Q-011 / ADR-0011；L2 关，Q-016）。须新桶 `1.88.6.0`；冷启动在 \(G\ge G_\text{min}\) 前为 `insufficient`。
- **采集/标准层：** schema 与插件路径兼容，可导入；离线重放需把 `bb-dirs.json` 增加 `1.88.6.0` → `C:\Program Files\HDT`，并做同版本 roundtrip 冒烟（Q-002 升级路径）。

## 留下的东西

- 事实：`docs/facts/diag-bb188-first-game-20261007.md`
- 未做：标准层导入、`bb-dirs` 更新、1.88 roundtrip、战力回填、复盘 HTML
