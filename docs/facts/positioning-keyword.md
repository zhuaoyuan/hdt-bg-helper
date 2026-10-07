# 关键词 / 邻接 / 有限交换摆位对 \(S\) 的增量

> 这份文档回答：在 Q-017 否定身材全局排序后，关键词钉位、邻接启发与有限局部交换能否抬高同回合池上的 \(S\)。

```text
样本：BB 1.85.0.0；T3–T7；ready 双侧场面 308（与 positioning-strength 同批）
工具：spikes/positioning/ --keyword；ReplaySim batch；iterations=500
对手池：同回合全体场面；评估剔同一 boardId
策略：taunt_pin_hp / cleave_adj_tank / reborn_dr_right / local_swap_b6
local_swap：邻交换爬山 ≤6 步；全局 pair 硬顶 250000（本批未触顶）
显著性：局聚类 bootstrap 95% CI；Wilcoxon；BH-FDR q=0.05
墙钟：进程约 6813 s（~113 min）；runInfo 累计模拟墙钟约 3504 s
最后核实：2026-10-07
证据：data/positioning/1.85.0.0/keyword/summary.json、scores.jsonl；design/R-positioning-keyword.md
```

## 1. 结论摘要

| 问题 | 结论 |
| --- | --- |
| 三条**可解释规则**能否显著抬高 \(S\)？ | **不能。** 无一 strategy×turn 的 CI **下界 > 0** |
| `local_swap_b6`（同池选序）？ | **有 CI+**（T3–T7 共 5 格）；合并 \(\overline{\Delta S}\approx +0.0098\)，提升比例 ≈0.78 |
| 是否可宣称「摆位提示值得产品化」？ | **规则：不值得。** 搜索：仅证明同度量下存在可挖增益；按方案 H3，**不得**因同池爬山 CI+ 直接上产品（乐观偏差） |
| 管线自洽 | `orig` \(\Delta S\equiv 0\)；`nMissing` 合计 0；截断场面 0 |

**含义：** 嘲讽钉位 / 裂解邻接 / 复生偏后等廉价规则，与身材排序一样**挖不到**系统性正 \(\Delta S\)（本批裂解命中极少，`cleave_adj_tank` 近乎恒等）。有预算的邻交换爬山能抬高对大厅池的 \(S\)（约 +0.01），但这是**在评估池上选序**的结果，不直接等于可部署的固定提示。

## 2. 样本量与搜索成本

| turn | 场面池 | 规则缺对 | local_swap pairsPlanned | nImproved | wallSec(swap) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 60 | 118 | 4720 | 28 | 42 |
| 4 | 62 | 793 | 18056 | 39 | 226 |
| 5 | 62 | （规则批内） | 36295 | 54 | 560 |
| 6 | 62 | 2135 | 60817 | 62 | 1196 |
| 7 | 62 | （规则批内） | 63257 | 57 | 1336 |
| **合计** | **308** | — | **~183k**（&lt;250k 硬顶） | — | **~3359** |

跑完后全局 pair 余量约 6.7e4；无 `truncated`。

## 3. 主表（\(\overline{\Delta S}\) 与 CI）

\(\Delta S=S_{\mathrm{strat}}-S_{\mathrm{orig}}\)。**CI+** = bootstrap CI 下界 > 0。

### 3.1 规则策略（无 CI+）

| 策略 | t3 | t4 | t5 | t6 | t7 |
| --- | ---: | ---: | ---: | ---: | ---: |
| taunt_pin_hp | −0.0016 [−0.0038,−0.0001] | +0.0005 [−0.0024,+0.0034] | −0.0010 [−0.0047,+0.0030] | −0.0047 [−0.0110,−0.0001] | −0.0054 [−0.0122,+0.0015] |
| cleave_adj_tank | 0 | 0 | −0.0001 [−0.0004,0] | 0 | −0.0001 [−0.0004,0] |
| reborn_dr_right | −0.0046 [−0.0145,+0.0008] | −0.0030 [−0.0066,−0.0003] | −0.0051 [−0.0096,−0.0014] | −0.0023 [−0.0061,+0.0012] | −0.0044 [−0.0094,−0.0001] |

本批场面：`AdditionalDeathrattles` 命中 0（`reborn_dr_right` 实质≈复生靠右）；cleave 随从极少（`_data.Cleave` / CardID 集一致，全池约 2 个随从实例）。

### 3.2 `local_swap_b6`（全部 CI+；同池乐观）

| turn | \(\overline{\Delta S}\) | CI95 | frac+ | Wilcoxon p | FDR |
| ---: | ---: | --- | ---: | ---: | :---: |
| 3 | +0.0044 | [+0.0019,+0.0079] | 0.47 | 7.5e-9 | 是 |
| 4 | +0.0088 | [+0.0057,+0.0124] | 0.63 | 3.6e-12 | 是 |
| 5 | +0.0115 | [+0.0074,+0.0167] | 0.87 | 1.6e-10 | 是 |
| 6 | +0.0115 | [+0.0088,+0.0144] | 1.00 | 7.6e-12 | 是 |
| 7 | +0.0125 | [+0.0084,+0.0185] | 0.92 | 5.1e-11 | 是 |

### 3.3 全策略合并（T3–T7）

| 策略 | n | \(\overline{\Delta S}\) | frac+ |
| --- | ---: | ---: | ---: |
| taunt_pin_hp | 308 | −0.0025 | 0.11 |
| cleave_adj_tank | 308 | −0.00005 | 0.00 |
| reborn_dr_right | 308 | −0.0039 | 0.06 |
| local_swap_b6 | 308 | **+0.0098** | **0.78** |

规则策略合并后 CI 上界均 &lt; 0.01（且均值≤0），满足方案对规则侧的「不值得做」实用阈值。

## 4. 与 R-positioning / 失败判定对照

| 标准（`R-positioning-keyword.md` §3.4） | 结果 |
| --- | --- |
| 主结论「有帮助」：任一格 CI 下界 > 0 | **仅** `local_swap_b6` 满足 |
| 规则失败 → 不值得做固定提示 | **成立**（三条规则无 CI+，合并上界 &lt; 0.01） |
| 仅搜索 CI+ → 标乐观偏差，不直接产品化 | **适用**；需 H3（搜索子样本 / 评估全池）或其它外推验证后再议 |
| 整表「摆位提示不值得做」硬关 | **不适用**（因搜索有 CI+）；降级为：规则不做；搜索=存在空间 |

## 5. 验收对照

| # | 项 | 结果 |
| --- | --- | --- |
| 1 | 重排单测（含关键词规则） | 通过 |
| 2 | `orig` \(\overline{\Delta S}=0\) | 是（`origMeanAbsMax=0`） |
| 3 | 冒烟 T5 limit=8 规则三策略 | 35/35 ok |
| 4 | 全量 keyword summary | 有；scores 1540 行；`nMissing=0` |
| 5 | 本事实文档 | 本文件 |

## 6. 复跑

```powershell
python -m unittest discover -s spikes/positioning
python -m spikes.positioning run --keyword --bb-version 1.85.0.0 --turns 3-7
python -m spikes.positioning report --summary data/positioning/1.85.0.0/keyword/summary.json
```

## 7. 局限

- `local_swap_b6` 在**同一** leave-one-board 池上选序与打分 → 乐观偏差（方案 H3）。
- 先天亡语未进规则（本批无额外亡语字段命中）；裂解样本极稀。
- \(\Delta S\) 相对同回合大厅池，不是本场匹配或名次。
- 效应量 ~0.01，接近实用阈值；解读宜谨慎。
