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

# 回填某一 BB 版本（可限回合）
python -m tools.strength backfill --bb-version 1.85.0.0 --turns 1-12

# 增量一局
python -m tools.strength increment --bb-version 1.85.0.0 --game-id 20261002_112126_685dd2

# 分位 + bootstrap → data/strength/<bb>/strength.jsonl（缺对会先补跑）
python -m tools.strength percentile --bb-version 1.85.0.0 --turns 1-12 --stats-out data/strength/exit_width_1.85.json

# 只用己方场面作参照（对照）
python -m tools.strength percentile --bb-version 1.85.0.0 --turns 1-12 --player-only --out data/strength/1.85.0.0/strength_player_only.jsonl

# 退出标准第 1 条（可复跑）
python -m tools.strength exit-width --bb-version 1.85.0.0

# 与 P3-T0 out_both 对照（3σ）
python -m tools.strength verify-p3t0 --limit 120 --stride 40
```

诊断根目录默认同时扫 `data/BgHelperDiag` 与 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag`。  
缓存默认 `data/strength/cache.sqlite`（gitignore）。  
分位输出默认 `data/strength/<bbVersion>/strength.jsonl`。
