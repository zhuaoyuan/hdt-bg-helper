# T3/T4 抽样全排列：头部站位共性

> 这份文档回答：在随从较少的 T3/T4 上，对低/中/高 \(S_{\mathrm{orig}}\) 分层抽样场面做全排列后，得分前 20% 的站位相对全体/底部有何可复述共性。

```text
样本：BB 1.85.0.0；T3–T4；每回合三分位各抽 2 场面（共 12）；n∈[2,5]
工具：spikes/positioning enumerate；ReplaySim；iterations=500
对手池：同回合全体场面；剔同一 boardId
头部：同场面按 S 降序前 ⌈0.2·n!⌉（并列扩边）
种子：enumerate-2026-10-07；pair 硬顶 1.5e5（本批未触顶）
墙钟：全进程约 120 s；实际新跑 pair 约 3136（余量 cap≈1.47e5）
最后核实：2026-10-07
证据：data/positioning/1.85.0.0/enumerate/；design/R-positioning-enumerate.md
```

## 1. 结论摘要

| 问题 | 结论 |
| --- | --- |
| 原序相对最优差多少？ | **很小。** 12 场面平均 \(\overline{\Delta}_{\mathrm{best}}=S_{\mathrm{best}}-S_{\mathrm{orig}}\approx +0.005\)；5/12 场面原序已是最优 |
| 原序在全排列中的位置？ | 平均 `origPercentile`≈**0.27**（0=最优）；多数落在较好半区，但有个别很差（如 T4 mid n=4：rank 21/24，pct≈0.87） |
| 头部 20% 有无稳定共性？ | **有描述性信号（样本小）。** ≥2/3 场面上，头部相对底部更：**身材偏左**（攻/血 Spearman、最强在左半）、**更接近原序**（Kendall↑、邻交换距离↓）、**复生偏右**（仅 2 场面有复生信号） |
| 嘲讽靠左？ | **不支持为稳共性。** 仅 3 场面含嘲讽；头部相对底部反而略少「嘲讽最左」、嘲讽均下标略偏右 |
| 是否可产品化固定口诀？ | **仍不建议。** 增益天花板约 0.005；与 Q-017/Q-018 一致——固定规则难系统性抬 \(S\)；共性多为「别离原序太远 + 略偏强左」 |

## 2. 抽样与成本

| turn | 池 | 合格 \(n\in[2,5]\) | 抽样 | pairsEst | 截断 |
| ---: | ---: | ---: | ---: | ---: | --- |
| 3 | 60 | 51 | 6（低/中/高×2） | 2714 | 无 |
| 4 | 62 | 58 | 6 | 4148 | 无 |
| **合计** | — | — | **12** | **6862** | **无** |

- 排列行：`nPermRows=114`；头部行：`nTopRows=30`
- 模拟：各抽样场面缺对均 ok；`truncatedBoards=[]`

## 3. 各抽样场面（最优 vs 原序）

\(\Delta_{\mathrm{best}}=S_{\mathrm{best}}-S_{\mathrm{orig}}\)；`origPct`：0=最优，1=最差。

| turn | 层 | n | \(\Delta_{\mathrm{best}}\) | origRank | origPct |
| ---: | --- | ---: | ---: | ---: | ---: |
| 3 | low | 3 | 0 | 1 | 0.00 |
| 3 | low | 3 | +0.009 | 2 | 0.20 |
| 3 | mid | 3 | +0.009 | 2 | 0.20 |
| 3 | mid | 2 | +0.009 | 2 | 1.00 |
| 3 | high | 4 | +0.006 | 8 | 0.30 |
| 3 | high | 2 | 0 | 1 | 0.00 |
| 4 | low | 3 | +0.006 | 2 | 0.20 |
| 4 | low | 4 | +0.011 | 13 | 0.52 |
| 4 | mid | 3 | 0 | 1 | 0.00 |
| 4 | mid | 4 | +0.014 | 21 | 0.87 |
| 4 | high | 3 | 0 | 1 | 0.00 |
| 4 | high | 2 | 0 | 1 | 0.00 |

最优序 CardID 见 `enumerate/summary.json` → `boardSummaries` / `features.json`。

## 4. 头部 vs 底部：特征差分（跨场面）

指标：每场面算 top20% 与 bottom20% 的特征均值差，再跨场面汇总。  
**agree±**：同号场面 ≥ ⌈2n/3⌉ 且均值同号（方案成功读出阈值）。

| 特征 | n 场面 | mean(top−bottom) | agree |
| --- | ---: | ---: | --- |
| spearmanHpLeft | 12 | **+0.64** | + |
| spearmanAtkLeft | 12 | **+0.47** | + |
| strongestAtkLeftHalf | 12 | +0.30 | + |
| strongestHpLeftHalf | 12 | +0.26 | + |
| kendallVsOrig | 12 | **+0.81** | + |
| adjSwapFromOrig | 12 | **−1.13** | −（头部更少交换） |
| rebornMeanIndex | 2 | +1.20 | +（偏右；样本极少） |
| tauntMeanIndex | 3 | +0.30 | +（偏右；样本极少） |
| tauntLeftmost | 3 | −0.10 | − |
| cleaveAdjTankRate | 0 | — | 本批无裂解 |

**解读：** 高分排列相对低分排列更「强/坦靠左、更贴原序」；嘲讽/裂解本批不足以支撑口诀。这与「全局 `atk_desc` 仍打不过原序」（Q-017）不矛盾：原序往往已接近最优，强行全局排序会破坏其它结构。

## 5. 验收对照

| # | 项 | 结果 |
| --- | --- | --- |
| 1 | 单测（分层 / top-k / 特征） | 通过 |
| 2 | dry-run 估 pair | 6862；shortfall 空 |
| 3 | 全量 summary / features | 有；无截断 |
| 4 | 本事实 + Q-019 | 本文件 |

## 6. 复跑

```powershell
python -m unittest discover -s spikes/positioning
python -m spikes.positioning enumerate --dry-run --bb-version 1.85.0.0 --turns 3,4
python -m spikes.positioning enumerate --bb-version 1.85.0.0 --turns 3,4
```

## 7. 局限

- 仅 12 场面、描述统计；特征「agree」非正式显著性检验。
- \(n=2\) 场面排列空间极小，头部/底部对比噪声大。
- 同池 leave-one-board；非本场匹配对手。
- 未做 T5+；未对 \(n\ge6\) 全排列。
