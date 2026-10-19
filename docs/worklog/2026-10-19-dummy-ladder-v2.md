# 2026-10-19 木桩梯队 v2：模型化估计 + 两阶段/自适应采集

## 目标

在 v1「7 个相同木桩」的设定内，把 50% 点从「相邻两档线性插值」升级为「全部档位的 logistic 位置 + 区间」，并把采集从「固定 7 点加密」升级为「粗档 + 自适应 4 + 2 点」。**不做多木桩族**：所有者判断其先验假设太强。

## 做了什么

- 方案：[R-dummy-ladder-v2.md](../design/R-dummy-ladder-v2.md)。
- `spikes/dummy-ladder/model_estimate.py`：
  - 加权 logistic 拟合（\(\log_2 L\) 上的位置 \(a\)、尺度 \(b\)），权重来自每次模拟得分的经验方差；
  - 主估计 \(X_{50}=2^a\)，渐近 95% 区间；
  - 对照：v1 两档插值、PAVA 单调拟合（形状诊断）；
  - 自适应选点（区间内 2 个几何点 + logistic 目标点），纯 stdlib；
  - `--selftest`：合成曲线恢复 / CI 覆盖 / 与插值对比 / 选点合法性（**未执行**）；
  - `--curves`：不重跑模拟，用 v1 `curves.json` 直接重打分。
- `spikes/dummy-ladder/run_adaptive.py`：粗档（默认公比 4，8 档）→ 自适应 4 点 → 自适应 2 点；固定跑满两轮、不按 CI 提前停止；输出 `out-adaptive/curves.json`（含 `x50`、`ci`、`a`、`b`、`x50Interp`、`x50Isotonic`、`sims`、`rounds`）。
- `spikes/dummy-ladder/compare_estimators.py`：v1 插值 vs v2 模型估计（按 boardId 对齐；Spearman、\(\lvert\log_2\) ratio\(\rvert\)、CI 宽度、每板模拟次数、按回合）。
- `.gitignore`：补 `spikes/**/out-*/`（v1 的 `out-wide/` 之前其实没被忽略；本次一并修复）。
- 文档索引与命令：`design/README.md`、`spikes/dummy-ladder/README.md`、`status.md`。

## 关键决定

- **估计量**：logistic 位置为主，插值保留为对照；isotonic 只作形状诊断。理由是前者用全部档、对“跨越的恰好是哪两档”不敏感，并能给区间。
- **采集**：两阶段（粗档 + 固定 4 + 固定 2），不按 CI 提前停止，避免 optional-stopping 偏差；区间解释为“条件于已实现设计”的近似。
- **与 v1 隔离**：v2 输出写到 `out-adaptive/`，v1 的 `out/`、`out-wide/` 及脚本不动，便于 A/B。
- **多木桩族不做**（所有者指示）。

## 验证（2026-10-19）

首次尝试时受限沙箱下 `pwsh` 全部 `0xC0000142`，无法执行；后用**一次性完全访问** shell 跑通全部验证。

**先发现并修掉一个真问题：** 初版估计量用「每次模拟得分的经验方差 + 0.25/n 下限」做加权最小二乘；饱和档（s=0/1）权重被放大到约 500×，拟合被尾部拖着走，区间虚假窄（329 板中位 CI 宽仅 0.0155 log2 ≈ ×1.011）。改成 **quasi-binomial logistic IRLS**（工作权重 \(n\,p(1-p)\)，不需要方差下限）后：点估计几乎不变（中位 ratio 0.0219→0.0203），区间回到可信量级（中位 0.1134 log2 ≈ ×1.082）。自测里另加了“精确 0/1 饱和档”回归检查。

结果（详见 `facts/dummy-ladder-v2-20261019.md`）：

