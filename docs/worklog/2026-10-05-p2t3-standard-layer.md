# 2026-10-05 P2-T3 离线导入与质量报告

## 目标

完成 roadmap P2-T3：诊断记录 + 团子文本 → 每回合标准层表；战果来源标注；质量报告（含可选重放偏差）。

## 做了什么

1. 新建分支 `feat/P2-T3-offline-import`（基于含 P2-T2 的 HEAD）。
2. 实现 `tools/standard_layer/`：
   - 发现 `records.jsonl` / `.gz`；`2022=0` 后选取 Combat `hdt_bb`；匿名化键修复。
   - 团子解析与按日+英雄名+对手名配对（复用 Q-014 思路）。
   - 战果：`tuanzi` → `hdt` → `lb` → `unknown`（`facts/combat-result-reconstruction.md` §4）。
   - 完整性标签；质量报告；可选 `--replay` 调 `replay-harness`。
3. `power_replay.read_power` 改为走 `diag_io.power_path`（认 `.gz` / 未压缩）。
4. 冒烟单测 7 项通过；本机全量导入 + 配对 5 局重放通过。

## 发现

- 若把「对手未知手牌 / 实体 2717≠Input」直接打成 `partial`，ready 会掉到 ~34%，与退出标准冲突；这些是 HDT Input 自带的视野盲区，改为 `gapFlags` 观测项。
- 团子攻血文案常对应 BB `BaseHealth`，对照时 Max/Base 任一多重集匹配即可（例：`3a513e` T12）。
- 当前仅 5 局有团子文本可配对（非退出标准字面「连续 10 局」）；该 5 局指标已达标。

## 留下的东西

| 路径 | 说明 |
| --- | --- |
| `tools/standard_layer/` | 导入 CLI 与模块 |
| `tools/README.md` | 用法 |
| `docs/facts/standard-layer-import.md` | 核实结果 |
| `docs/design/P2-data-capture.md` §8 | T3 实现记录 |
| 本地 `data/standard/` | 609 行表 + 报告（gitignore） |

下一步：P3-T0（依赖本表）；所有者继续团子采集凑满连续 10 局以正式勾 P2 退出标准。
