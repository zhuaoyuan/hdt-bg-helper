# 2026-10-05 插件 0.2.0 首局验收

## 目标

确认部署后的 **HdtDiagLogger 0.2.0** 最新一局数据可被标准层导入，并满足团子对照与同版本 BB 重放。

## 做了什么

1. 定位 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\20261005_104908_ed11e0`（10:49–11:11）。
2. 同步团子当日文本 `C:\Program Files\HDT\对战记录\2026年10月05日.txt` → `data/tuanzi/`。
3. 跑 `python -m tools.standard_layer --out data\standard_ed11e0 --game ed11e0 --replay`。
4. 抽查 `records.jsonl.gz`：`$type` / `Player` / `Windfury` / `ControlledByPlayer` 均保留；无 0.1.x 误伤痕迹。

## 发现

| 项 | 值 |
| --- | --- |
| `pluginVersion` | **0.2.0** |
| 落盘 | `records.jsonl.gz` + `power.log.gz`（局末压缩生效） |
| `errors` / `probeInitError` / `endReason` | 0 / null / `game_end` |
| HDT / BB | 1.58.6.0 / 1.85.0.0（团子版） |
| 回合 | 12；英雄 伊利丹·怒风；名次 5 |
| ready（非 direct_dc） | **12/12 = 100%** |
| 团子阵容+五率+次数 | **12/12** |
| 重放 3σ | **12/12** |
| 战果来源 | 全部 `tuanzi` |
| gap | `opp_unknown_hand`×6（观测项，不降级） |

结论：**0.2.0 本局数据可用**；团子配对样本由 5 增至 **6**（仍未满退出标准的连续 10 局）。

## 留下的东西

- 本地报告：`data/standard_ed11e0/`（gitignore）
- 团子文本已更新：`data/tuanzi/2026年10月05日.txt`
