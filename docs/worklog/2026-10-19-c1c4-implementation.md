# 2026-10-19/20 数据完整性 C1–C4 实施

## 目标

所有者决定 Q-022 暂缓，Wave 1 只做 C1–C4：

1. C1 本地终局名次投影；
2. C2 规则块进标准层/战力行；
3. C3 canonical 数据集 + 质量报告刷新；
4. C4 1.88.6 同版本 roundtrip。

## 做了什么

- **C1：** 新增 `tools/standard_layer/placement.py`；标准行加 `placement` / `placementRaw` / `placementTuanzi` / `placementTuanziValid` / `placementSource`。团子写“第 1 名”但该局最终“我被抬走”时判为不一致，回退 raw。
- **C2：** `combat.rules_block` 输出 `availableRaces`（Input 的序列化 `List<Race>` 归一为字符串数组）/ `anomalyDbfId` / `damageCap` / `duos`；标准行 meta 加 `hearthDbVersion` / `hearthstoneBuild`；`strength` 的 `Board.label` + `evaluate_candidate` 输出 `rules`/`versions`；新增 `tools/strength/backfill_rules.py` 对已有 663 行做元数据回填（identity 哈希校验不变）。
- **C3：** 标准层导入写 `data/standard/dataset.json`（roots、turns/quality sha256、counts、placement、rules、versions）；重新导入 **144 局 / 1724 回合**（旧 55 局/640 报告保留为历史）。
- **C4：** 用 `%APPDATA%\...\BgHelperDiag` 的 1.88.6 局跑同版本 roundtrip（DLL `C:\Program Files\HDT`），**978/978 通过**（81 局），JSON `data/strength/roundtrip_188_full.json`。
- 单测：standard_layer 16、strength 50、strength_validity 8、review_view 11 全过。

## 发现

- 重新扫描 APPDATA 后标准层从 933 行涨到 **1724 行 / 144 局**；团子配对从 7 局增加到 **18 局**（10-05/10-07 的新局被匹配上）。
- **名次标签不是“raw 就是真值”**：`PLAYER_LEADERBOARD_PLACE` 在对局中会随存活人数变化；raw `game_end` 与团子 14/18 一致，1 局团子内部矛盾（`6ab052` 写第 1 名但第 10 回合被抬走），3 局 raw 比团子大 1（`20ad61` 5/4、`ed11e0` 6/5、`d7b573` 4/3），原因未定。
- **T4 结论改变：** 1.85 n=31、分位 vs −名次 rho **0.070**（p=0.707），HDT rho **0.507**（p=0.0036）；1.88.6 n=25、rho **0.277**（p=0.179），HDT **0.678**（p=0.0002）。两版 `exit3` 均 **fail**，不再是 sample insufficient。tuanzi-only 敏感性 1.85 n=13、rho 0.069，方向不变。
- **C4 通过**：1.88.6 同版本 978/978，不再是 Q-002 的阻塞；但 1.88.6 仍无团子文本，团子对照未做。
- 规则覆盖：race 1724/1724、damageCap 1710/1724、anomaly 0、duos 0；`availableRaces` 的 Input dump 是序列化 `List<Race>`，已在导入侧归一。

## 留下的东西

- 代码：`tools/standard_layer/{placement.py,combat.py,__main__.py,report.py}`；`tools/strength/{pool.py,engine.py,backfill_rules.py}`；测试 `test_placement.py` / `test_dataset_manifest.py` / `test_backfill_rules.py`。
- 数据（本地，不入库）：`data/standard/{turns.jsonl,quality_report.*,dataset.json}`；`data/strength/validity_1.85_c1c4.*`、`validity_1.88.6_c1c4.*`、`validity_1.85_c1c4_tuanzi_only.*`、`validity_1.88.6_c1c4_tuanzi_only.*`、`roundtrip_188_full.json`；`strength.jsonl` 已回填 rules（备份 `.bak_before_rules`）。
- 文档：`design/R-data-completeness-plan.md` §12 实施记录；`status.md` 更新；`facts/replay-roundtrip.md` §1.1；`open-questions.md` Q-002/Q-022；审计文档加实施状态。
- 未提交。

## 下一步

所有者决定 T4 新结果：接受负结果 / 改指标 / 先复核 3 局名次标签再重跑；C5–C8 未批准，Q-022 暂缓。
