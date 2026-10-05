# 2026-10-05 — P2-T2 诊断插件转正

## 目标

完成 roadmap P2-T2：诊断插件必要补丁（匿名化词边界、局末压缩 `records`），转正为采集工具。

## 做了什么

1. 分支 `feat/P2-T2-diag-plugin-patches`。
2. **`Anonymizer`（0.2.0）**
   - 已知玩家名用编译正则替换，词边界类为 `[A-Za-z0-9_.]`（含 `.` 以保护 `$type` 命名空间段）。
   - 跳过 BB 结构保留裸名：`Player` / `Opponent` / `*Teammate` / `ControlledByPlayer` / `DuosInputPlayer*` / `Windfury` / `MegaWindfury` / `Simulation`。
   - `Player#1234` 等仍走原有 BattleTag 规则。
3. **`RecordWriter`**：局末对 `records.jsonl` 做与 `power.log` 相同的 gzip，产出 `records.jsonl.gz`。
4. **`DiagPlugin`**：版本 `0.2.0`；描述改为 capture tool。
5. **工具**：新增 `tools/diag_io.py`；`check_capture`、各 eval/analyze/peek、`replay-harness/tools/roundtrip.py` 同时认 `.jsonl` / `.jsonl.gz`。
6. **DumpTest**：断言结构键不被腐蚀；断言写出 `records.jsonl.gz`。本机构建 + 运行 **ALL CHECKS PASSED**；`check_capture` 对 fake 根目录 1/1 complete。
7. 文档：`design/P2-data-capture.md` §8、roadmap、status、field-capture、spike README；批评估事实 §4.1 注明 0.2.0 已修。

## 发现

- 仅靠 `\b` 风格词边界不够：`.Player`（`$type`）与 JSON 键 `"Player"` 仍会被整词匹配；保留名列表是必要补充。
- `hearthstoneBuild` / `2717` 按方案列为可选项，本任务未做。

## 留下的东西

- 代码：`spikes/hdt-diag-logger/`（插件 + tools）、`spikes/replay-harness/tools/roundtrip.py` 读路径。
- 已构建 DLL：`spikes/hdt-diag-logger/HdtDiagLogger/bin/Release/net472/HdtDiagLogger.dll`（对官方 HDT app-1.58.6）。**未**自动 `-Deploy`；需所有者关 HDT 后部署。
- 改动在分支 `feat/P2-T2-diag-plugin-patches`。
- 下一步：P2-T3 离线导入；历史 0.1.0 腐蚀局导入侧继续 `fix_anon`。
