# P3-T0 核心假设早期验证（全交叉模拟）

> 这份文档回答：用个人 `ready` 场面按 ADR-0003 做同回合交叉模拟时，\(S(x)\)/分位是否有区分度、成本是否可接受、bootstrap 稳不稳、相对 HDT 当场胜率有无增量、固定基准集是否够用、对手场面进池是否明显有害。

```text
样本：BB 1.85.0.0 队列，回合 ≤12 的 ready Combat；diag = data/BgHelperDiag + %APPDATA%\...\BgHelperDiag
工具：spikes/strength-cross/ + ReplaySim --batch；iterations=4000，maxDuration=4000
主跑：player_vs_player（候选/参照均为己方 Player，整局留出）5090 对，全部 ok
对照：player_vs_both（参照含 Opponent）10552 对，全部 ok
冒烟：同场 Player+Opponent 拼回，30/30 五率 3σ 通过
最后核实：2026-10-05
证据：spikes/strength-cross/out/、out_both/；docs/design/P3-T0-core-hypothesis.md
```

## 1. 结论摘要

| 问题 | 结论 |
| --- | --- |
| 拼装是否可信 | **是。** 自洽冒烟 30/30 |
| 单局计算成本 | **可接受。** 驻留批跑下每局交叉模拟合计 max ≈44 s（仅 Player 池）/ ≈92 s（参照含对手），≪ 10 分钟 |
| bootstrap 稳定性 | **基本可用。** 同回合 Player 池：分位 95% 宽中位 ≈14 百分位点，84% ≤20；含对手场面后中位 ≈12，89% ≤20 |
| 与当场战果 | **有中等正相关**（Spearman ≈0.45）；胜/平/负平均分位 0.64 / 0.43 / 0.35 |
| 相对 HDT 当场胜率增量 | **对「本场对阵结果」无增量。** HDT 同场五率 Spearman≈0.89、AUC≈0.98；与分位简单混合反而略差。分位回答的是大厅相对战力，不是本场匹配预测 |
| 固定基准场面集 | **弱于全参照池**（Spearman ≈0.26–0.34 vs ≈0.45）；池够时优先全交叉，基准集作样本极少时的退路 |
| 对手场面进池 | **本批未见明显毒化**；稳定性略升，S–战果相关略升。P3-T1 可默认允许，保留可关开关 |
| ADR-0003 | **不触发推翻。** 有区分度与可用成本；「相对 HDT 增量」需改用名次/后续承伤等标签再评（P3-T4） |

## 2. 样本与冒烟

| 项 | player_vs_player | player_vs_both |
| --- | ---: | ---: |
| 局数（BB 1.85） | 23 | 24 |
| 候选场面（Player，≤12） | 251 | 256 |
| 交叉对数 | 5090 | 10552 |
| 模拟成功 | 5090/5090 | 10552/10552 |

自洽冒烟：从同一 `_input` 取出 Player/Opponent 再拼回，与记录 Output 比五率，**30/30** 在 3σ（含地板）内。

## 3. 成本

| 指标 | pvp | pvb |
| --- | ---: | ---: |
| 批处理墙钟 | ≈780 s（≈13 min） | ≈1523 s（≈25 min） |
| 单对 `elapsedMs` p50 / p90 | 147 / 270 | 136 / 259 |
| `hydrateMs` p50 | 1 | 1 |
| 每局合计模拟 ms（max / p50） | 44372 / 29967 | 92030 / 57637 |
| 超过「每局 ≤10 分钟」 | **0** | **0** |

相对 P2-T0「一场一进程」：驻留 `--batch` 把 hydrate/启动开销压到可忽略；交叉规模下必须用批跑。

## 4. 分位稳定性（bootstrap，B=200）

对每个候选：有放回重采样其参照池，重算分位，取 2.5%–97.5% 宽度（百分位点）。

| 指标 | pvp | pvb |
| --- | ---: | ---: |
| 中位宽度 | 13.6 | 11.8 |
| p90 宽度 | 23.8 | 21.4 |
| 宽度 ≤20 的比例 | 84% | 89% |

同回合桶在本批已有约 11–23 个参照（仅 Player）时，多数分位已接近 P3 退出占位（≤20）；再加对手场面主要是收窄尾巴。

## 5. 与战果 / 承伤 / 名次

**当场战果编码：** 胜=1、平=0.5、负=0。

| 指标 | pvp |
| --- | ---: |
| Spearman(分位, 战果) | 0.45 |
| Spearman(S, 战果) | 0.45 |
| 胜 / 平 / 负 平均分位 | 0.64 / 0.43 / 0.35 |
| Spearman(HDT 当场得分, 战果) | 0.89 |
| AUC(分位→是否胜) | 0.76 |
| AUC(HDT→是否胜) | 0.98 |
| AUC(0.5 分位+0.5 HDT) − AUC(HDT) | **−0.032** |

承伤：`damage` 字段在胜/负场均可非零（更像本场战斗伤害幅度，非纯承伤）；与分位 Spearman≈0.05，负场子集≈0.02——**本批看不到有用关系**。

名次：仅 7 局团子配对有 `placement`；回合级分位与名次 Spearman≈0；局均分位样本过小，**不作结论**。P3-T4 需更多配对局。

## 6. 固定基准集对照

从场面池抽固定 K=20 为基准，\(S_{\mathrm{base}}\)=对其平均得分：

| 模式 | Spearman(S_base, 战果) | Spearman(S_pool, 战果) |
| --- | ---: | ---: |
| pvp | ≈0.26–0.34（随抽样） | 0.45 |
| pvb | 0.42 | 0.48 |

全参照池一致优于固定基准；基准集适合「桶内 N 极小」时的降级指标，不是主路径。

## 7. 对手场面（Q-007 / Q-008）

`player_vs_both` 相对 `player_vs_player`：

- 参照变多 → bootstrap 更窄；
- S–战果相关略升（0.45→0.48）；
- 对「本场 HDT 增量」仍为负。

**[推断]** 对手侧可见性缺口在本批未表现为系统性污染；仍建议 P3-T1 保留「仅己方参照」开关以便回归。

## 8. 对 P3-T1 的约束

1. **默认分桶：** 同 BB 版本 + 同回合；N 不足时优先加对手场面，再考虑 turn±1；不要按种族/畸变硬拆桶（与 Q-008 一致）。
2. **UI/语义：** 战力分位与 HDT 当场胜率并列；不要声称分位能替代本场匹配预测。
3. **有效性标签：** P3-T4 主看名次、后续存活/承伤、跨局泛化；「相对 HDT 的本场增量」不是推翻条件。
4. **工程：** 批量必须驻留进程（或等价批 API）；按局面哈希缓存交叉结果（P3-T2）。
5. **退路：** 参照 <≈8 时显示不稳定，可降级为固定基准集并标注。
6. **ADR-0003：** 本任务不推翻；若 P3-T4 在名次/后续指标上仍无区分度再议。

## 9. 复现

```powershell
& "C:\Program Files\dotnet\dotnet.exe" build spikes\replay-harness\ReplaySim -c Release -p:HdtDir="$env:LOCALAPPDATA\HearthstoneDeckTracker\app-1.58.6" -o spikes\replay-harness\ReplaySim\bin\run
python -m tools.standard_layer --out data\standard
python spikes\strength-cross\tools\cross_eval.py --smoke --out spikes\strength-cross\out
python spikes\strength-cross\tools\cross_eval.py --run --mode player_vs_player --out spikes\strength-cross\out
python spikes\strength-cross\tools\cross_eval.py --run --mode player_vs_both --out spikes\strength-cross\out_both
```
