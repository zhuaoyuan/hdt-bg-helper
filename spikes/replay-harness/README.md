# Spike：离线重放与往返验证（P2-T0）

**目的：** 把诊断记录里的 HDT `_input` 反射转储还原成 BB `Input`，按采集时 BB 版本在独立进程模拟，与记录 `Output` 对照；并跑 Q-009 / Q-011 / Q-013。

**结论：** 本机有 DLL 的 1.78.1 + 1.85.0 共 261/261 场五率往返通过。详见 [`docs/facts/replay-roundtrip.md`](../../docs/facts/replay-roundtrip.md)、方案 [`docs/design/P2-replay-harness.md`](../../docs/design/P2-replay-harness.md)。

## 内容

| 路径 | 说明 |
| --- | --- |
| `ReplaySim/` | net472 x64；运行时从 `--bb-dir` 加载 `BobsBuddy.dll` / `HearthDb.dll` |
| `tools/roundtrip.py` | 分段过滤残留 invoker、匿名化键修复、对照、q009/q011/q013 |
| `bb-dirs.json` | `fileVersion` → 本机 DLL 目录（可改） |
| `out/` | 本地跑出来的 JSON/日志（gitignore） |

## 复现

```powershell
$dn = "C:\Program Files\dotnet\dotnet.exe"
$hdt = "$env:LOCALAPPDATA\HearthstoneDeckTracker\app-1.58.6"
& $dn build spikes\replay-harness\ReplaySim -c Release -p:HdtDir=$hdt -o spikes\replay-harness\ReplaySim\bin\run

python spikes\replay-harness\tools\roundtrip.py --root data\BgHelperDiag --versions 1.78.1.0 1.85.0.0
python spikes\replay-harness\tools\roundtrip.py --root data\BgHelperDiag --mode q011 --limit 40
python spikes\replay-harness\tools\roundtrip.py --root data\BgHelperDiag --mode q013 --limit 30

# P3 批跑：驻留进程读 JSONL（每行 {"id","input"} 或 {"id","inputPath"}）
# ReplaySim.exe --bb-dir DIR --batch jobs.jsonl [--iterations N] [--max-duration MS]
```

缺 1.80.1 / 1.81.2 的 DLL 时对应局会 `skipped_no_dll`，不算失败。
