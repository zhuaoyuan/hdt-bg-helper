# 2026-09-26 清点新对局并做 P1-T3 字段分析

## 目标

所有者又打了几局。按方案第 5 节验收全部记录；样本够则做 P1-T3 / Q-006 / Q-007；不擅自 commit / push。

## 做了什么

1. 清点 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\`：3 个对局目录（另有 `salt.txt`，不入库）。
2. 跑 `python spikes/hdt-diag-logger/tools/check_capture.py --all`，并对照 HDT 日志里的插件超时警告。
3. 写离线分析脚本（只输出计数和匿名值）：
   - `spikes/hdt-diag-logger/tools/analyze_fields.py`
   - `analyze_timing.py`、`analyze_q007.py`、`analyze_extra.py`、`peek_structure.py`、`peek_input.py`
4. 把结论写进 `facts/diag-capture-measured.md`，更新 `facts/bobsbuddy-simulator-input.md`、`open-questions.md`。清单 v1 草稿 `design/P1-data-checklist-v1.md`（review，不勾 P1-T5）。
5. 未做 Q-013 / Q-009 / Q-011 独立进程实验（不阻塞 P1-T3）。未做往返验证。

## 发现

- **3 局均完整：** 9+8+10=27 场战斗，开战快照、`hdt_bb` Input/Output、战后快照齐全，0 错误，匿名化通过。快照最长 19 ms，单行回调最长 44 ms。HDT 日志无插件超时（只有启动时 Updater 的 2000ms 提示）。**不需要修插件，也不需要为完整性重打。**
- **Q-006：** `3533=0` 置战斗阶段并拍实体快照；`2022=0` 才有 BB Input，晚 54–105 行（中位 81）。第一次 Input 与 `2022=0` 27/27 同行 → 排队的 `StartCombat` 在 `OnPowerLogLine` 之前已跑完。
- **残留 invoker：** 后两局开头会倒出上一局回合 7/8/9 的 Input。不按 `2022=0` 行号过滤会把上一局血量当成这一局。过滤后 Health/Tier 27/27 对上。
- **Q-007：** 每场对手都有 `Bacon_TagTransferPlayerE`。多数 3.7 计数器与 TF 一致。`2717` 从不在 TF 上，Input 恒 0，玩家实体 9/27 场有 1–9。对手花费 27/27 为 0。3.6 附魔、饰品、神祇、英雄技能激活有正例。无畸变、无 Malorne、任务 1 条、战斗中补录几乎没有。
- **Q-002：** 27 场反射仍成功；Output 均为 9996 / `CompletedSimulations`。
- HDT 日志本批 `Duration=` 约 74–854 ms（进程内，留给 Q-009，不是独立进程）。

## 留下的东西

- 新增：`docs/facts/diag-capture-measured.md`、`docs/design/P1-data-checklist-v1.md`、本日志、若干 `spikes/hdt-diag-logger/tools/analyze_*.py` / `peek_*.py`。
- 更新：`bobsbuddy-simulator-input.md`、`open-questions.md`（Q-006 / Q-007 关闭）、`facts/README.md`、`roadmap.md`（P1-T3 勾完）、`status.md`、插件方案与 spike README。
- 未完成：P1-T5 等审阅；Q-013 / Q-009 / Q-011；P2 把快照改到 `2022=0`、丢掉旧 invoker 键。

---

## 异地采集：插件齐备判断与操作说明

### 目标

所有者将暂时没有开发环境，要在另一台电脑上继续 P1 采集。确认当前诊断插件是否够用，并写一份只靠拷文件就能开工的说明。

### 做了什么

1. 对照方案第 5 节、3 局 / 27 场验收、清单 v1 缺口，核对插件代码与本机已部署 DLL。
2. 新增 [`docs/process/field-capture.md`](../process/field-capture.md)；spike README 与流程索引加了入口；更新 `status.md`。

### 发现 / 结论

- **对继续采集齐备。** 本机 `Plugins\HdtDiagLogger.dll` 与仓库 Release 构建均为 44032 字节、2026-09-25 16:56，版本 0.1.0。27/27 场开战快照 / Input / Output / 战后快照齐全，0 错误，无超时。已知缺口是样本与游戏可见性，不是插件坏了。
- **新电脑不需要开发环境。** 只拷这一个 DLL 到官方 HDT 的 `Plugins\`，启用即可。不要拷 HDT / Bob's Buddy 二进制。
- **不必为 P2 设计债停手。** 快照仍在 `3533`、新对局会倒残留 invoker：分析能处理，正式采集器以后再改。

### 留下的东西

- 新增：`docs/process/field-capture.md`。
- 更新：`spikes/hdt-diag-logger/README.md`、`docs/process/prompts/README.md`、`docs/status.md`、本日志。
- 未完成：与上一节相同。
