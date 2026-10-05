# 提示词：P3-T3 分位计算与不确定度

> 用途：在 **P3-T2 已交付** 的缓存/批跑之上，实现循环赛分位、聚类 bootstrap、放宽阶梯与退出统计。  
> 通用流程另见 [`implement-task.md`](implement-task.md)。

## 所有者可粘贴的短指令

```text
执行 P3-T3，严格按 docs/process/prompts/p3-t3-percentile.md。
前置：P3-T2 已合入（tools/ReplaySim + tools/strength 缓存/批跑可用）。
规格：docs/design/P3-T1-strength-engine.md §3.2–3.4、§3.7、§3.9–3.10、§5；ADR-0011。
校准默认值见 docs/facts/strength-calibration.md。重点复核 P3 退出标准第 1 条（校准样本聚类宽中位曾≈36，勿用改 iterations 来“修”宽度）。
完成后按 session-handoff 更新 status / worklog / roadmap；如实报告宽度是否达标。
不要 push，除非我要求。
```

## 开始前（必读顺序）

1. `AGENTS.md` → `docs/status.md` → `docs/roadmap.md`（P3 退出标准三条）。
2. 确认 **P3-T2 完成**（roadmap 已勾或 `tools/strength` 缓存/批跑可复现）。未完成则停，先做/续做 P3-T2。
3. **方案：** [`P3-T1-strength-engine.md`](../../design/P3-T1-strength-engine.md) §3.2–3.4、§3.7、§3.9–3.10、§5（P3-T3 行）、§7 第 4 步。
4. **ADR-0011**；事实 [`strength-calibration.md`](../../facts/strength-calibration.md)、[`strength-cross-p3t0.md`](../../facts/strength-cross-p3t0.md)。
5. 从 `main`（或含 T2 的已合并点）建分支：`feat/P3-T3-strength-percentile`。

## 本任务范围（做）

1. **留一局循环赛 \(S/Q\)**（方案 §3.2 / ADR-0011）：
   - 候选仅 **`side=Player`** 的 `ready` 场面；`Opponent` 只作参照/同伴。
   - 参照群体 = 桶内除候选所在局以外的场面（默认含非幽灵对手）；整局留出。
   - 对手集 = 参照 ∩ 面板；候选与每个同伴对着同一对手集（去掉各自所在局）算 \(S\)，再加权经验 CDF 得 \(Q\)。
2. **放宽阶梯**（§3.3 + 校准表）：
   - L0：同版本同回合；\(G \ge G_\text{min}=6\)
   - L1：并入 t±1，\(w_\text{relax}=0.25\)（已校准启用）
   - L2：**默认关闭**（配置可留，勿默认打开）
   - 仍不足 → `insufficient`（可有 \(S\)，\(Q\) 为空）；宽度 >20 点打 `wide`，仍给分位。
3. **聚类 bootstrap**（§3.7）：按**局**有放回重采样 + 蒙特卡洛噪声；默认 **B=1000**；输出 `ci95`、`widthPts`。
4. **输出** `data/strength/<bbVersion>/strength.jsonl`（gitignore 的 `data/` 下）：字段对齐方案 §3.10；带 `level` / `flags`；透传 HDT 五率与 `avDamage`（不解读符号）。
5. **CLI / 脚本：** 对当前 1.85 队列全量跑一遍；另提供**可复跑**的退出标准第 1 条统计（中位宽、≤20 点占比）。
6. **测试：** 合成矩阵单元测试（已知排名、已知区间形状）；全量跑后抽查：每行有 `level`；不存在「用了放宽却没标注」。

## 明确不做

- 重做 P3-T2 缓存基础设施（只消费/小修接口）。
- P3-T4 名次/承伤有效性主验证；P3-T5 复盘 UI。
- 为「压窄区间」擅自提高 `iterations` 或放宽 \(G_\text{min}\)/打开 L2——宽度不达标时**如实报告**，由所有者决定攒局或改规格。
- 给 Opponent 侧输出产品用分位（对照实验除外，且须标注非主路径）。

## 默认参数（冻结）

| 参数 | 值 |
| --- | ---: |
| `iterations` / `maxDurationMs` | 500 / 500（批跑侧，沿用 T2） |
| `panelGames` K | 30 |
| \(G_\text{min}\) | 6 |
| L1 / \(w_\text{relax}\) | 启用 / 0.25 |
| L2 | 关闭 |
| bootstrap B | 1000 |
| 参照含对手 | 是（可关） |

## P3 退出标准第 1 条（本任务必须跑出数字）

对当前主版本队列（≥20 局）、回合 ≤12 的己方 `ready` 场面：

1. 聚类 bootstrap 95% 区间宽度**中位 ≤15** 百分位点；
2. 且 **≥80%** 的场面宽度 ≤20。

校准期同批曾见中位宽 ≈36（分位离散主导）。**达标与否都要写入 facts 或 worklog 数字**；不达标不假装完成 P3 整阶段退出——只完成 T3 交付物与报告。

## 实现约束

- 消费 `tools/strength` cache；缺对时触发 T2 批跑补齐，勿另起一套模拟路径。
- 权重：同回合 \(w=1\)；L1 放宽 \(w=w_\text{relax}\)；对手侧默认不额外打折。
- PowerShell 5.1；小步 commit；不要 push。
- 语义变更停下来改方案/ADR，勿静默偏离 ADR-0011。

## 验收清单

- [ ] 合成矩阵单测通过（排名与区间行为符合预期）
- [ ] 1.85 全量 `strength.jsonl` 可生成；每行有 `level`；放宽均有标注
- [ ] 退出标准第 1 条统计脚本可复跑，结果写入 worklog（或 `docs/facts/`）
- [ ] 「只用己方参照」开关仍可用于对照（至少可配置）
- [ ] roadmap / status / worklog 已更新；宽度是否达标写清楚

## 收尾

按 [`session-handoff.md`](session-handoff.md)。所有者总结须突出：退出标准第 1 条数字、是否建议继续攒局、与校准宽≈36 的对比。
