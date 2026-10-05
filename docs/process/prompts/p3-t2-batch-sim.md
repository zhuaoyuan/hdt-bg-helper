# 提示词：P3-T2 批量模拟服务

> 用途：在新会话中实现战力引擎的入池 / 面板 / 缓存 / 增量批跑。  
> 通用流程另见 [`implement-task.md`](implement-task.md)；本文件是任务专用边界与验收清单。

## 所有者可粘贴的短指令

```text
执行 P3-T2，严格按 docs/process/prompts/p3-t2-batch-sim.md。
方案已批准：docs/design/P3-T1-strength-engine.md；ADR-0011 accepted。
校准默认值见 docs/facts/strength-calibration.md（不要重跑 E1–E5）。
完成后按 session-handoff 更新 status / worklog / roadmap。
不要 push，除非我要求。
```

## 开始前（必读顺序）

1. `AGENTS.md` → `docs/status.md` → `docs/roadmap.md`（P3 段）。
2. **方案（唯一规格）：** [`docs/design/P3-T1-strength-engine.md`](../../design/P3-T1-strength-engine.md) §3.1–3.6、§3.9、§5（P3-T2 行）、§7 第 3 步。状态须为 `approved`。
3. **ADR：** [`0011-strength-pool-round-robin.md`](../../decisions/0011-strength-pool-round-robin.md)（accepted）。
4. **事实：** [`strength-calibration.md`](../../facts/strength-calibration.md)、[`strength-cross-p3t0.md`](../../facts/strength-cross-p3t0.md)；拼装可参考 `spikes/strength-cross/tools/cross_input.py`。
5. **既有代码：** `tools/standard_layer/`（包结构模板）；`spikes/replay-harness/ReplaySim/`（待迁移）；`spikes/strength-cross/`（对照，正式代码不得依赖 spike 运行时）。
6. 从 `main` 建分支：`feat/P3-T2-strength-batch`（或等价短名）。

## 本任务范围（做）

1. **迁移** `ReplaySim`：`spikes/replay-harness/ReplaySim/` → `tools/ReplaySim/`，保持 `--batch` 驻留批跑可用；spike 侧可留薄包装指向新位置或注明已迁移，避免双份逻辑分叉。
2. **新建** `tools/strength/`（Python 包，风格对齐 `tools/standard_layer`）：
   - 从标准层 / diag 入池：`ready`、单人、有 `_input`；`Opponent` 非幽灵（`KelThuzad`）；场面单位 `(gameId, turn, side)`。
   - 分桶：`bbVersion + turn`；面板：每桶最早入池 **K=30 局**（确定性）；满面板后新局只作同伴。
   - 缓存：`data/strength/cache.sqlite`（须 gitignore）；`boards` / `pairs` 表按方案 §3.6；`pairKey` 规范化；**存次数可合并补跑**；`assemblerVersion`。
   - 增量批跑：算缺失对 → 调 `ReplaySim --batch` → 写回 cache；默认 `iterations=500`、`maxDurationMs=500`。
   - CLI：能对指定 BB 版本做「回填」与「增量一局」；诊断数据根目录需同时支持项目 `data/BgHelperDiag` 与 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag`（与 P3-T0 一致）。
3. **单元测试**（`python -m unittest discover -s tools/strength`）：至少覆盖 key 稳定性、补跑合并、留一局排除、幽灵剔除、面板确定性。
4. **对照验收（本机）：** 对与 P3-T0 `out_both` 可比的一批对重跑，与历史结果在 3σ 内比例 ≥99%；**第二次**全量/增量运行缓存命中率 100%。

## 明确不做（留给 P3-T3）

- 循环赛 \(S/Q\)、聚类 bootstrap、放宽阶梯 L0/L1/L2、`strength.jsonl`、退出标准第 1 条统计脚本。
- 重跑校准 E1–E5；改默认旋钮（除非实现发现方案错误——那时停下来写 worklog / 提方案修订，勿擅自改）。
- P3-T4 有效性、P3-T5 UI。
- 启用 L2；利用反对称省半成本。

## 默认参数（冻结，来自校准）

| 参数 | 值 |
| --- | ---: |
| `iterations` | 500 |
| `maxDurationMs` | 500 |
| `panelGames` K | 30 |
| 参照含对手场面 | 是（保留可关开关） |
| L2 | 关（本任务只需在配置里占位即可） |

## 实现约束

- 正式包**禁止** `import` spike；可复制/迁入拼装逻辑并设 `assemblerVersion`。
- 每个方向单独模拟（不反对称省半）。
- 候选外壳规则：用候选方 Input 外壳拼 `s(a,b)`（见方案 §3.1）。
- PowerShell 5.1：不用 `&&`；`dotnet` 用完整路径（见 `AGENTS.md`）。
- `data/` 下原始对局与 `cache.sqlite` 不入库；提交前确认 `.gitignore`。
- 一次可独立验证的改动一个 commit；约定式前缀；**不要 push**。
- 方案未覆盖且会改语义时：**停下**，不要自行扩大范围。

## 验收清单（全部勾上才算完成）

- [ ] `tools/ReplaySim` 可独立批跑
- [ ] `tools/strength` 入池 / 面板 / 缓存 / 增量可跑通 1.85 一小段烟测
- [ ] `python -m unittest discover -s tools/strength` 全过
- [ ] 与 P3-T0 对照 3σ ≥99%；二次运行缓存命中 100%
- [ ] 方案 §7 第 3 步与 roadmap P3-T2 可打勾的证据已写入 worklog
- [ ] `docs/status.md` + 当日 worklog + 必要 facts 已更新

## 收尾

按 [`session-handoff.md`](session-handoff.md)。给所有者的总结须包含：分支名、如何复跑验收命令、已知限制（例如尚未算分位）。
