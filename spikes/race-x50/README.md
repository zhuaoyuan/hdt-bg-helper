# 当局种族池 vs 玩家 X50 战力

探索性问题：酒馆战棋大厅的可用种族池（`rules.availableRaces`）与玩家当局的 X50 战力（木桩梯队 v2）是否相关？如果相关，现有按 `(simPool, turn)` 的参照池是否应拆成更公平的子池？

## 两份分析

1. **全扫描（第一份）**：`analyze.py` —— 10 个种族的联合/单族检验、80 个“种族 × 回合”单元格、精确种族池/聚类分池可行性。
   - 报告：`docs/research/race-pool-x50-20261020.md`
   - 结论：联合模型不显著（R²≈5%、p=0.81）；精确池不可行；唯一 lead 是 t8 的 MECHANICAL/PIRATE（Q-023）。
2. **聚焦复核（第二份，所有者点名少数高影响力种族）**：`focus.py` —— 只检验预注册的 5 个种族（主：UNDEAD、QUILBOAR；次：MECHANICAL、PIRATE、DRAGON），加平衡面板 t5–8、稳健性、功效/等效性。
   - 报告：`docs/research/race-pool-x50-focus-20261020.md`
   - 结论：亡灵/野猪人存在性对 X50 无显著均值差异（+3.5% / +1.4%，q=0.78）；当前数据只能排除 ≥15% 差异；主池不拆。

## 输入与输出

- 输入：`spikes/dummy-ladder/out-adaptive-all/curves.json`（X50，1.88.6 DLL）、`data/standard/turns.jsonl`（种族池/回合/版本）
- 输出（gitignore）：`out/summary.json`、`out/boards.csv`、`out/games.csv`；`out-focus/focus.json`、`out-focus/boards_focus.csv`、`out-focus/games_focus.csv`

## 复跑

```powershell
python spikes\race-x50\analyze.py --permutations 5000 --bootstrap 5000
python spikes\race-x50\focus.py --bootstrap 10000 --permutations 10000
```

口径：只用 `status=interior` 的板、回合 5–12（`focus.py` 另有平衡面板 t5–8）；X50 是固定木桩的绝对刻度；种族池在每局内是常数，且每局恰好 5 个种族。
