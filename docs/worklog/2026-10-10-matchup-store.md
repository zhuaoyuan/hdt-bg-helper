# 2026-10-10 1.88.6 全池算分，两两对战结果落盘

## 目标

把最新 BB 版本已结束对局放进同一个参照池算分，并把两两阵容的模拟结果存下来，下次只补缺对。

## 做了什么

1. 诊断目录里 BB **1.88.6.0** 已结束但未入库的 6 局，侧写到 `data/standard_188_late`（80 行，全部 `ready`），再并入 `data/standard/turns.jsonl`（备份 `turns.jsonl.bak_before_188_late`）。全库 **79 局 / 933 行**。无团子日文件，名次仍空。
2. 方案 [`docs/design/P3-matchup-store.md`](../design/P3-matchup-store.md)：
   - `data/strength/cache.sqlite` 增加 `matchups`（场面 Id → `pairKey`）。次数仍在 `pairs`。
   - 规划缺对时先查 hash 索引；够次数就登记 `matchups`，不调用模拟器。
   - 只有留一局后不足 \(G_\text{min}\) 的回合才做 turn±1。早前回合不再被晚回合拖进跨回合重算。
3. `python -m tools.strength percentile --bb-version 1.88.6.0 --turns 1-17`（约 6.4 分钟）。再 `backfill --dry-run`：同回合 **21296 / 21296** 命中，`pairsMissing=0`，约 9 秒。

## 发现

- 薄回合只有 t14–t17。L1 实际新跑 388+28+8 对，不是上次那种整桶约 1.9 万对。
- `pairs`（1.88.6）由约 3.4 万行增到 **43600**。`matchups` **21824** 行（本池用到的对，含薄回合跨回合）。`boards` 541。
- 分位：`data/strength/1.88.6.0/strength.jsonl`，**23 局、277** 个己方场面。`missingAfter=0`。L0 **266** / L1 **6** / insufficient **5**（`3f32a5` T15–T17，`7953ca` T15，`0ed6d1` T15）。`nWide=230`。

## 留下的东西

- 代码：`tools/strength/cache.py`、`batch.py`、`engine.py`、`assembler.py`；测试 `test_index_hit_skips_job_and_records_matchup`、`test_slack_turns_do_not_expand_fat_buckets`。
- 未做：按新分位重写复盘 HTML；1.88.6 同版本 roundtrip。早前 7 份复盘页仍是 17 局池的分。
