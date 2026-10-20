# X50 时序：我 vs 对手（分回合，可并池）

回答一个问题：**同回合的 \(X_{50}\) 有没有随时间漂移？** 用木桩梯队 v2 的绝对刻度，两侧都测；展示用 10 局 trailing 均线（log2 域，满 10 个有效板才画）。

两套口径并存：

| 数据集 | 范围 | 局数 / 窗口 | 用途 |
| --- | --- | ---: | --- |
| `out/` | 现版本 BB `1.88.6.0` | 81 局 / 10 天（10-07～10-17） | 主报告 §0–§9 |
| `out-pool/` | 模拟池 `1.85.0.0`（1.85.0.0 + 1.88.6.0） | **112 局 / 16 天**（10-02～10-17） | 报告 §10 扩展复核；含版本台阶/交互检验 |

方案与口径：`docs/design/R-x50-trend.md`。报告：`docs/research/x50-trend-20261020.md`。

## 输入

| 文件 | 内容 |
| --- | --- |
| `spikes/dummy-ladder/out-adaptive-all/curves.json` | 己方 \(X_{50}\)（v2；`|Player` 板；含 1.85 与 1.88.6 两版） |
| `spikes/dummy-ladder/out-opp-188/curves.json` | 对手 \(X_{50}\)，仅 1.88.6 的 81 局（`DummySim --measureSide opponent`） |
| `spikes/dummy-ladder/out-opp-pool/curves.json` | 对手 \(X_{50}\)，整个模拟池 112 局（1.85 348 板 + 1.88.6 937 板） |
| `data/standard/turns.jsonl` | `bbVersion` 过滤/版本归属、名次、生存回合 |
| `data/strength/1.85.0.0/strength.jsonl` | （间接）版本归属，仅用于核对 |

两侧 \(X_{50}\) 的有效口径：`status == "interior"`；主分析回合 5–12（\(X_{50}\) 在 t5 以前不稳，t13 以后样本 <35）。

## 输出（gitignore：`spikes/**/out*/`）

| 文件 | 内容 |
| --- | --- |
| `out*/boards.csv` | 每块板一行：gameId、version、seq、date、turn、side、status、x50、log2x50、ci |
| `out*/games.csv` | 每局一行：version、名次、生存回合、t5–12 的均值 |
| `out*/index.csv` | 回合调整后的每局指数（去掉存活导致的回合组成偏差） |
| `out*/analysis.json` | 主检验（系数/CI/q/MDE）、分回合趋势、稳健性、均线序列；多版本时含 `extended`（版本台阶/交互/版本内趋势） |
| `out*/figs/fig1..4*.png` | 分回合小多图、汇总强度时序、回合剖面、分回合趋势森林图（点线=版本切换） |

## 复跑

```powershell
# 0) 对手侧 X50（一次性；见 spikes/dummy-ladder/README.md 的 --side 用法）
python spikes\dummy-ladder\run_adaptive.py --pool 1.88.6.0 --turns 1-17 --side opponent --out spikes/dummy-ladder\out-opp-188
python spikes\dummy-ladder\run_adaptive.py --pool 1.85.0.0 --turns 1-17 --side opponent --out spikes\dummy-ladder\out-opp-pool   # 扩展用，约 5 分钟

# 1) 现版本 81 局
python spikes\x50-trend\build_dataset.py
python spikes\x50-trend\analyze.py

# 2) 模拟池 112 局（扩展复核）
python spikes\x50-trend\build_dataset.py --pool 1.85.0.0 --opp-curves spikes/dummy-ladder\out-opp-pool\curves.json --out spikes\x50-trend\out-pool
python spikes\x50-trend\analyze.py --out spikes\x50-trend\out-pool

# 3) 独立复算（不同数值路径 + 不同 bootstrap 种子；可加 --out）
python spikes\x50-trend\verify.py
python spikes\x50-trend\verify.py --out spikes\x50-trend\out-pool
```

## 统计口径（摘要）

- 时间轴：`gameId` 升序（`YYYYMMDD_HHMMSS`），seq=1..N，图上按日期打刻度。
- **主检验**：\(\log_2 X_{50} \sim \text{seq} + \gamma_{\text{turn}}\)，按局聚类 bootstrap（B=2000，整局重采样）给斜率 95% CI；报告每 10 局变化百分比 \(2^{10\beta}-1\)、累计漂移 \(2^{(N-1)\beta}-1\)、80% 功效 MDE。分别跑「我」「对手」「对局强度（两侧 log 均值）」及相对难度；BH-FDR。
- **多版本**：另加 `y ~ seq + version + seq×version + 回合FE`（版本虚拟变量=较新版本，基准=最早版本），给出版本层差、版本×时间斜率差、版本内趋势；版本虚拟变量与日历时间共线，解读只能到"有没有台阶"。
- **均线**：10 局 trailing，log2 域，满窗口才画；只对 `interior` 板。
- 稳健性：前后半段（回合调整指数的中位数，按局数对半分）、t6–12、trim 不可靠板（CI 缺失或宽 >1 log2）、局级回合调整指数趋势、按天中位数 Kendall τ、存活/回合组成漂移。

## 注意

- 这是 spike / 描述性分析：不写回 `strength.jsonl`、不动分位参照池、不做因果解释。
- 对手侧 \(X_{50}\) 依赖 `DummySim --measureSide opponent`；换侧 ground truth 校验见 `spikes/dummy-ladder/verify_side_opp.py`。
- 早期回合（t1–t4）大量 `below`（\(X_{50}<1\)），不进入主分析。
- 1.85 局的水合告警约 0.03/行（96/2784），1.88.6 为 0；版本台阶检验吸收系统性差异。
