# tools/strength（P3-T2 / P3-T3）

战力引擎：入池 / 面板 / 缓存 / 增量批跑，以及留一局循环赛分位与聚类 bootstrap。

## 构建 ReplaySim

```powershell
$dn = "C:\Program Files\dotnet\dotnet.exe"
$hdt = "$env:LOCALAPPDATA\HearthstoneDeckTracker\app-1.58.6"
& $dn build tools\ReplaySim -c Release -p:HdtDir=$hdt -o tools\ReplaySim\bin\run
```

## 常用命令

```powershell
# 单元测试
python -m unittest discover -s tools/strength

# 回填某一模拟池（文件版本会先查 sim_pools.json；1.88.6.0 与 1.85.0.0 同一池）
python -m tools.strength backfill --bb-version 1.85.0.0 --turns 1-12

# 列出版本表 / 兼容检查 / 并池（检查未通过时 pool-join 不改表）
python -m tools.strength pools
python -m tools.strength pool-check --candidate 1.99.0.0 --sim-pool 1.85.0.0 --limit 100
python -m tools.strength pool-join --candidate 1.99.0.0 --sim-pool 1.85.0.0 --evidence docs/facts/....md --check data/strength/pool-checks/....json

# 分位 + bootstrap → data/strength/<simPool>/strength.jsonl（缺对会先补跑）
python -m tools.strength percentile --sim-pool 1.85.0.0 --turns 1-17

# 增量一局
python -m tools.strength increment --bb-version 1.85.0.0 --game-id 20261002_112126_685dd2

# 只用己方场面作参照（对照）
python -m tools.strength percentile --bb-version 1.85.0.0 --turns 1-12 --player-only --out data/strength/1.85.0.0/strength_player_only.jsonl

# 退出标准第 1 条（可复跑）
python -m tools.strength exit-width --bb-version 1.85.0.0

# 与 P3-T0 out_both 对照（3σ）
python -m tools.strength verify-p3t0 --limit 120 --stride 40
```

诊断根目录默认同时扫 `data/BgHelperDiag` 与 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag`。  
缓存默认 `data/strength/cache.sqlite`（gitignore）。  
`pairs` 存模拟次数；`matchups` 存「哪个场面打过哪个场面」并指向 `pairKey`。命中后不再重跑。  
分位输出默认 `data/strength/<simPool>/strength.jsonl`。`pairKey` 用模拟池，不用 DLL 文件版本。
