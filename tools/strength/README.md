# tools/strength（P3-T2）

战力引擎的入池 / 面板 / 缓存 / 增量批跑。分位计算见 P3-T3。

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

# 与 P3-T0 out_both 对照（3σ）
python -m tools.strength verify-p3t0 --limit 120 --stride 40
```

诊断根目录默认同时扫 `data/BgHelperDiag` 与 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag`。  
缓存默认 `data/strength/cache.sqlite`（gitignore）。