- `--selftest`：PASSED；恢复 \(a\) 误差 0.001、\(b\) 2.3%；CI 覆盖 40/40；密集合成 model/interp 1.028。
- `--curves`（同一批 v1 档位，329 板）：Spearman **0.9995**，中位 \(\lvert\log_2\) ratio\(\rvert\) **0.0203**（×1.014），中位 CI 宽 **0.1134 log2**。
- 20 板冒烟：20/20 `interior`，14 档/板，墙钟 46.4 s（含索引）。
- 全量 329 板：**329/329 `interior`**，中位 **14 档/板**（v1 21），中位 CI 宽 **0.1288 log2**（×1.093），墙钟 **126.8 s**；与 v1 插值 Spearman **0.9992**、中位 ratio **×1.019**、成本比 **1.51×**。
- 分回合中位 \(X_{50}\)：t6 7.78 / t8 23.68 / t10 111.43（v1：7.68 / 24 / 112.41）。
- 实际战果（n=130 决胜）：模型 AUC **0.7606** / ρ 0.4432；v1 插值 **0.7613** / 0.4446；主线分位 **0.8051** / 0.5183。**v2 与 v1 无差别，主线仍高约 0.044。**
- **跨 DLL 稳定性**（同一批 329 板、同一套 4601 档位，1.85.0.0 vs 1.88.6.0）：Spearman **0.9999**；中位 signed ratio **1.000**；中位 \(\lvert\)ratio\(\rvert\) **×1.002**（聚类 bootstrap CI ×1.0015–×1.0024）；>10% 仅 1 板（max ×1.18）；两版 0 errors（1.85 侧 7706 条 hydration warnings）。**“绝对值”跨这两个 BB 版本基本不变。**
- **战果的按局聚类 bootstrap**（47 局 / 130 决胜，B=5000）：ΔAUC（模型 − 主线分位）**−0.0445 [−0.0713, −0.0196]**；Δρ **−0.0751 [−0.12, −0.034]**；ΔAUC（模型 − v1 插值）**−0.0007 [−0.0163, 0.0131]**。即：v2 与 v1 区分度相同；**主线分位在实际战果上显著更好**（差距不大但 CI 不含 0）。
- **全回合敏感性**（`--turns 1-17`，1321 板）：**1112 interior / 198 below / 11 above**；中位 14 档/板；304 s；分回合中位 \(X_{50}\) 从 t3 的 2.0 升到 t15 的 3283。战果：**480 决胜（47 局）**；模型 AUC 0.7664 vs 分位 0.7951；**ΔAUC −0.0425 [−0.0663, −0.0197]**，与 t6/8/10 的 −0.0445 几乎相同——**回合选择没有驱动结论**。但 **t5 以前刻度不稳定**：t1–t2 大多 below，t2/t3 的 CI 中位宽 30 log2（退化拟合），t4 1.88，t5 才回到 0.27。\(X_{50}\) 只适合 t5 以后；模型可用决胜（420）少于分位（479）主要就是这批 below 板。

设计文档 §5 检查 1–8 通过。

## 下一步

1. 跨 patch/规则变化与 1.78.1 仍未测（本次只测了 1.85.0.0 vs 1.88.6.0 两个 DLL 文件版本）。
2. \(X_{50}\) 可用范围限定 t5 以后；产品/复盘若显示，应同时保留分位或 HDT 当场胜率。
3. 若确认采用 v2：把 `out-adaptive/curves.json` 接入评分/复盘管线，作为“带单位的平行读数”（不要替换分位；战果上分位仍更好）。
4. 可选：用实际标签校准“绝对刻度 → 分位”的固定映射（免池方案），再与主线分位比。

## 留下的东西

- 代码：`spikes/dummy-ladder/model_estimate.py`、`run_adaptive.py`、`compare_estimators.py`、`score_model_outcomes.py`、`bootstrap_outcomes.py`、`cross_dll.py`。
- 方案：`docs/design/R-dummy-ladder-v2.md`（implemented + verified）。
- 事实：`docs/facts/dummy-ladder-v2-20261019.md`。
- 本地输出（gitignore）：`spikes/dummy-ladder/out-adaptive/`、`out-adaptive-smoke/`、`out-adaptive-all/`（全回合）、`out-wide/curves-model.json`、`cross-dll/compare.json`。
- 未改 `strength.jsonl`；未并入 `main`。
