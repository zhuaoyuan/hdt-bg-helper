# P3-T2 批量模拟服务验收

> 这份文档回答：`tools/ReplaySim` + `tools/strength` 的入池 / 面板 / 缓存 / 增量是否按方案跑通，以及与 P3-T0 的对照结果。

```text
样本：BB 1.85.0.0；烟测回合 t1（46 场面 / 23 局）；对照 out_both 抽样 120 对
工具：tools/ReplaySim；python -m tools.strength
最后核实：2026-10-05
证据：data/strength/smoke_t1_run1.json、smoke_t1_run2.json、verify_p3t0.json（本地，gitignore）
```

## 1. 结论

| 检查项 | 结果 |
| --- | --- |
| `tools/ReplaySim` 独立批跑 | 通过（`bin/run/ReplaySim.exe --batch`） |
| 入池 / 面板 / 缓存 / 增量烟测 | 通过（t1 回填 2024 对；增量一局 t1 缓存命中 176/176） |
| 单元测试 | 通过（`python -m unittest discover -s tools/strength`，10 项） |
| 与 P3-T0 `out_both` 3σ | **120/120 = 100%**（iterations=500，stride=40） |
| 第二次回填缓存命中 | **2024/2024 = 100%** |

## 2. 默认参数（沿用校准，未改旋钮）

`iterations=500`、`maxDurationMs=500`、`panelGames=30`、参照含对手场面、L2 关闭。  
`assemblerVersion=1`（拼装逻辑自 `cross_input.make_cross_input` 迁入）。

## 3. 实现要点

- 分桶键 `bbVersion + turn`；面板 = 桶内最早入池 K 局（`gameId` 字典序）。
- 缺失对 = 桶内每场面 × 面板场面，且 **留一局**（同 `gameId` 排除）；双向各自模拟。
- 缓存 `data/strength/cache.sqlite`：`boards` / `pairs`；`pairKey = sha256(bbVersion\|assemblerVersion\|规范化 Input)`；次数可合并补跑。
- BB 实际 `simulationCount` 常略低于请求（如 498/500）；`sims_sufficient` 允许 2% 或 2 次绝对短缺，避免假未命中。

## 4. 未做（P3-T3）

循环赛 \(S/Q\)、聚类 bootstrap、放宽阶梯标签、`strength.jsonl`、退出标准第 1 条统计。
