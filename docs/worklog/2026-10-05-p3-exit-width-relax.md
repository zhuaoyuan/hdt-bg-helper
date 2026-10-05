# 2026-10-05 放宽 P3 退出宽度门槛（ADR-0014）

## 目标

所有者拍板放宽 P3 退出标准第 1 条的聚类 bootstrap 宽度门槛，并落地代码默认值与文档。

## 做了什么

- 新增 [ADR-0014](../decisions/0014-relax-p3-exit-width.md)（accepted）：中位 ≤25，≥80% ≤30；`wide` 标签仍 >20。
- `tools/strength/config.py` / `engine.exit_width_stats` 使用新默认；复跑 `exit-width`。
- 更新 `roadmap`、`status`、`facts/strength-percentile-p3t3.md`、方案 §5。

## 发现

- T3 实测中位 23.53、p80≈27.8，新门槛下第 1 条可通过；旧 ≤15/≤20 明确废止以免混用。

## 留下的东西

- ADR-0014；配置常量 `EXIT_WIDTH_MEDIAN_LE` / `EXIT_WIDTH_P80_LE`。
