# 项目状态

> 这份文档回答：项目现在在哪一步、下一步做什么、有什么阻塞。每次会话结束时由 agent 更新。

**最后更新：** 2026-10-05
**当前阶段：** P3 — 战力评估引擎（离线）；**P2 已提前退出**（所有者 2026-10-05）；**P3-T0 已完成**；**P3-T1 方案已批准**

## 最近完成

- **P3-T1 方案批准**（2026-10-05）：所有者确认 ADR-0011（留一局循环赛 + 固定参照面板；BB 版本分桶；L2 默认关）与 P3 退出标准修订。方案 `design/P3-T1-strength-engine.md` → approved；ADR-0011 → accepted。见 [`worklog/2026-10-05-p3t1-design.md`](worklog/2026-10-05-p3t1-design.md)。
- **局面阵容图渲染可行性调研**（2026-10-05）：HDT 悬停上次对手阵容链路已定位；诊断 `entities@combat_start`（首选）/ `_input` 场面足以支撑等价阵容条；肖像走 HSJSON；不能直接离线调用 HDT 控件。见 [`facts/hdt-past-opponent-board-render.md`](facts/hdt-past-opponent-board-render.md)。
- **P3-T0 核心假设早期验证**（2026-10-05）：BB 1.85.0 同回合交叉；冒烟 30/30；pvp 5090 / pvb 10552 对全 ok。成本 ≪10 分钟/局；bootstrap 中位宽 ≈12–14 百分位点；分位对当场战果有中等区分，对本场对阵相对 HDT **无增量**；固定基准集弱于全池；对手场面可进池。不推翻 ADR-0003。见 [`facts/strength-cross-p3t0.md`](facts/strength-cross-p3t0.md)、[`worklog/2026-10-05-p3t0-strength-cross.md`](worklog/2026-10-05-p3t0-strength-cross.md)。
- **P2 提前退出**（2026-10-05）：配对 7 局 ready 95.1%、对照/重放 78/78。见 [`worklog/2026-10-05-p2-early-exit.md`](worklog/2026-10-05-p2-early-exit.md)。
- **插件 0.2.0 / P2-T3–T0**（2026-10-05）：诊断转正、标准层、往返验证。
- **分支合并入 `main`**（2026-10-05）：快进合并 `feat/P2-T2` → `feat/P2-T3` → `feat/P3-T0`（`99e2cc7..5ba9d2d`，共 5 个提交）。本地 `main` 相对 `origin/main` ahead 6；未 push。

## 进行中

- **P3-T1 校准实验**（方案已批准，参数未定）：E1–E3（E5 可选）— 迭代次数（Q-015）、面板上限 K、\(G_\text{min}\) 与 turn±1 权重；结果写 `facts/strength-calibration.md`，填方案 §3.9。
- **P3-T6 局面阵容图渲染方案（approved）**（2026-10-05）：[`design/P3-board-render.md`](design/P3-board-render.md) + [ADR-0012](decisions/0012-board-render-side-unit.md)。核心为无状态 `render_side`；本机可读 HDT 贴图；v1 只画随从。未写代码。

## 下一步（按优先级）

1. **agent：P3-T1 校准实验 E1–E3（E5 可选）** — 填 §3.9 默认参数后进 P3-T2。
2. **agent：实现 P3-T6**（方案已批准）— 按 `design/P3-board-render.md` §7 的 T6.1 → T6.4；与 P3-T1 互不依赖，可并行。
3. **所有者（可选）：** 继续团子版 + 0.2.0 采集（名次标签供 P3-T4）；`git push` 发布 `main`。

## 待决事项默认值（所有者未否决即按此执行）

| 事项 | 默认值 |
| --- | --- |
| Q-008 对局频率 | 按每周约 15–20 局规划。P3-T0 显示 ~23 局同回合己方池已基本可用；只用自己的数据 |
| Q-009 耗时标准 | **已关闭**：赛后每局 ≤10 分钟；交叉批跑亦远低于预算 |
| Q-005 CI 与托管 | 暂不做 CI，只在本机构建 |
| 个人采集环境 | **团子版 + 对战记录对照**（ADR-0008） |
| ADR-0004 / ADR-0010 | **已接受** |
| ADR-0011 | **已接受**（留一局循环赛 + 固定参照面板；BB 版本分桶；L2 默认关） |
| ADR-0012 | **已接受**（单侧阵容渲染单元；本机 HDT 贴图；v1 只画随从） |
| ADR-0003 | P3-T0 **不推翻**；有效性主验证在 P3-T4（名次/后续指标） |
| P3 退出标准 | **已确认**（中位宽 ≤15 且 ≥80% ≤20；增量在名次上比 HDT；见 `roadmap.md`） |
| P2 退出样本数 | **已关闭**（7 局提前退出） |

## 阻塞 / 需要所有者决定

- 无。
