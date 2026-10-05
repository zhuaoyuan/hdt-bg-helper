# 2026-10-05 — 拔线场次 × HdtDiagLogger 完整性

## 做了什么

对照团子版对战记录 `C:\Program Files\HDT\对战记录\2026年10月05日.txt`（已拷入 `data/tuanzi/`）与当日 `BgHelperDiag` 三目录，核对拔线回合的 diag 是否完整。

工具：`check_capture.py`、`eval_tuanzi_crosscheck.py`；临时脚本已删。

## 三局对应关系

| 团子局 | 英雄 | 名次 | 拔线 | diag 目录 | 对应依据 |
| --- | --- | --- | --- | --- | --- |
| 局1 | 泽瑞拉 | 5 | T6/T7 直接拔线；T9 不知结果 | `20261005_070214_bdd811`（残局） | `session_start.reason=enabled_mid_game`；game_end 残留 T9/T10 阵容与团子攻血多重集 **完全一致** |
| 局2 | 雷诺·杰克逊 | 显示第1 / 原分0（与 T10「被抬走」矛盾，疑团子战绩异常） | 无 | `20261005_070312_6ab052` | ZONE=1 `TB_BaconShop_HERO_41`；阵容+五率交叉验证 |
| 局3 | 奥拉基尔 | 7 | T8/T10 不知结果；T9 直接拔线 | `20261005_072336_c88ca9` | ZONE=1 `TB_BaconShop_HERO_76`；T8/T10/T11 阵容与团子一致 |

时间线：`bdd811` 07:02–07:03（`next_game_start`）→ `6ab052` 07:03–07:21 → `c88ca9` 07:23–07:44。

## 拔线类型与 diag 完整性

团子文本里拔线有两类：

1. **直接拔线**（`第N回合，我直接拔线~`）：本回合无阵容、无模拟、无实际结果。
2. **打前拔线 / 不知结果**（有阵容+模拟，文末 `我拔线了，插件并不知道结果~`）：团子缺实际战果；HDT/BB 开战前 Input/Output 仍可能已写出。

### 局1（插件中途才开）— **不完整**

- 仅 5 条记录；`power.log.gz` 空；`create_game=0`；无 `combat_phase` 分段。
- 唯一有用内容：局末 `hdt_bb` 对 T9（Shopping）/ T10（GameOver）的残留 dump，阵容+五率与团子一致。
- T1–T8（含两次直接拔线）**完全没有** diag。

### 局2（无拔线）— **完整**

- `check_capture`：**10/10** complete；`power` 89707 行；`endReason=game_end`。
- 与团子交叉：阵容/模拟五率对齐（见交叉脚本输出）。

### 局3（有拔线）— **模拟侧基本完整，实际战果与 T9 战斗 dump 有缺口**

| 回合 | 团子 | diag Input/Output（Combat） | combat_start/end 实体快照 | 结论 |
| --- | --- | --- | --- | --- |
| T1–T7 | 正常 | 有 | 正常（end 计数递增） | 完整 |
| T8 | 不知结果 | **有**（board 与团子一致，sim=19998） | start=1074；end 记在下一购物相位 | **BB 完整**；缺团子「实际结果」；随后出现 `create_game`（重连） |
| T9 | 直接拔线 | **无本局 Combat dump**（segment 内仅 Shopping 且 `hasInput/Out=false`） | start=525；**end=8**（异常稀疏） | **不完整**；又一次 `create_game` |
| T10 | 不知结果 | **有**（board 一致） | start=594；end=8 | **BB 完整**；缺实际结果；再 `create_game` |
| T11 | 正常抬走 | 有 | start=765；game_end=891 | 完整 |

`check_capture` 汇总：`complete combats 10/11`（缺的正是 T9）。

局初还 dump 了上一局（雷诺 T9/T10）的残留 invoker——与已知「应按对局丢掉旧 invoker」问题一致，**不能**当成奥拉基尔 T9 的数据。

## 发现

1. **「不知结果」≠ diag 无模拟数据。** 局3 T8/T10、局1 残局 T9 均有完整 `_input`/`Output`；缺的是团子侧实际胜负（可用相邻回合 `friendlyHealth` 差分补一部分，拔线重连时差分会断）。
2. **「直接拔线」→ 该回合通常没有可用 Combat dump。** 局3 T9 即如此；`combat_end` 实体数掉到 8 是拔线信号。
3. **拔线会触发多次 `create_game`**（本局 4 次），污染会话边界；评估时需按对局过滤残留 invoker。
4. **局1 主要缺口来自「中途启用插件」**（`enabled_mid_game`），不是拔线本身抹掉了整局——但拔线回合若发生在插件开启前，同样不会有记录。

## 留下什么

- 事实摘要：[`facts/diag-disconnect-completeness-20261005.md`](../facts/diag-disconnect-completeness-20261005.md)
- 对战记录副本：`data/tuanzi/2026年10月05日.txt`（gitignore）
- 原始 diag 仍在 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\`

## 追加：最新一局 `20261005_082741_20ad61`（08:27–08:49）

团子第 4 局：德雷阿佳丝，第 4 名；拔线 T6–T11（其中 T10 为「直接拔线」）。

| 项 | 结果 |
| --- | --- |
| `check_capture` | **11/12** complete；唯 T10 无 Combat Output |
| 按回合阵容对照 | T1–T9、T11–T12 与团子攻血多重集 **全部一致**；T10 无阵容（直接拔线） |
| 「不知结果」T6–T9、T11 | BB Input/Output 均在 |
| `combat_end` 实体数 | 自 turn=7 起多为 **8**（拔线后 end 快照退化）；`combat_start` 仍正常 |
| `create_game` | **7** 次（重连频繁） |
| errors | 0；`endReason=game_end`；power ≈1.1MB / 111926 行 |

**结论：** 模拟侧基本可用（差 T10）；实际战果与 combat_end 快照因连续拔线不完整。
