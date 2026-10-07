# Spike：摆位策略对战力 \(S\) 的增量

独立于主线（见 [`docs/design/R-positioning-strength.md`](../../docs/design/R-positioning-strength.md)、
[`docs/design/R-positioning-keyword.md`](../../docs/design/R-positioning-keyword.md)）。

在 BB 同版本、同回合对手池上重排候选 `Side.items`，相对原摆位算 \(\Delta S\)，并做局聚类 CI / Wilcoxon / BH-FDR。

## 命令

```powershell
cd C:\projects\github\hdt-bg-helper

# 单测
python -m unittest discover -s spikes/positioning

# 身材策略冒烟（Q-017）
python -m spikes.positioning run --bb-version 1.85.0.0 --turns 5 --strategies orig,atk_desc --limit-boards 8

# 关键词/邻接冒烟（Q-018，不含全量 swap）
python -m spikes.positioning run --keyword --bb-version 1.85.0.0 --turns 5 `
  --strategies orig,taunt_pin_hp,cleave_adj_tank,reborn_dr_right --limit-boards 8

# 关键词全量（规则 + local_swap_b6；swap≤6，pair 硬顶 2.5e5）
python -m spikes.positioning run --keyword --bb-version 1.85.0.0 --turns 3-7

# 看表
python -m spikes.positioning report --summary data/positioning/1.85.0.0/keyword/summary.json
```

默认复用 `data/strength/cache.sqlite`（pair 键含完整 Input，重排后自动 miss）。
`--keyword` 时默认输出到 `data/positioning/<bb>/keyword/`。

## 输出

- `scores.jsonl` — 每场面×策略一行
- `summary.json` — strategy×turn 汇总（含 `searchMeta`）
