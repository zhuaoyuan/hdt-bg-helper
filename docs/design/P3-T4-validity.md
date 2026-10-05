# 方案：P3-T4 指标有效性评估

- **状态：** implemented（2026-10-05；口径微调见 §8）
- **任务：** P3-T4
- **作者 / 日期：** agent / 2026-10-05
- **相关：** ADR-0003、ADR-0011、ADR-0014；`facts/strength-cross-p3t0.md` §5/§8；`design/P3-T1-strength-engine.md` §5 第 3 条；roadmap P3 退出标准第 3 条

## 1. 目标与非目标

**目标：** 在已产出的 `strength.jsonl` 上，可复跑地评估战力分位对**名次**与**下一回合己方血量**的区分度，并在名次标签上相对 HDT 当场胜率比增量；给出退出标准第 3 条与 ADR-0003 / ADR-0014 推翻材料（不替所有者做推翻决定）。

| “做完”判据 | 说明 |
| --- | --- |
| 短方案钉死口径 | 本文件 §3–§5 |
| 可复跑脚本 | `tools/strength_validity`；合成单测通过 |
| 主结果事实 | `docs/facts/strength-validity-p3t4.md`（数字 + n + 命令 + 裁决小节） |
| 第 2 条顺带 | 引用 T2/T0 墙钟或补一次增量/回填量级烟测 |

**非目标：** 重跑循环赛/改默认旋钮；用本场胜平负当主增量标签；调权重拟合名次；P4/T5 UI；`git push`。

## 2. 依据

| 来源 | 约束 |
| --- | --- |
| roadmap 退出 #3 | 局均分位↔名次、↔下一回合血量显著相关；增量在**名次**上比 |
| ADR-0003 推翻 | 区分度/稳定性不足才谈推翻；agent 只给证据 |
| ADR-0014 推翻 #2 | 现宽度下无区分 → 先收窄再谈有效性 |
| T0 §5/§8 | `damage`≠纯承伤；名次需足够配对局；相对 HDT 本场增量不是推翻条件 |
| ADR-0011 | 评估按整局切分思维；局内回合非独立 |

**依赖假设：** `data/strength/<bb>/strength.jsonl` 已由 T3 生成；标准层 `turns.jsonl` 可对齐；诊断目录可读 `Player.Health`。

## 3. 样本与过滤

| 项 | 默认 |
| --- | --- |
| 队列 | 主 BB 版本（当前 `1.85.0.0`） |
| 候选 | `side=Player` 且 `percentile` 非空 |
| 回合 | 主表 `turn≤12`；另附全回合对照 |
| 名次分析 | 仅团子配对且 `placement` 非空的局 |
| 血量分析 | 该局有 `t` 与 `t+1` 开战前血量；不要求有 placement |
| 对照 | 默认 strength（参照含对手）与 `--player-only` 产出的 jsonl 各跑一版主表 |

**局均分位：** 局内可用回合（满足上表）的 `percentile` 算术均值；若某局零可用回合则该局不进名次表。

**HDT 局均得分：** 同回合集合上 `hdtScore = winRate + 0.5·tieRate` 的均值（缺 `hdt` 时从标准层 `output` 回退）。

## 4. 下一回合血量（操作化）

1. **主指标：** 对回合 `t`，取同局回合 `t+1` 战斗前己方英雄血量 = 诊断 Input `Player.Health`（开战快照）。
2. **降级：** 若 Input 不可得，用标准层 `output.friendlyHealth`（同为开战/记录血量；本机对照与 Input 一致时证据不降级，否则标弱）。
3. **禁止：** 不把本场 `damage` 当纯承伤主标签（T0 已否定）。
4. **相关方向：** 更高分位应关联**更高**的下一回合血量（Spearman 期望为正）。报告时同时给回合级与「局均分位 ↔ 局末日血量/局均下回合血量」对照；主判定用**局均**口径与退出条文对齐，回合级作附录（注明非独立）。

