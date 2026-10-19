# 方案：木桩梯队 v2 —— 模型化估计 + 两阶段/自适应采集

- **状态：** implemented + verified（2026-10-19 跑通自测、v1 曲线重打分、全量 329 板自适应、战果对比；数字见 [dummy-ladder-v2-20261019.md](../facts/dummy-ladder-v2-20261019.md)）
- **任务：** 主线外。不替换 ADR-0003 的历史分位，不改 `strength.jsonl`。
- **作者 / 日期：** agent / 2026-10-19
- **相关：** [R-dummy-ladder.md](R-dummy-ladder.md)（v1）、[dummy-ladder-20261018.md](../facts/dummy-ladder-20261018.md)（v1 结果）、Q-021

## 1. 目标与非目标

**目标（在 v1 的「7 个相同木桩」设定内）：**

1. 把 50% 点从「相邻两档线性插值」换成**全部档位的加权 logistic 位置**，并给出 95% 区间；
2. 把采集从「固定粗档 + 固定 7 点加密」换成**粗档 + 自适应 4 + 2 点**，在同样或更好的精度下降低每板模拟次数；
3. 保留 v1 的插值估计作为对照，保证可回退、可比较。

**非目标（明确不做）：**

- **不做多木桩族**（方阵/宽/高/嘲讽…）。所有者判断：这会引入太强的先验假设，收益不值得。
- 不改木桩数量、形状、卡（仍是 7 个 `CFM_315t` 方阵）。
- 不改主线 `strength.jsonl`；本方案只影响旁路读数。
- 不解决跨 DLL/补丁稳定性（单独实验，见 v1 文档 §6）。

## 2. 估计量

对一块场面的已采样档位 \(L_i\)：

- 每档得分 \(s_i=P(\text{win})+0.5P(\text{tie})\)，每档 `iterations` 次模拟；
- 拟合 \(s(L)=1/(1+\exp((\log_2 L-a)/b))\)，\(b>0\)，用 **quasi-binomial logistic IRLS**：每档视为 \(n\) 局、得分 \(s\) 为分数响应（平局记 0.5），工作权重 \(n\,p(1-p)\)；饱和档（\(s\approx0/1\)）信息量自然趋于 0，不需要方差下限（避免尾部被人为放大）。
- 主估计 \(X_{50}=2^a\)；
- 区间：\(\mathrm{Cov}=(J^\top WJ)^{-1}\)，\(W=n\,p(1-p)\)，\(a\pm1.96\sqrt{\mathrm{Cov}_{aa}}\)，再变换回 \(L\)；
- 对照：v1 两档插值 \(X_{50}^{\text{interp}}\)；非参数单调拟合（PAVA）的 \(X_{50}^{\text{iso}}\) 只作形状诊断，不作主估计。

注意：这里的 logistic 只是**光滑单调曲线**，不是胜/平/负的概率模型；区间是渐近近似，且条件于已实现的设计（见 §6）。

## 3. 采集方案

- **第 0 轮（粗档）**：默认 \(1,4,16,\dots,16384\)（公比 4，8 档）；`--coarse ratio2` 可回到 v1 的 \(1..8192\)（14 档）。若最高档仍 \(s\ge0.5\)，后续轮按 ×2、×4 扩到 \(2^{20}\)；若最低档 \(s<0.5\) 记 `below`。
- **第 1 轮（自适应）**：对每块板，在已观测的 50% 区间内取 2 个几何点（区间中点、以及中点到低端的 1/4 点），再加当前拟合的 2 个 logistic 目标点（\(s=0.25,0.75\)），共 ≤4。
- **第 2 轮（自适应）**：在更新后的拟合上取 \(s=0.4,0.6\) 两点，共 ≤2。
- 默认**固定跑满 2 个自适应轮**，不按 CI 提前停止，避免 optional-stopping 偏差；`--extra-rounds` 可改。
- 成本：公比 4 时约 **8+4+2 ≈ 14 次/板**（v1 约 21 次）；公比 2 时约 20 次/板。

## 4. 与 v1 的关系

