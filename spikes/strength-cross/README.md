# Spike：战力分位核心假设早期验证（P3-T0）

**目的：** 用 BB 1.85.0 队列的 `ready` 双方场面做同回合交叉模拟，算 \(S(x)\)/分位，评估成本、bootstrap 稳定性、与战果/承伤相关、相对 HDT 胜率增量，并对照固定基准场面集。

**结论：** 见 [`docs/facts/strength-cross-p3t0.md`](../../docs/facts/strength-cross-p3t0.md)。方案：[`docs/design/P3-T0-core-hypothesis.md`](../../docs/design/P3-T0-core-hypothesis.md)。

## 内容

| 路径 | 说明 |
| --- | --- |
| `tools/cross_input.py` | 拼装 Player←A / Opponent←B 的 Input JSON |
| `tools/cross_eval.py` | 冒烟、批跑、分析 |
| `out/` | 本地结果（gitignore） |

依赖已有 `spikes/replay-harness/ReplaySim` 的 `--batch` 模式。

## 复现

```powershell
$dn = "C:\Program Files\dotnet\dotnet.exe"
$hdt = "$env:LOCALAPPDATA\HearthstoneDeckTracker\app-1.58.6"
& $dn build spikes\replay-harness\ReplaySim -c Release -p:HdtDir=$hdt -o spikes\replay-harness\ReplaySim\bin\run

# 可选：刷新标准层标签（含 APPDATA 新局）
python -m tools.standard_layer --out data\standard

python spikes\strength-cross\tools\cross_eval.py --smoke --out spikes\strength-cross\out
python spikes\strength-cross\tools\cross_eval.py --run --mode player_vs_player --out spikes\strength-cross\out
# 对照：参照含对手场面
python spikes\strength-cross\tools\cross_eval.py --run --mode player_vs_both --out spikes\strength-cross\out_both
```
