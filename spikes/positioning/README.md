# Spike：摆位策略对战力 \(S\) 的增量

独立于主线（见 [`docs/design/R-positioning-strength.md`](../../docs/design/R-positioning-strength.md)）。

在 BB 同版本、同回合对手池上，按身材规则重排候选 `Side.items`，相对原摆位算 \(\Delta S\)，并做局聚类 CI / Wilcoxon / BH-FDR。

## 命令

```powershell
cd C:\projects\github\hdt-bg-helper

# 单测
python -m unittest discover -s spikes/positioning

# 冒烟（小池）
python -m spikes.positioning run --bb-version 1.85.0.0 --turns 5 --strategies orig,atk_desc --limit-boards 8

# 全量（默认策略 × T3–T7；数小时）
python -m spikes.positioning run --bb-version 1.85.0.0 --turns 3-7

# 看表
python -m spikes.positioning report --summary data/positioning/1.85.0.0/summary.json
```

默认复用 `data/strength/cache.sqlite`（pair 键含完整 Input，重排后自动 miss）。

## 输出

- `data/positioning/<bb>/scores.jsonl` — 每场面×策略一行
- `data/positioning/<bb>/summary.json` — strategy×turn 汇总
