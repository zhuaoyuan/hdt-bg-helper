# 2026-10-05 P3-T3 分位与不确定度

## 目标

按 `docs/process/prompts/p3-t3-percentile.md`：实现留一局循环赛 \(S/Q\)、放宽阶梯、聚类 bootstrap、`strength.jsonl`，并跑出 P3 退出标准第 1 条数字。

## 做了什么

- 分支 `feat/P3-T3-strength-percentile`。
- 新增 `tools/strength/percentile.py`、`engine.py`；CLI：`percentile`、`exit-width`；合成矩阵单测 4 项（合计 14）。
- L0 回填 1.85 回合 1–12（约 3.3 万对，墙钟约 12 min）；L1 交叉对仅在薄桶触发（本批 t≤12 全跳过）。
- 生成 `data/strength/1.85.0.0/strength.jsonl`（329 行）与 `exit_width_1.85.json`。

## 发现

- **退出标准第 1 条未达标**：中位宽 **23.53**（要 ≤15）；≤20 占比 **25.2%**（要 ≥80%）。相对校准 ≈36 有改善（30 局、双侧同伴），仍差一截。
- 曾误对所有回合做 L1 并集补对，成本爆炸；改为仅 \(G < G_\text{min}\) 时补。
- `verify-p3t0` 占位哈希污染默认缓存（120 行），已清理并禁止默认写入。

## 留下的东西

- 代码：`tools/strength/{percentile,engine}.py` 及 CLI/测试/README。
- 事实：`docs/facts/strength-percentile-p3t3.md`。
- 本地产物（gitignore）：`strength.jsonl`、`exit_width_1.85.json`、`cache.sqlite`。
- 下一步：P3-T4 有效性；或所有者决定是否攒局 / 改宽度门槛。
