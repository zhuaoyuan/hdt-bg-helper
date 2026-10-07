# 2026-10-07 摆位对战力增量：实现与全量跑

## 目标

按 `design/R-positioning-strength.md` 默认参数落地 spike 并给出结论。

## 做了什么

- 实现 `spikes/positioning/`（重排、批跑、bootstrap/Wilcoxon/FDR、CLI）。
- 单测 9 项通过；T5 冒烟 8 场面 64/64 ok。
- 全量：1.85 T3–T7，308 场面 × 8 策略行；补跑 59956 对全部 ok；墙钟模拟约 17 min。
- 事实：`docs/facts/positioning-strength.md`；关闭 Q-017。

## 发现

- **无一策略×回合**满足 CI 下界 > 0；身材规则均值多为略负。
- **`rev_orig` 显著为负**（各回合 FDR 拒绝）——原摆位好于整板反转，但简单身材排序不能系统性改进。
- `orig` 自洽 \(\Delta S=0\)；`nMissing=0`。

## 留下

- 若继续挖摆位：需关键词邻接 / 局部搜索，而非再扩身材系数表。
- 主线仍：T5 人核、攒配对局重跑 T4。