## 5. 「显著相关」与增量口径

| 项 | 口径 |
| --- | --- |
| 主统计量 | Spearman ρ（秩相关） |
| 不确定度 | 对局做 bootstrap（B=5000）得 95% CI；另报置换检验双侧 p（B=5000） |
| 显著性 | CI 不含 0 **且** 置换 p&lt;0.05；**同时**满足最小 n |
| 最小 n（名次） | 配对局 **n≥12** 才判通过/未通过；否则 **样本不足无法判定**（仍报点估计） |
| 最小 n（血量，局均） | 有下回合血量的局 **n≥12**；回合级附录 n≥30 才谈显著 |
| 小 n | 禁止把「方向对」写成「显著」；事实文明确写 n |
| 相对 HDT 增量 | 标签 = `placement`（越小越好；相关时对名次取负号使「更强→更好」为正，或直接报 ρ 并注明方向）。比较：ρ(局均分位, −名次) vs ρ(局均 HDT, −名次)；增量 = 分位在控制 HDT 后的偏 Spearman（残差秩相关）。**禁止**用本场胜/平/负作主增量标签（附录可对照并标注非退出项） |
| 稳定性（建议） | 留一局重算 ρ 符号；前后半队列各算一次；去掉 `wide`/`insufficient` 后 ρ 是否同号同量级 |

**退出标准第 3 条判定：**

- **通过：** 名次与下一回合血量（局均口径）均达「显著」且方向正确（分位↑ → 名次更好、下回合血量↑）。
- **未通过：** n 足够但至少一项不显著或方向错误。
- **样本不足无法判定：** 名次或血量任一项 n 不足。

ADR-0003 / ADR-0014：只给「不触发 / 建议讨论推翻 / 证据不足」材料，不擅自改 ADR 状态。

## 6. 交付与命令

新建 `tools/strength_validity/`：

| 文件 | 职责 |
| --- | --- |
| `align.py` | strength × turns ×（可选）diag Health |
| `metrics.py` | Spearman / bootstrap CI / 置换 / 偏相关 |
| `report.py` | 汇总主表 JSON + Markdown |
| `__main__.py` | CLI |
| `test_validity.py` | 合成单调/无关系表锁对齐与聚合 |

```powershell
python -m unittest discover -s tools/strength_validity
python -m tools.strength_validity run --bb-version 1.85.0.0 --strength data/strength/1.85.0.0/strength.jsonl --out data/strength/validity_1.85.json --md docs/facts/_validity_1.85.md
# player-only 对照（若已有 jsonl）
python -m tools.strength_validity run --bb-version 1.85.0.0 --strength data/strength/1.85.0.0/strength_player_only.jsonl --out data/strength/validity_1.85_po.json
```

主结论写入 `docs/facts/strength-validity-p3t4.md`（可手改润色；数字以脚本输出为准）。

## 7. 风险与回退

| 风险 | 处理 |
| --- | --- |
| 配对局仍少（T0 时 7 局） | 诚实报「样本不足」；建议攒局后再评 |
| strength 有局而 turns 未导入 | 名次依赖 turns；血量可走 diag；报告列出未对齐 gameId |
| player-only 缺 jsonl | 若缓存可快速出则补跑；否则主表只报默认池并注明对照缺 |

## 8. 偏差

- 实现包名 `tools/strength_validity`（未做成 `strength` 子命令，避免拖长引擎 CLI）。
- Spearman 用 `scipy.stats.spearmanr`；常数列返回 `rho=None`（避免 Windows 警告刷屏）。
- 血量主路径 1.85 队列上 Input 与 `friendlyHealth` 一致；本批回合级 300 点全为 `input`。
- `--player-only` 对照：用现有缓存 `percentile --player-only --no-fill` 写出 `strength_player_only.jsonl` 后再评（未改默认池）。
- JSON 笔记用 ASCII，避免 Windows GBK 控制台打印失败。
