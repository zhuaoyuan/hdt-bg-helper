# 2026-10-06 P3-T5 生成最近一盘复盘

## 目标

用已有 `tools/review_view`（P3-T5）为**最近一盘**诊断对局生成赛后静态 HTML。

## 做了什么

1. 定位最近局：`%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\20261006_215623_f41aef`（鼠王，16 场战斗；当时尚未进 `turns.jsonl`）。
2. 标准层：`python -m tools.standard_layer --game f41aef --out data\standard_f41aef` → 16/16 `ready`，`resultSource=hdt`；无团子配对（`data/tuanzi` 尚无 10-06）。合并进 `data/standard/turns.jsonl`（备份 `turns.jsonl.bak_before_f41aef`），全库 56 局 / 656 行。
3. 战力：`tools.strength increment --bb-version 1.85.0.0 --game-id 20261006_215623_f41aef`（全侧 ~2058 对，约 96s）；再对该局 16 个 Player 场面评估分位并合并进 `strength.jsonl`（备份 `strength.jsonl.bak_before_f41aef`）。T15–T16 `insufficient`（晚回合样本过稀）；T14 为 L1 放宽。
4. 阵容：`board_render --game f41aef --side both --offline` → 32 PNG（缺 9 个肖像，离线占位）。
5. 复盘：`python -m tools.review_view --game f41aef ...` → `data/review/20261006_215623_f41aef/index.html`（并写对手分位缓存 `strength_opp.jsonl`）。

## 发现

- AppData 诊断目录已有 10-05 晚间多局 + 今日 `f41aef`，仓库 `data/BgHelperDiag` 仍停在 10-04；标准层默认扫两边，但**此前未重跑导入**，故「最近一盘」需先导入再复盘。
- `--game` 导入会**整文件覆盖** `turns.jsonl`，单局增量必须侧写再合并。
- 无团子日文件时 `placement=null`；战果可从 HDT 诊断还原。
- 回合 ≥14 参照池变薄：分位变宽 / L1 / insufficient，复盘页会诚实标出。

## 留下的东西

- 复盘页：`data/review/20261006_215623_f41aef/index.html`（及 `model.json`、`boards/`）
- 侧写导入：`data/standard_f41aef/`
- 合并后的 `data/standard/turns.jsonl`、`data/strength/1.85.0.0/strength.jsonl`（及 `.bak_before_f41aef`）
- 未做：团子 10-06 配对、全量 `percentile` 重写、T5 验收 5 人核
