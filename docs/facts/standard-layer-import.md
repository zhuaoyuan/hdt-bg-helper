# 标准层离线导入（P2-T3）

> 这份文档回答：诊断记录如何变成每回合一行的标准层？质量报告看什么？本机跑通结果如何？

```text
工具：python -m tools.standard_layer
样本：data/BgHelperDiag（49）+ %APPDATA%/.../BgHelperDiag（6 去重后共 52 局）/ 609 回合
团子：data/tuanzi/2026年10月04日.txt、2026年10月05日.txt（配对 5 局）
重放：spikes/replay-harness，BB 1.85.0.0，配对 5 局 ready 回合
最后核实：2026-10-05
证据：docs/worklog/2026-10-05-p2t3-standard-layer.md；本地 data/standard/（不入库）
```

## 1. 结论

| 项 | 结果 |
| --- | --- |
| 标准层介质 | JSONL：每回合一行（`gameId`/`turn`/`inputRef`/`output`/`result`/`resultSource`/`status`/…） |
| 全量 ready（非 direct_dc） | **601/607 = 99.0%**（8 回合 `missing`，多为无 Combat Output） |
| 团子配对 5 局 ready（非 direct_dc） | **54/58 = 93.1%** ≥ 90% |
| ready ∩ 团子阵容+五率+次数 | **54/54 = 100%** |
| 同版本 BB 重放 3σ（配对 ready） | **54/54** |
| 战果来源（全量） | `hdt` 548 / `tuanzi` 47 / `lb` 14 |

连续满 **10** 局带团子文本的样本尚未凑齐；工具与配对局上的退出数字已满足，待所有者继续采集补到 10 局。

## 2. 命令

```powershell
python -m tools.standard_layer --out data\standard
python -m tools.standard_layer --out data\standard_replay_sample --game 62725a --game 3a513e --game 6ab052 --game c88ca9 --game 20ad61 --replay
python -m unittest discover -s tools\standard_layer -p "test_*.py" -v
```

## 3. 完整性与缺口

- `ready` / `partial` / `missing` / `unsupported` / `invalid` 定义见 `design/P2-data-capture.md` §3.3 与 §8（T3）。
- `gapFlags` 仍统计 `opp_unknown_hand`、`gap_2717_entity_nonzero_input_zero` 等正例，供 P1 缺口监控；**不**单凭它们降级 `ready`。
