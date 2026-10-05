# P3-T3 分位与不确定度验收

> 这份文档回答：正式引擎上留一局循环赛 \(S/Q\)、聚类 bootstrap、放宽标签与 `strength.jsonl` 是否交付；以及 P3 退出标准第 1 条在当前 1.85 队列上的实测数字。

```text
样本：BB 1.85.0.0；回合 ≤12 的己方 ready 场面 329 个；队列 30 局
工具：python -m tools.strength percentile / exit-width；缓存 data/strength/cache.sqlite
参数：iterations=500，K=30，G_min=6，L1 启用但本批 t≤12 均 L0，L2 关，B=1000，参照含对手
最后核实：2026-10-05
证据：data/strength/1.85.0.0/strength.jsonl；data/strength/exit_width_1.85.json（本地 gitignore）
```

## 1. 交付物

| 项 | 结果 |
| --- | --- |
| 合成矩阵单测 | 通过（排名单调、CI 含点估计、`insufficient` / `L1:turn±1` 标签） |
| `strength.jsonl` | 329 行 Player；每行有 `level`；本批全为 `L0`；`wide` 246 行 |
| 放宽标注 | 本批未触发 L1/L2；实现按 §3.3 逐级尝试；L1 仅在 leave-one-game \(G < G_\text{min}\) 时补交叉回合对 |
| `--player-only` | 可用；t5 烟测同伴数 ≈29（仅 Player），对照双侧 ≈56 |
| `exit-width` 可复跑 | `python -m tools.strength exit-width --bb-version 1.85.0.0` |

## 2. 退出标准第 1 条（必须写明数字）

对回合 ≤12、有分位与宽度的己方场面：

| 指标 | 实测 | 门槛 | 通过 |
| --- | ---: | ---: | :---: |
| 队列局数 | 30 | ≥20 | 是 |
| 聚类 bootstrap 中位宽（百分位点） | **23.53** | ≤15 | **否** |
| 宽度 ≤20 的占比 | **25.2%** | ≥80% | **否** |
| p80 / p95 宽 | 27.8 / 35.5 | — | — |

**结论：第 1 条未达标。** 相对校准期同批中位宽 ≈36（B=200、同伴仅 Player、约 24 局），正式引擎在 30 局 + 双侧同伴 + B=1000 下收到 ≈23.5，仍明显高于 15。宽度仍由分位离散主导，不是靠提高 `iterations` 能压掉的（与校准结论一致）。

建议：继续攒局扩大同回合同伴集；**不要**为压窄区间擅自提高 iterations / 放宽 \(G_\text{min}\) / 打开 L2。是否改退出门槛由所有者决定。

## 3. 实现要点

- 分位：ADR-0011 留一局循环赛；同伴 = \(R\) 内全部场面（含非幽灵 Opponent）；权重同回合 1、L1 放宽 \(w=0.25\)。
- CI：按局聚类 bootstrap + MC 噪声；默认 B=1000。
- 消费 T2 缓存；缺对走 `ReplaySim --batch` 补齐。
- 坑：`verify-p3t0` 曾把 `rowBoardHash=verify` 写入默认缓存，污染哈希索引；已删 120 行并回补；CLI 默认拒绝往默认缓存写 verify 占位哈希。

## 4. 复跑

```powershell
python -m unittest discover -s tools/strength
python -m tools.strength percentile --bb-version 1.85.0.0 --turns 1-12 --stats-out data/strength/exit_width_1.85.json
python -m tools.strength exit-width --bb-version 1.85.0.0
```
