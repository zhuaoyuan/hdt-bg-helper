# 提示词：P3-T4 指标有效性评估

> 用途：在 **P3-T3 已产出** `strength.jsonl` 之上，评估战力分位对名次 / 后续血量的区分度，并在**名次**标签上相对 HDT 当场胜率比增量信息。  
> 通用流程另见 [`write-design.md`](write-design.md)（短方案）与 [`implement-task.md`](implement-task.md)。

## 所有者可粘贴的短指令

```text
执行 P3-T4，严格按 docs/process/prompts/p3-t4-validity.md。
前置：P3-T3 已合入；data/strength/<bb>/strength.jsonl 与标准层 turns 可对齐；退出标准第 1 条按 ADR-0014 已通过。
规格：roadmap P3-T4 + 退出标准第 3 条；ADR-0003 推翻条件；facts/strength-cross-p3t0.md §5/§8；design/P3-T1-strength-engine.md §5 第 3 条。
先写短方案 docs/design/P3-T4-validity.md（指标定义、样本过滤、显著性口径、验收命令），再实现可复跑脚本并跑当前主版本队列。
完成后按 session-handoff 更新 status / worklog / roadmap；如实报告是否触碰 ADR-0003。
不要 push，除非我要求。
```

## 开始前（必读顺序）

1. `AGENTS.md` → `docs/status.md` → `docs/roadmap.md`（P3-T4 与退出标准三条）。
2. 确认 **P3-T3 完成**：`tools/strength` 可生成 `strength.jsonl`；事实 [`strength-percentile-p3t3.md`](../../facts/strength-percentile-p3t3.md)；宽度门槛见 [ADR-0014](../../decisions/0014-relax-p3-exit-width.md)（已通过，本任务不重开宽度争论，除非 T4 结论要求）。
3. **指标定义：** [ADR-0003](../../decisions/0003-strength-metric-definition.md)（含推翻条件）。
4. **先验对照：** [`strength-cross-p3t0.md`](../../facts/strength-cross-p3t0.md) §5（战果/承伤/名次）、§8（有效性标签约束）；[`P3-T1-strength-engine.md`](../../design/P3-T1-strength-engine.md) §5 第 3 条、§6「只用己方」回归。
5. **数据：** 标准层 `turns.jsonl`（`placement`、`result`、`damage`、`status`、团子配对）；`strength.jsonl` 的 `percentile` / `S` / `ci95` / `hdt` / `level` / `flags`。英雄血量优先从 Input/诊断里的 `Player.Health`（战斗前快照）取「下一回合」——勿把本场 `damage` 误当成纯承伤（T0 已踩坑）。
6. 从 `main` 建分支：`feat/P3-T4-validity`（或等价短名）。

## 本任务范围（做）

### A. 短方案（先于代码）

写 `docs/design/P3-T4-validity.md`（可短），至少钉死：

| 项 | 要求 |
| --- | --- |
| 样本 | 主 BB 版本队列；候选仅 `side=Player` 且有分位；名次分析只含有 `placement` 的配对局；回合过滤默认与退出一致（≤12，可另报全回合对照） |
| 局均分位 | 定义清楚（如该局可用回合分位的均值）；缺回合如何处理 |
| 下一回合血量 | 操作化定义：优先 turn `t+1` 开战前己方英雄 `Health`；若字段缺失则写明降级指标（如累计净承伤）并标证据强度弱 |
| 「显著相关」 | 主报 Spearman（或等价秩相关）+ 样本 n + 置换/Bootstrap p 或置信区间；**小 n 时禁止夸大** |
| 相对 HDT 增量 | **标签 = 名次**（或名次二分：如 top4），**禁止**用本场胜/平/负当主增量标签（T0 已否定） |
| 稳定性（可选但建议） | 留一局 / 分前后半队列重算相关是否同号同量级；`wide` / `insufficient` 子集是否拖垮信号 |
| 对照 | 默认参照（含对手）vs `--player-only` 各跑一版主表 |

方案状态可为 `proposed`；实现中若只微调阈值口径，在方案「偏差」节补一句即可，不必另开 ADR。

### B. 可复跑评估

1. **包/脚本**（建议 `tools/strength_validity/` 或 `tools/strength` 子命令 `validity`，风格对齐现有 tools）：
   - 对齐 `strength.jsonl` × 标准层；
   - 输出 JSON/Markdown 表：局均分位↔名次、分位↔下一回合血量、HDT 基线、联合模型增量；
   - 命令写入事实文档，本机可复跑。
2. **主结果写入** `docs/facts/strength-validity-p3t4.md`（数字 + n + 命令 + 是否触碰 ADR-0003）。
3. **单元测试**：合成小表（已知单调关系 / 已知无关系）锁住聚合与对齐逻辑；不依赖本机全量对局。
4. **顺带核一眼退出标准第 2 条**（若 T2/T3 事实已有墙钟数字可引用则引用，缺则补一次增量一局 / 回填量级烟测）：新增 1 局 ≤10 分钟；整版本回填 ≤2 小时。不达标只报告，不改引擎默认值。

### C. 对所有者的裁决材料

在事实文末用固定小节回答：

1. 退出标准第 3 条：**通过 / 未通过 / 样本不足无法判定**（须带 n）。
2. ADR-0003：**不触发 / 建议讨论推翻 / 证据不足**。
3. ADR-0014 推翻条件第二条（宽度下无区分 → 先收窄再谈有效性）：是否命中。
4. 是否建议继续攒配对局后再评一次。

## 明确不做

- 重做循环赛 / bootstrap / 批跑缓存（只消费 T3 输出；缺行先跑现有 `percentile`）。
- 改默认 `iterations` / \(G_\text{min}\) / 打开 L2 / 放宽宽度门槛来「刷」相关显著性。
- 用本场战果 AUC 作为退出主证据（可作附录对照，须标注非退出项）。
- 调权重去拟合名次（样本太少；方案已禁止）。
- P4 覆盖层、P3-T5 UI 改版、方向决策（P5）。
- 擅自 `git push`。

## 先验约束（勿静默偏离）

| 来源 | 约束 |
| --- | --- |
| T0 §8 | 分位与 HDT **并列**；「相对 HDT 的本场增量」不是推翻条件 |
| roadmap / T1 §5 | 增量在**名次**上比；局均分位↔名次、↔下一回合血量 |
| T0 §5 | `damage` ≠ 纯承伤；名次相关需要足够配对局 |
| ADR-0003 | 区分度/稳定性不足才谈推翻——由所有者确认，agent 只给证据 |
| ADR-0011 | 评估按整局切分思维；报告时注意局内回合非独立 |

## 验收清单

- [ ] `docs/design/P3-T4-validity.md` 已写清指标与显著性口径
- [ ] 可复跑脚本 + 合成数据单测通过
- [ ] `docs/facts/strength-validity-p3t4.md` 含主表数字、n、复跑命令
- [ ] 退出标准第 3 条结论写清楚（含样本是否够）
- [ ] ADR-0003 / ADR-0014 相关裁决材料已写，未替所有者做「推翻」决定
- [ ] 退出标准第 2 条有引用或补测
- [ ] roadmap / status / worklog 已更新

## 收尾

按 [`session-handoff.md`](session-handoff.md)。给所有者的总结须突出：**第 3 条是否通过、配对局 n、是否建议攒局、是否需要讨论 ADR-0003**。
