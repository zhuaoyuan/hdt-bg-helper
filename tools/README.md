# 离线工具

| 路径 | 用途 |
| --- | --- |
| `standard_layer/` | P2-T3：诊断记录 + 团子文本 → 每回合标准层表 + 质量报告 |
| `board_render/` | P3-T6：无状态单侧阵容条 PNG（`render_side`）；本机可读 HDT Minion 贴图 |

## 标准层导入

```powershell
python -m tools.standard_layer --root data\BgHelperDiag --root "$env:APPDATA\HearthstoneDeckTracker\BgHelperDiag" --tuanzi data\tuanzi --out data\standard
```

可选 `--replay`：对同版本 BB 做往返并写 `replayDelta`（需本机 `spikes/replay-harness` 已构建）。

## 阵容图渲染

```powershell
python -m tools.board_render --game ed11e0 --side both --out data\boards
python -m tools.board_render --check --game ed11e0
python -m tools.board_render --game ed11e0 --offline --chrome-dir "D:\path\to\Minion" --out data\boards
```

HDT 贴图仅本机个人使用，勿提交进 git。输出在 `data/`（已 gitignore）。
