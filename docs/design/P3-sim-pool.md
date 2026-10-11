# 方案：模拟池版本表与对战重刷

- **状态：** implemented
- **任务：** P3 战力参照池（ADR-0011 分桶键的替换）
- **作者 / 日期：** agent / 2026-10-11
- **相关：** [ADR-0015](../decisions/0015-sim-pool-by-compat.md)、`facts/replay-roundtrip.md` §3、`facts/sim-pool-members.md`、`process/prompts/sim-pool-versions.md`

## 1. 目标与非目标

**目标**

- 仓库内版本表 `tools/strength/sim_pools.json`：每条实际版本有 `bbVersion`、`simPool`、`joinedAt`、`evidence`。
- 入池、面板、L0/L1、`matchups`、分位按 `simPool` + 回合。`pairKey` 含 `simPool`，不含 DLL 文件版本。
- 1.85 与 1.88.6 的已有次数按 `(rowBoardHash, colBoardHash, shellHash, assemblerVersion)` 相加合并；缺对补模拟；池 `1.85.0.0` 重算分位且 `missingAfter=0`。
- CLI：列出版本表、`pool-check`、`pool-join`（无通过记录不改表）。

**非目标**

- 不把 1.78.1 / 1.80.1 / 1.81.2 并入 1.85 池，不启用 L2，不重跑 E1–E5，不改 `iterations` / `K` / `G_min` / `w_relax`。
- 不重写复盘 HTML。不删除旧的 `data/strength/1.85.0.0/` 与 `data/strength/1.88.6.0/` 分位文件。

## 2. 依据

- §3.2：1.85.0→1.88.6 同输入 100/100 在 3σ 内。§3.1：1.78.1→1.85.0 有显著偏差。§3.3 的「不混参照池」由 ADR-0015 取代，测量句子保留。
- 并池门槛是同输入五率，不是分位差。判定函数与 `spikes/replay-harness/tools/roundtrip.py` 的 Q-011 相同（win/tie/loss 的 3σ 加地板；事实文档称五率）。

## 3. 方案

| 名字 | 字段 | 规则 |
| --- | --- | --- |
| 实际版本 | `bbVersion` | 采集版本。场面行保留。 |
| 模拟池 | `simPool` | 池内最早的 `bbVersion`。未出现在表中的版本视为单独成池（池 Id = 自身）。 |

- `pairKey = sha256(simPool | assemblerVersion | 规范化 Input)`。传入文件版本时先查表再哈希。
- `pairs.simPool` 为分组列。迁移时同一池、同一 hash 的多行次数相加，保留建池版本那一行的 `pairKey`（1.85 的键已经等于新键）。只有 1.88.6 的行保留原 `pairKey`，查找仍走 hash 索引，避免重跑。
- `matchups` 主键 `(simPool, rowBoardId, colBoardId)`。
- 池内新模拟使用已安装成员里版本号最大且本机有 `BobsBuddy.dll` 的那一份（当前池 `1.85.0.0` 为 `1.88.6.0`）。
- 分位写到 `data/strength/<simPool>/strength.jsonl`，行内同时有 `bbVersion` 与 `simPool`。写入前把尚无 `simPool` 字段的旧文件复制为同目录 `strength.pre-sim-pool.jsonl`。
- 缺对粗算用缓存里 `elapsedMs` 中位数 × 缺对数（按单线程）。超过 2 小时则只打印数字、不开始模拟。

`pool-check` 调用现有 Q-011：候选 DLL 对目标池最新已安装 DLL。通过才写出检查 JSON。`pool-join` 读取该 JSON，`passed` 不为真则不改 `sim_pools.json`。

## 4. 考虑过的替代方案

按文件版本继续分桶：实现零迁移，但 1.88.6 参照池维持偏窄。不选，见 ADR-0015。

## 5. 验收方式

```powershell
python -m unittest discover -s tools/strength
```

本机：池 `1.85.0.0` 的 `strength.jsonl` 候选数大于并池前 1.88.6 的 277，`missingAfter=0`，再次 `backfill --dry-run` 的 `pairsMissing=0`。

## 6. 风险与回退

混池分位不必等于旧的 1.88.6 分位。与旧 `strength/1.88.6.0/strength.jsonl` 的共同场面分位差中位数记入 worklog。缓存迁移前复制 `cache.pre-sim-pool.sqlite`。

## 7. 任务拆分

1. 版本表、ADR、方案。
2. `pairKey` / 缓存 / 入池改为 `simPool`，单测。
3. 迁移生产缓存，干跑缺对数，未超 2 小时则补模拟并重算分位。
