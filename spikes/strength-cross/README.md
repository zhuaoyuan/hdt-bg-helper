# Spike：战力分位交叉模拟（P3-T0 / P3-T1 校准）

**P3-T0 目的：** 用 BB 1.85.0 队列的 `ready` 双方场面做同回合交叉模拟，算 \(S(x)\)/分位，评估成本与区分度。  
**结论：** [`docs/facts/strength-cross-p3t0.md`](../../docs/facts/strength-cross-p3t0.md)。

**P3-T1 目的：** 在 `out_both` 对集上跑校准实验 E1–E3（E5 可选），落盘默认参数。  
**结论：** [`docs/facts/strength-calibration.md`](../../docs/facts/strength-calibration.md)。方案：[`docs/design/P3-T1-strength-engine.md`](../../docs/design/P3-T1-strength-engine.md)。

## 内容

| 路径 | 说明 |
| --- | --- |
| `tools/cross_input.py` | 拼装 Player←A / Opponent←B 的 Input JSON |
| `tools/cross_eval.py` | P3-T0：冒烟、批跑、分析 |
| `tools/calibrate.py` | P3-T1：E1 迭代 / E2 面板 K / E3 \(G_\text{min}\) 与 L1 / E5 跨版本 |
| `out/`、`out_both/`、`out_calibrate/` | 本地结果（gitignore） |

依赖 [`tools/ReplaySim`](../../tools/ReplaySim/) 的 `--batch` 模式（P3-T2 已从 spike 迁出）。

## 复现

```powershell
$dn = "C:\Program Files\dotnet\dotnet.exe"
$hdt = "$env:LOCALAPPDATA\HearthstoneDeckTracker\app-1.58.6"
& $dn build tools\ReplaySim -c Release -p:HdtDir=$hdt -o tools\ReplaySim\bin\run

# 可选：刷新标准层标签（含 APPDATA 新局）
python -m tools.standard_layer --out data\standard

python spikes\strength-cross\tools\cross_eval.py --smoke --out spikes\strength-cross\out
python spikes\strength-cross\tools\cross_eval.py --run --mode player_vs_player --out spikes\strength-cross\out
# 对照：参照含对手场面
python spikes\strength-cross\tools\cross_eval.py --run --mode player_vs_both --out spikes\strength-cross\out_both

# P3-T1 校准（复用 out_both 的 jobs；结果写入 out_calibrate/）
python spikes\strength-cross\tools\calibrate.py --all --baseline spikes\strength-cross\out_both --out spikes\strength-cross\out_calibrate
# 仅重算分析、不重跑模拟：
python spikes\strength-cross\tools\calibrate.py --e2 --e3 --skip-sim --baseline spikes\strength-cross\out_both --out spikes\strength-cross\out_calibrate
```
