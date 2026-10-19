# 2026-10-19 数据完整性候选计划项重评

## 目标

在“完整八人排名不可得”修正之后，重新评估数据完整性候选，回答：现在做哪些、缓哪些、砍哪些，以及每项的可验收交付。

## 做了什么

- 复核 `research/data-architecture-audit-20261018.md` 的 20 项缺口与 G-02 修正；确认 `PLAYER_LEADERBOARD_PLACE` 只在出局时确定、HDT 自身只存本地 `FinalPlacement`（`GameEventHandler.cs:1069–1084`）。
- 复核现有工具：`tools/strength/raw_placement.py` 已能读本地终局名次（score-search 用过 56 局）；`tools/standard_layer` 仍只从团子写 `placement`（7 局）。
- 重新按“价值 / 成本 / 数据是否已经存在”给候选排序，形成 Wave 1/2/3。
- 新增方案 `docs/design/R-data-completeness-plan.md`（proposed）；审计文档第 4 节加“2026-10-19 重评”指针；`status.md` 下一步改为按 Wave 1 执行。

## 发现（重评结论）

- **最高 ROI 不是“补更多字段”，而是把已有的本地名次投影进标准层**：预计 P3-T4 的 `n` 从 7 提到 50+，直接重开退出标准第 3 条；成本却最小。
- **完整八人排名砍掉**：不是插件漏采，而是客户端在你提前出局后不再提供剩余玩家名次；没有新来源就不该留在 P0。
- **“标准层完全自包含”降级为缓办**：优先 thin standard + raw manifest/备份（C7）；否则成本大、且与 raw 事实源重复。
- **规则块（种族/畸变/伤害上限）值得立即做**：raw 已有，投影成本低，是“同规则参照池/可复算”的基础。
- **经济/操作数据仍等 Q-022**：对 P3 无直接收益，插件成本最大；不在 Wave 1 里偷偷排期。
- **1.88.6 验证是任何字段补强的门槛**：没有同版本 roundtrip/团子对照，不能宣称当前版本数据可信。

## 留下的东西

- 新方案：`docs/design/R-data-completeness-plan.md`（候选表 C1–C15、Wave 1/2/3、验收总表）。
- 审计第 4 节重评指针；`docs/status.md` 下一步更新。
- 未改代码/数据；未提交。

## 下一步

等所有者确认 Wave 1 范围后，从 W1-1（本地名次投影）开始；随后 W1-4（1.88.6 roundtrip）和 W1-2（规则块）。
