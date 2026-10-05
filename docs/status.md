# 项目状态

> 这份文档回答：项目现在在哪一步、下一步做什么、有什么阻塞。每次会话结束时由 agent 更新。

**最后更新：** 2026-10-05
**当前阶段：** P3 — 战力评估引擎（离线）；**P2 已提前退出**；**P3-T0 已完成**；**P3-T1 已完成**（方案 + 校准参数）

## 最近完成

- **P3-T1 校准实验**（2026-10-05）：在 worktree `feat/P3-T1-calibration` 扩展 `spikes/strength-cross/tools/calibrate.py`，复用 `out_both` 跑 E1–E3 + E5。默认参数：`iterations=500`、`panelGames=30`、\(G_\text{min}=6\)、\(w_\text{relax}=0.25\) 且启用 L1、L2 关闭。见 [`facts/strength-calibration.md`](facts/strength-calibration.md)、[`worklog/2026-10-05-p3t1-calibration.md`](worklog/2026-10-05-p3t1-calibration.md)。Q-015 / Q-016 已关闭。
- **P3-T1 方案批准**（2026-10-05）：ADR-0011 accepted；方案 approved。见 [`worklog/2026-10-05-p3t1-design.md`](worklog/2026-10-05-p3t1-design.md)。
- **局面阵容图渲染可行性调研**（2026-10-05）：见 [`facts/hdt-past-opponent-board-render.md`](facts/hdt-past-opponent-board-render.md)。
- **P3-T0 核心假设早期验证**（2026-10-05）：见 [`facts/strength-cross-p3t0.md`](facts/strength-cross-p3t0.md)。
- **P2 提前退出**（2026-10-05）：配对 7 局 ready 95.1%、对照/重放 78/78。
- **分支合并入 `main`**（2026-10-05）：`feat/P2-T2` → `feat/P2-T3` → `feat/P3-T0`；本地 `main` 相对 `origin/main` ahead（未 push）。

## 进行中

- **P3-T6 局面阵容图渲染**（方案 approved）：[`design/P3-board-render.md`](design/P3-board-render.md) + [ADR-0012](decisions/0012-board-render-side-unit.md)。另一会话在 `feat/P3-T6-board-render`；与 P3-T1 互不依赖。

## 下一步（按优先级）

1. **agent：P3-T2** — `tools/ReplaySim` 迁移；`tools/strength/` 入池 / 面板 / 缓存 / 增量批跑（默认参数用校准表）。
2. **agent：P3-T3** — 循环赛 \(S/Q\)、聚类 bootstrap、放宽阶梯、`strength.jsonl`；复核退出标准第 1 条（校准中聚类宽中位≈36 点，正式实现需再核）。
3. **agent：P3-T6**（可并行）— 按 `design/P3-board-render.md` §7。
4. **所有者（可选）：** 继续团子版 + 0.2.0 采集；`git push`；审阅校准事实文档。

## 待决事项默认值（所有者未否决即按此执行）

| 事项 | 默认值 |
| --- | --- |
| Q-008 对局频率 | 按每周约 15–20 局规划。P3-T0/T1：同回合池在约 20+ 局可用；\(G_\text{min}=6\)；只用自己的数据 |
| Q-009 耗时标准 | **已关闭**：赛后每局 ≤10 分钟 |
| Q-005 CI 与托管 | 暂不做 CI，只在本机构建 |
| Q-015 迭代次数 | **已关闭**：默认 **500**（`facts/strength-calibration.md`） |
| Q-016 跨版本 L2 | **已关闭**：默认 **关闭**（\|ΔQ\| p95≈13.6 >5） |
| 个人采集环境 | **团子版 + 对战记录对照**（ADR-0008） |
| ADR-0004 / ADR-0010 / ADR-0011 / ADR-0012 | **已接受** |
| ADR-0003 | P3-T0 **不推翻**；有效性主验证在 P3-T4 |
| P3 退出标准 | **已确认**（见 `roadmap.md`）；聚类宽在校准样本上偏宽，P3-T3 再核 |
| P2 退出样本数 | **已关闭**（7 局提前退出） |

## 阻塞 / 需要所有者决定

- 无。
