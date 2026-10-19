# 标准层离线导入（P2-T3）

> 这份文档回答：诊断记录如何变成每回合一行的标准层？质量报告看什么？本机跑通结果如何？

```text
工具：python -m tools.standard_layer
样本：团子配对 7 局（含 0.2.0 的 ed11e0、e1f536）；历史全量约 52+ 局
团子：data/tuanzi/2026年10月04日.txt、2026年10月05日.txt
重放：spikes/replay-harness，BB 1.85.0.0
最后核实：2026-10-20（新增 144 局/1724 回合重新导入；P2 结论仍为 2026-10-05）
证据：docs/worklog/2026-10-05-p2t3-standard-layer.md；docs/worklog/2026-10-05-p2-early-exit.md
```

## 1. 结论

| 项 | 结果 |
| --- | --- |
| 标准层介质 | JSONL：每回合一行（`gameId`/`turn`/`inputRef`/`output`/`result`/`resultSource`/`status`/…） |
| 全量 ready（非 direct_dc，历史 52 局） | **601/607 = 99.0%** |
| 团子配对 **7** 局 ready（非 direct_dc） | **78/82 = 95.1%** ≥ 90% |
| ready ∩ 团子阵容+五率+次数 | **78/78 = 100%** |
| 同版本 BB 重放 3σ（配对 ready） | **78/78** |
| P2 退出 | **已关闭**（所有者 2026-10-05 接受 7 局样本提前结束；字面 10 局未凑满） |

### 1.1 插件 0.2.0 两局（2026-10-05）

| 局 id | 英雄 / 名次 | ready / 对照 / 重放 |
| --- | --- | --- |
| `20261005_104908_ed11e0` | 伊利丹 / 5 | 12/12 / 12/12 / 12/12 |
| `20261005_111748_e1f536` | 托里姆 / 3 | 12/12 / 12/12 / 12/12 |

命令：`python -m tools.standard_layer --out data\standard_paired7 --game 62725a --game 3a513e --game 6ab052 --game c88ca9 --game 20ad61 --game ed11e0 --game e1f536 --replay`

## 2. 命令

```powershell
python -m tools.standard_layer --out data\standard
python -m tools.standard_layer --out data\standard_paired7 --game 62725a --game 3a513e --game 6ab052 --game c88ca9 --game 20ad61 --game ed11e0 --game e1f536 --replay
python -m unittest discover -s tools\standard_layer -p "test_*.py" -v
```

## 3. 完整性与缺口

- `ready` / `partial` / `missing` / `unsupported` / `invalid` 定义见 `design/P2-data-capture.md` §3.3 与 §8（T3）。
- `gapFlags` 仍统计 `opp_unknown_hand`、`gap_2717_entity_nonzero_input_zero` 等正例，供 P1 缺口监控；**不**单凭它们降级 `ready`。

### 3.1 2026-10-20 重新导入（C1–C4）

- 根：仓库 `data/BgHelperDiag` + `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag`；结果 **144 局 / 1724 回合**（旧 55 局/640 回合报告保留为历史）。
- `ready` 1710、`missing` 14；非直接拔线 ready 99.4%；团子 strict 204/204（18 局配对）。
- `placement`：1724/1724 行有值；`rawVsTuanzi` 14/18（4 局不一致，其中 `6ab052` 团子“第 1 名”与“我被抬走”矛盾，已回退 raw）。
- `rules`：`availableRaces` 1724/1724（Input 的序列化 `List<Race>` 已归一）、`damageCap` 1710、`anomaly` 0、`duos` 0。
- 唯一 canonical 入口：`data/standard/dataset.json`（含 turns/quality 的 sha256、counts、placement/rules/versions）。
