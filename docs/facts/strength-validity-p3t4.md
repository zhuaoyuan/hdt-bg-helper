# P3-T4 指标有效性评估

> 这份文档回答：正式引擎 `strength.jsonl` 的局均分位是否与名次、下一回合血量显著相关；在名次标签上相对 HDT 当场胜率有无增量；以及是否触碰 ADR-0003 / ADR-0014。

```text
样本：BB 1.85.0.0；strength 30 局 / 329 己方场面（turn≤12）；团子配对有 placement 的局 7
工具：python -m tools.strength_validity；方案 docs/design/P3-T4-validity.md
健康：诊断 Input Player.Health（开战前）；本批 300 个 t→t+1 快照均为 input
统计：Spearman + 局级 bootstrap CI（B=5000）+ 置换 p（B=5000）；显著 = CI 不含 0 且 p<0.05 且 n≥12（局）
最后核实：2026-10-05
证据：data/strength/validity_1.85.json、validity_1.85_po.json（本地 gitignore）
```

## 1. 结论摘要（给所有者）

| 问题 | 结论 |
| --- | --- |
| 退出标准第 3 条 | **样本不足无法判定**（配对局 n=7 < 12） |
| 局均分位 ↔ 名次 | n=7，ρ≈**−0.22**（方向反常但极宽 CI），置换 p≈0.69，**不显著** |
| 局均分位 ↔ 下一回合血量 | n=30，ρ≈**0.21**，CI 含 0，p≈0.25，**不显著**（局均主口径） |
| 回合级血量（附录） | n=300，ρ≈0.21，CI≈[0.10, 0.32]，p≈0.0006，显著为正；局内非独立，**不作退出主证** |
| 相对 HDT 增量（名次） | 双方均 n=7 且不显著；偏 Spearman≈−0.14；**无法谈增量** |
| ADR-0003 | **证据不足**（未达最小 n，不触发、也不建议推翻） |
| ADR-0014 推翻#2（宽度下无区分） | **未命中**（有效性尚未可判定，不能归因于宽度） |
| 是否建议攒配对局 | **是**（至少凑到 n≥12，更好 ≥20） |

## 2. 主表（默认参照：含对手场面）

标签说明：名次相关的 y = `−placement`，故 **正 ρ = 分位越高名次越好**。

### 2.1 局均分位 vs 名次

| 指标 | 值 |
| --- | ---: |
| n（配对局） | **7** |
| Spearman ρ | −0.218 |
| bootstrap 95% CI | [−0.991, 0.921] |
| 置换 p | 0.691 |
| significant | False |
| 留一局同号 | False（小样本下符号不稳） |

配对 `gameId`：`62725a`, `3a513e`, `6ab052`, `c88ca9`, `20ad61`, `ed11e0`, `e1f536`。

### 2.2 相对 HDT（名次标签）

| 指标 | HDT 局均得分 vs −名次 | 分位 \| HDT（偏 Spearman） |
| --- | ---: | ---: |
| n | 7 | 7 |
| ρ | −0.109 | −0.143 |
| CI95 | [−0.961, 0.939] | [−1.0, 1.0] |
| 置换 p | 0.857 | 0.800 |

两者皆不显著；**不能**声称分位相对 HDT 有/无增量。

### 2.3 下一回合血量

| 口径 | n | ρ | CI95 | 置换 p | significant | 裁决 |
| --- | ---: | ---: | --- | ---: | --- | --- |
| **局均（主）** | 30 | 0.212 | [−0.157, 0.540] | 0.252 | False | 不显著 |
| 回合级（附录） | 300 | 0.213 | [0.102, 0.319] | 0.0006 | True | 附录显著；非独立 |

血量来源：`Player.Health`（input）300/300。未使用本场 `damage`。

### 2.4 附录：本场战果（非退出项）

与 T0 一致：回合级分位 vs 战果（胜=1/平=0.5/负=0）ρ≈**0.49**（n=250，显著）。**仅作对照**，不计入退出标准第 3 条。

## 3. 对照：`--player-only` 参照池

`strength_player_only.jsonl`（同 329 候选，缓存命中补齐交叉，L0）。

| 项 | 默认（含对手） | player-only |
| --- | ---: | ---: |
| 名次 ρ (n=7) | −0.218 | −0.164 |
| 局均血量 ρ (n=30) | 0.212 | 0.123 |
| 回合血量 ρ (n=300) | 0.213\* | 0.110（不显著） |
| 退出 #3 | 样本不足 | 样本不足 |

\*默认池回合级显著；player-only 回合级不显著。方向上血量相关仍偏正、名次点估计仍偏负，**无证据表明去掉对手场面能救名次信号**。

## 4. 退出标准第 2 条（墙钟，顺带）

| 检查 | 证据 | 门槛 | 结果 |
| --- | --- | --- | :---: |
| 新增 1 局增量 | 本机对 `ed11e0` `increment`（缓存已热）墙钟 ≈**17 s**；T0 冷交叉每局 max ≈44–92 s | ≤10 分钟 | **通过（引用+烟测）** |
| 整版本回填 | T3 冷 L0 回填 `wallSec≈742`（≈12.4 min，~33k 对）；本机缓存已满时 `backfill --dry-run` `pairsMissing=0` | ≤2 小时 | **通过（引用）** |

未改引擎默认旋钮。

## 5. 对所有者的裁决材料

1. **退出标准第 3 条：样本不足无法判定**（配对局 **n=7**；血量局均 n=30 已够但本身不显著）。
2. **ADR-0003：证据不足** — 名次样本不够；血量局均无显著相关，但尚不足以主张「指标无效到该推翻」。
3. **ADR-0014 推翻条件第二条：未命中** — 不能把「尚不可判定 / 局均血量弱」写成「因宽度过大而无区分」。
4. **建议继续攒团子配对局**后再跑同一命令；目标至少 n≥12（方案门槛），理想 ≥20 与退出第 1 条队列规模对齐。

## 6. 复跑

```powershell
python -m unittest discover -s tools/strength_validity

python -m tools.strength_validity run `
  --bb-version 1.85.0.0 `
  --turns 1-12 `
  --also-all-turns `
  --out data/strength/validity_1.85.json `
  --md data/strength/validity_1.85.md

# player-only 分位（缓存命中时无需补模拟）
python -m tools.strength percentile --bb-version 1.85.0.0 --turns 1-12 --player-only --no-fill `
  --out data/strength/1.85.0.0/strength_player_only.jsonl

python -m tools.strength_validity run `
  --bb-version 1.85.0.0 `
  --strength data/strength/1.85.0.0/strength_player_only.jsonl `
  --out data/strength/validity_1.85_po.json `
  --md data/strength/validity_1.85_po.md
```