- v1 的脚本与输出保持不变（`out/`、`out-wide/`）；v2 写到单独的 `out-adaptive/`。
- `model_estimate.py --curves <v1 curves.json>` **不重跑模拟**，只用 v1 的 `levels/scores` 重新估一遍（把平局信息当 0 处理，区间略保守），用来先看「换估计量」本身的影响。
- `compare_estimators.py` 把 v2 与 v1 按 `boardId` 对齐，报 Spearman、\(\lvert\log_2\text{ratio}\rvert\)、CI 宽度、每板模拟次数、按回合中位数。

## 5. 预注册的验收/检查

1. **合成自测**（`model_estimate.py --selftest`）：已知 \(a,b\) 的合成曲线恢复误差 \(|\Delta a|<0.15\)、\(|\Delta b|/b<0.30\)；CI 覆盖率 ≥85%；与插值在密集曲线上的比值 <1.25；自适应选点数量/范围正确。
2. **不重跑的估计量对比**：v1 `out-wide` 的 329 板上，模型估计与插值估计的 Spearman 应 ≥0.98（预期接近 1），中位 \(\lvert\log_2\text{ratio}\rvert\le0.05\)（约 3.5%）。
3. **自适应 vs v1**：同 329 板上 Spearman ≥0.98；中位 CI 宽度 ≤0.20 log2（约 ×1.15）；中位模拟次数（公比 4）≤16；`interior` 比例不低于 v1（v1：329/329）。
4. **有效性（下一批，不在本批）**：与实际战果的 AUC 非劣于 v1（ΔAUC 的按局聚类 bootstrap CI 下界 > −0.03）；与下一回合血量/名次的相关度不劣。
5. **成本**：全池 329 板墙钟应低于 v1 的 168 s（同机、同 500 次）。
6. **跨 DLL**：同一批档位、同一批输入，用 1.85.0.0 与 1.88.6.0 重放，Spearman ≥0.99，中位 \(\lvert\log_2\) ratio\(\rvert\) ≤0.05。
7. **战果差距的区间**：按局聚类 bootstrap 报告 ΔAUC / Δρ 的 95% CI；不预设“必须更好”，只要求把差距量化。
8. **全回合敏感性**：把回合扩到 1–17，ΔAUC 与 t6/8/10 的差 ≤0.01；t5 以前刻度不稳定必须显式标注（`below` 比例、CI 宽度）。

### 5.1 实测（2026-10-19）

全部通过（详见 `facts/dummy-ladder-v2-20261019.md`）：

- 自测：恢复 \(a\) 误差 0.001、\(b\) 相对误差 2.3%；CI 覆盖 40/40；饱和档额外检查通过。
- 同一批 v1 档位只换估计量：329 板 Spearman **0.9995**，中位 \(\lvert\log_2\) ratio\(\rvert\) **0.0203**（×1.014），中位 CI 宽 **0.1134 log2**（×1.082）。
- 自适应全量：329/329 `interior`；中位 **14 档/板**（v1 21），中位 CI 宽 **0.129 log2**（×1.093），墙钟 **126.8 s**；与 v1 插值 Spearman **0.9992**，中位 ratio ×1.019，成本比 **1.51×**。
- 战果（n=130 决胜）：模型 AUC **0.7606** / ρ 0.4432；v1 插值 **0.7613** / 0.4446；主线分位 **0.8051** / 0.5183。v2 与 v1 在战果上无可分辨差别；主线仍高约 0.044。
- **跨 DLL**：同一批 329 板、同一套 4601 档位，1.85.0.0 vs 1.88.6.0：Spearman **0.9999**，中位 signed ratio **1.000**，中位 \(\lvert\)ratio\(\rvert\) **×1.002**（聚类 bootstrap CI ×1.0015–×1.0024），>10% 仅 1 板；两版均有 0 errors（1.85 侧 7706 条 hydration warnings）。
- **战果的按局聚类 bootstrap**（47 局 / 130 决胜，B=5000）：ΔAUC（模型 − 分位）**−0.0445 [−0.0713, −0.0196]**；Δρ **−0.0751 [−0.12, −0.034]**；ΔAUC（模型 − v1 插值）**−0.0007 [−0.0163, 0.0131]**。即：v2 与 v1 区分度相同，主线分位在实际战果上仍显著更好，差距约 0.04 AUC。
- **全回合敏感性**（t1–t17，1321 板）：1112 interior / 198 below / 11 above；480 决胜（47 局）；ΔAUC **−0.0425 [−0.0663, −0.0197]**，与 t6/8/10 的 −0.0445 几乎相同——**回合选择没有驱动结论**。但 t1–t2 大多 below、t2/t3 的 CI 中位宽 30 log2（退化拟合），**\(X_{50}\) 只适合 t5 以后**；模型可用决胜 420 少于分位的 479，主要就是这批 below 板。


