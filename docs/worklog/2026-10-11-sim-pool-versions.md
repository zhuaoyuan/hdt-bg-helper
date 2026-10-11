# 2026-10-11 模拟池版本表与并池重刷

按 `docs/process/prompts/sim-pool-versions.md` 把战力参照池从「BB 文件版本」改成「模拟池」。

## 决定与表

- ADR-0015（accepted）：只取代 ADR-0011 的分桶键。留一局循环赛、面板、L0/L1 不变。L2 仍关。并池条件是同输入五率，不是 E5 的分位差。
- `tools/strength/sim_pools.json`：`1.88.6.0` → 池 `1.85.0.0`（证据 `facts/replay-roundtrip.md` §3.2，未重跑 100 场）。`1.78.1.0` / `1.80.1.0` / `1.81.2.0` 各自单独成池。
- `pairKey` 改为 `sha256(simPool | assemblerVersion | 规范化 Input)`。`matchups` 主键改为 `(simPool, rowBoardId, colBoardId)`。
- 未通过检查时 `pool-join` 不改表（单测覆盖）。

## 缓存

- 迁移前复制 `data/strength/cache.pre-sim-pool.sqlite`。
- 1.85 与 1.88.6 的 `pairs` 都标成池 `1.85.0.0`。按 hash 归并时没有同一 Input 的两行（次数没有相加；也没有把 1.78 并进来，缓存里本来就没有 1.78）。
- 缺对粗算：约 32904 对，按 `elapsedMs` 中位数单线程约 362 秒，低于 2 小时，于是开跑。新模拟用池内最新已安装 DLL `1.88.6.0`。
- 重算过程中又进了一局（回合 1–13 左右各多 2 个场面）。补了 1760 对（全部 `ok`）后再干跑：回合 1–17 `pairsMissing=0`（73397/73397）。

## 分位

- 输出 `data/strength/1.85.0.0/strength.jsonl`。写入前把旧的按文件版本结果复制为同目录 `strength.pre-sim-pool.jsonl`。`data/strength/1.88.6.0/strength.jsonl` 未改，两份都停用。
- 第二次分位（含中途那一局）：**663** 个己方场面，L0 658 / L1 3 / insufficient 2，`missingAfter=0`，`nWide=258`。候选数大于并池前 1.88.6 单独的 277。
- 与旧 `strength/1.88.6.0/strength.jsonl` 比，共同场面 272 个，分位差绝对值中位数 **0.038**（分位按 0–1 计，约 3.8 个百分位点），p95≈0.176，max≈0.245。

## 单测

`python -m unittest discover -s tools/strength`：18 项通过。
