# 现版本 X50 时序：我 vs 对手（分回合）

回答一个问题：**现版本（BB `1.88.6.0`，81 局 / 2026-10-07～10-17）里，同回合的 \(X_{50}\) 有没有随时间漂移？**
用木桩梯队 v2 的绝对刻度，两侧都测；展示用 10 局 trailing 均线（log2 域，满 10 个有效板才画）。

方案与口径：`docs/design/R-x50-trend.md`。报告：`docs/research/x50-trend-20261020.md`。

## 输入

| 文件 | 内容 |
| --- | --- |
| `spikes/dummy-ladder/out-adaptive-all/curves.json` | 己方 \(X_{50}\)（v2；`|Player` 板） |
| `spikes/dummy-ladder/out-opp-188/curves.json` | 对手 \(X_{50}\)（v2；`|Opponent` 板，`DummySim --measureSide opponent`，校验见 `spikes/dummy-ladder/verify_side_opp.py`） |
| `data/standard/turns.jsonl` | `bbVersion` 过滤（现版本=1.88.6.0）、名次、生存回合 |
| `data/strength/1.85.0.0/strength.jsonl` | （间接）版本归属，仅用于核对 |

两侧 \(X_{50}\) 的有效口径：`status == "interior"`；主分析回合 5–12（\(X_{50}\) 在 t5 以前不稳，t13 以后样本 <35）。

## 输出（gitignore：`spikes/**/out*/`）

| 文件 | 内容 |
| --- | --- |
| `out/boards.csv` | 每块板一行：gameId、seq、date、turn、side、status、x50、log2x50、ci |
| `out/games.csv` | 每局一行：名次、生存回合、t5–12 的均值 |
| `out/index.csv` | 回合调整后的每局指数（去掉存活导致的回合组成偏差） |
| `out/analysis.json` | 主检验（系数/CI/q/MDE）、分回合趋势、稳健性、均线序列 |
| `out/figs/fig1..4*.png` | 分回合小多图、汇总强度时序、回合剖面、分回合趋势森林图 |

## 复跑

```powershell
# 0) 对手侧 X50（一次性，约 5-10 分钟；见 spikes/dummy-ladder/README.md 的 --side 用法）
python spikes\dummy-ladder\run_adaptive.py --pool 1.88.6.0 --turns 1-17 --side opponent --out spikes\dummy-ladder\out-opp-188

# 1) 数据表
python spikes\x50-trend\build_dataset.py

# 2) 分析 + 图
python spikes\x50-trend\analyze.py
```

## 统计口径（摘要）

- 时间轴：`gameId` 升序（`YYYYMMDD_HHMMSS`），seq=1..81，图上按日期打刻度。
- **主检验**：\(\log_2 X_{50} \sim \text{seq} + \gamma_{\text{turn}}\)，按局聚类 bootstrap（B=2000，整局重采样）给斜率 95% CI；报告每 10 局变化百分比 \(2^{10\beta}-1\)。分别跑「我」「对手」「对局强度（两侧 log 均值）」；三者 BH-FDR。
- **均线**：10 局 trailing，log2 域，满窗口才画；只对 `interior` 板。
- **MDE**：由 bootstrap 斜率 SD 反推 80% 功效的可检测效应，避免把"没检出差"说成"确定没变"。
- 稳健性：前后半段同回合中位数、去掉 t5、按天中位数、存活回合是否随时间漂移。

## 注意

- 这是 spike / 描述性分析：不写回 `strength.jsonl`、不动分位参照池、不做因果解释。
- 对手侧 \(X_{50}\) 依赖 `DummySim --measureSide opponent`；若 `verify_side_opp.py` 的换侧 ground-truth 校验不过，对手曲线不可比，只报告己方。
- 早期回合（t1–t4）大量 `below`（\(X_{50}<1\)），不进入主分析。
