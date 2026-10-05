# 2026-10-05 P3-T0 核心假设早期验证

## 目标

按 roadmap P3-T0：用 BB 1.85.0 的 `ready` 双方场面做全交叉模拟，评估 \(S(x)\)/分位的成本、bootstrap 稳定性、与战果相关、相对 HDT 胜率增量、固定基准集，并对照对手场面进池。

## 做了什么

1. 方案 [`design/P3-T0-core-hypothesis.md`](../design/P3-T0-core-hypothesis.md)；分支 `feat/P3-T0-core-hypothesis`。
2. `ReplaySim` 增加 `--batch`（驻留加载 BB，JSONL 批跑）。
3. Spike `spikes/strength-cross/`：拼装交叉 Input、冒烟、批跑、分析。
4. 刷新标准层（含 APPDATA 新局）：55 局 / 640 行。
5. 实测：冒烟 30/30；`player_vs_player` 5090 对；`player_vs_both` 10552 对。
6. 事实 [`facts/strength-cross-p3t0.md`](../facts/strength-cross-p3t0.md)。

## 发现

- 分位对当场战果有中等区分（胜/平/负平均分位 0.64/0.43/0.35），但**不能**在预测本场胜负上超过 HDT 当场五率（预期内：问题不同）。
- 同回合个人池已能使多数分位 bootstrap 宽 ≤20 百分位点；加对手场面更稳。
- 每局交叉成本远低于 Q-009 的 10 分钟预算。
- 固定基准集弱于全池；名次样本（7 局）尚不够做有效性结论。

## 留下的东西

- 代码/工具：`spikes/strength-cross/`、`ReplaySim --batch`
- 本地结果：`spikes/strength-cross/out/`、`out_both/`（gitignore）
- 下一步：P3-T1 设计（参照池放宽、抽样、缓存、CI 宽度目标）；有效性主标签放到 P3-T4
