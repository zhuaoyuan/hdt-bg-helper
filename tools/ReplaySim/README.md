# ReplaySim（正式位置）

从 `spikes/replay-harness/ReplaySim/` 迁入（P3-T2）。独立进程加载 `--bb-dir` 下的 `BobsBuddy.dll`，支持单次 `--input` 与驻留 `--batch`。

```powershell
$dn = "C:\Program Files\dotnet\dotnet.exe"
$hdt = "$env:LOCALAPPDATA\HearthstoneDeckTracker\app-1.58.6"
& $dn build tools\ReplaySim -c Release -p:HdtDir=$hdt -o tools\ReplaySim\bin\run

# 批跑：每行 {"id","input"} 或 {"id","inputPath"}
# tools\ReplaySim\bin\run\ReplaySim.exe --bb-dir DIR --batch jobs.jsonl --iterations 500 --max-duration 500
```

BB 版本 → DLL 目录映射见同目录 `bb-dirs.json`（可按本机修改，不入库也可）。
