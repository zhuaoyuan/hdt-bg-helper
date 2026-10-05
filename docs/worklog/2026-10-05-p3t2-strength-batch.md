# 2026-10-05 P3-T2 批量模拟服务

## 目标

按 `docs/process/prompts/p3-t2-batch-sim.md` 实现入池 / 面板 / 缓存 / 增量批跑；不写分位（P3-T3）。

## 做了什么

1. **迁移** `spikes/replay-harness/ReplaySim/` → `tools/ReplaySim/`；spike 侧留 `MOVED.md`，`cross_eval` / README 默认 exe 指向新路径。
2. **新建** `tools/strength/`：
   - `assembler.py`：拼装 + 规范化 hash / `pairKey`
   - `pool.py`：ready 入池、幽灵剔除、分桶
   - `panel.py`：确定性最早 K 局面板、留一局缺失对、增量对
   - `cache.py`：SQLite `boards`/`pairs`，次数合并
   - `batch.py` + `__main__.py`：`backfill` / `increment` / `verify-p3t0`
3. **单元测试** 10 项：key 稳定、补跑合并、留一局、幽灵、面板确定性、sims slack。
4. **验收**：
   - t1 回填 2024 对约 11.5 s；第二次命中率 100%
   - `verify-p3t0` 120 对相对 `out_both` 3σ = 100%
   - 增量一局：t1 全命中，其余回合补跑成功

## 发现

- BB 返回的 `simulationCount` 常比请求少几个；若严格 `>=500` 会把已缓存对当成缺失再跑一遍。已用 `sims_sufficient`（2% / 2 abs）处理。
- 早期回合对极快（t1 两千对约 12 s），成本模型仍应以中后期为准。

## 留下的东西

- 分支：`feat/P3-T2-strength-batch`
- 正式代码：`tools/ReplaySim/`、`tools/strength/`
- 事实：`docs/facts/strength-batch-p3t2.md`
- 本地缓存与报告在 `data/strength/`（gitignore），不入库
- **下一步：** P3-T3（`process/prompts/p3-t3-percentile.md`）
