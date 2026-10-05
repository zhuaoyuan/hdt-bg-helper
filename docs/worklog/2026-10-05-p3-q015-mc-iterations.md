# 2026-10-05 — P3 增加 Q-015（交叉迭代次数甜区）

## 决定

所有者要求：P3 增加一项调研——每次场面对场面的目标蒙特卡洛迭代次数，降到什么位置仍能保留胜负/\(S\)/分位质量并最大限度省时；作为 P3-T1「抽样与加权」的候选路径之一（与参照场面抽样并列）。

## 落盘

- `roadmap.md` P3-T1 表述补充该候选
- `research/open-questions.md` 新增 **Q-015**（open）
- `facts/strength-cross-p3t0.md` §8 第 7 条约束
- `status.md` 下一步注明 Q-015

## 下一步

写 P3-T1 方案时列入评估矩阵；具体扫档可在设计通过后用 `strength-cross` / `ReplaySim --batch` 复用 P3-T0 对集做对照实验。
