# 2026-10-05 — P3-T1 校准实验

## 做了什么

- 因主工作区在 `feat/P3-T6-board-render` 有未提交改动，用 git worktree 隔离：`C:\projects\github\hdt-bg-helper-p3t1`，分支 `feat/P3-T1-calibration`（自 `main`）。
- 新增 `spikes/strength-cross/tools/calibrate.py`：E1 迭代扫档、E2 面板 K、E3 \(G_\text{min}\)/L1/\(w_\text{relax}\)、E5 跨版本；复用 `out_both` jobs + ReplaySim `--batch`。
- 跑完 E1–E3 与 E5；结果在 `spikes/strength-cross/out_calibrate/`（gitignore）。
- 写入 `docs/facts/strength-calibration.md`；填方案 §3.9；关闭 Q-015 / Q-016；更新 status / roadmap / README。

## 发现

- **iterations=500** 为最小通过档；250 的 \|ΔQ\| p95≈4.5 未过。
- **K=30**（本批 24 局 ≡ 全面板）；K=20 p95≈5 刚未过。
- **\(G_\text{min}=6\)**；L1 启用，**\(w_\text{relax}=0.25\)**（略优于 L0）。
- **L2 关闭**：跨 1.81→1.85 分位 \|ΔQ\| p95≈13.6。
- 聚类 bootstrap 中位宽本批≈36 点（分位离散主导），与 P3-T0 场面重采样 12–14 点不可直接比；P3 退出标准第 1 条留给 P3-T3 正式实现再核。
- 未重刷 out_both 到最新 25–27 局：固定对集足够判别档位。

## 留下什么

- 下一步 P3-T2（`tools/strength` + ReplaySim 迁移），默认参数用校准表。
- worktree 分支待合并回 `main`（勿与 P3-T6 工作区混提交）。