## 6. 风险

- **区间是渐近近似**：IRLS Fisher 信息 + 条件于已实现设计，不覆盖自适应设计带来的额外不确定性；严格做法是整流程 bootstrap（本模块未默认做）。
- **两阶段依赖**：第 1/2 轮选点依赖前一轮拟合；最终区间按「设计已定」解释。默认固定轮数、不按 CI 提前停止。
- **模型错设**：若真实曲线是平台/多级台阶，logistic 位置可能落在平台中间；`x50Isotonic` 仅作诊断。v1 插值在同样情形下也有偏。
- **低档整数分辨率**：1–4 之间没有可用细档，早期回合的 \(X_{50}\) 受整数限制。
- **模拟次数分母**：C# 的 `simulationCount`（≈498）与 500 次迭代不完全一致；权重按 `--iterations`（500）保守处理。
- **执行方式**：验证是在一次性的完全访问 shell 里跑的（普通 `pwsh` 在受限沙箱下 `0xC0000142`）；原始输出留在 `out-adaptive*/` 与 `out-wide/curves-model.json`，按 `.gitignore` 不入库。结论只对本机 1.88.6.0 DLL 与本批 329 板成立。

## 7. 命令

```powershell
# 1) 构建（若尚未构建）
& "C:\Program Files\dotnet\dotnet.exe" build spikes\dummy-ladder\DummySim -c Release -o spikes\dummy-ladder\DummySim\bin\run
# 2) 合成自测（不需要 BB/DLL）
python spikes\dummy-ladder\model_estimate.py --selftest
# 3) 不重跑模拟：用 v1 曲线比较估计量
python spikes\dummy-ladder\model_estimate.py --curves spikes\dummy-ladder\out-wide\curves.json
# 4) 小样本冒烟（先 20 板）
python spikes\dummy-ladder\run_adaptive.py --limit 20 --out spikes\dummy-ladder\out-adaptive-smoke
# 5) 全量
python spikes\dummy-ladder\run_adaptive.py --coarse ratio4
python spikes\dummy-ladder\compare_estimators.py
# 6) 与实际战果对比（需要 data/standard/turns.jsonl）
python spikes\dummy-ladder\score_model_outcomes.py
# 7) 战果差距的按局聚类 bootstrap
python spikes\dummy-ladder\bootstrap_outcomes.py --bootstrap 5000
# 8) 跨 DLL 稳定性（需要本机 1.85.0.0 与 1.88.6.0 两个 BB 目录）
python spikes\dummy-ladder\cross_dll.py --bootstrap 2000
```

## 8. 验收后的去向

- 检查 1–8 已通过：`out-adaptive/curves.json` 可以作为 v2 主读数（带区间）；`facts/dummy-ladder-v2-20261019.md` 已记录。
- **跨 DLL 稳定性支持“绝对值”主张**：1.85.0.0 vs 1.88.6.0 的排序 0.9999、中位差 0.2%。
- **但战果上主线分位仍显著更好**（ΔAUC −0.0445 [−0.0713, −0.0196]）；全回合（t1–t17）重跑给出几乎相同的 −0.0425，说明回合选择不是原因。
- **可用范围**：\(X_{50}\) 只适合 t5 以后；早期回合 `below`/CI 退化，产品/复盘里应显示分位或 HDT 当场胜率，而不是 \(X_{50}\)。
- 下一步：决定是否把 \(X_{50}\) 显示接入复盘/局内（作为第二读数）；跨 patch/规则变化与 1.78.1 仍未测。
