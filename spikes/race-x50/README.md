# 当局种族池 vs 玩家 X50 战力

探索性问题：酒馆战棋大厅的可用种族池（`rules.availableRaces`）与玩家当局的 X50 战力（木桩梯队 v2）是否相关？如果相关，现有按 `(simPool, turn)` 的参照池是否应拆成更公平的子池？

- 分析脚本：`analyze.py`（可复跑）
- 结论/图表：`docs/research/race-pool-x50-20261020.md`
- 输入：`spikes/dummy-ladder/out-adaptive-all/curves.json`（X50，1.88.6 DLL）、`data/standard/turns.jsonl`（种族池/回合/版本）
- 输出（gitignore）：`out/summary.json`、`out/boards.csv`、`out/games.csv`

```powershell
python spikes\race-x50\analyze.py --permutations 5000 --bootstrap 5000
```

口径：只用 `status=interior` 的板、回合 5–12；X50 是固定木桩的绝对刻度；种族池在每局内是常数，且每局恰好 5 个种族。
