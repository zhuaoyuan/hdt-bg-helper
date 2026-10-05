# 离线工具

| 路径 | 用途 |
| --- | --- |
| `standard_layer/` | P2-T3：诊断记录 + 团子文本 → 每回合标准层表 + 质量报告 |

## 标准层导入

```powershell
python -m tools.standard_layer --root data\BgHelperDiag --root "$env:APPDATA\HearthstoneDeckTracker\BgHelperDiag" --tuanzi data\tuanzi --out data\standard
```

可选 `--replay`：对同版本 BB 做往返并写 `replayDelta`（需本机 `spikes/replay-harness` 已构建）。
