# 2026-10-04 — BgHelperDiag 大批次评估

## 做了什么

- 所有者把后续采集的对局放到仓库 `data/BgHelperDiag`（已 gitignore）。
- 用 `check_capture.py --all` 与新增的 `eval_fields.py` / `eval_anon_corruption.py` / `eval_dataset.py` 评估 48 局。
- 结论写入 [`facts/diag-capture-batch-20261003.md`](../facts/diag-capture-batch-20261003.md)；更新 `status.md`、`open-questions.md`（Q-002 / Q-011）。
- **团子版兼容性**（同日稍后）：分析 `20261004_200638_13406d`（团子 HDT 1.58.6.0 + 插件 0.1.0），对照官方 `20261003_105158_c4b8de`，并用 `data/tuanzi/2026年10月04日.txt` 交叉验证。脚本：`eval_tuanzi_crosscheck.py`。事实：[`facts/diag-tuanzi-compat-20261004.md`](../facts/diag-tuanzi-compat-20261004.md)。

## 发现

- **537/539** 场战斗按 P1 口径完整；46 局可用。跨 HDT 1.58.3→1.58.6、BB 1.78.1→1.85.0 采集链路未断。
- `meta.hearthstoneBuild` 在 56608/253216 间翻转，不能当分桶键。
- 匿名化无词边界替换导致 **10 局** `Player` 键/`$type` 被改成 `player_ab598ebe`；可机械修复，但插件要改。
- BB 1.85.0 出现 `DiscardCounter`；重放必须按采集版本选 DLL。
- P1 缺口再现：对手花费与 `2717` 仍全 0；畸变/双人仍 0；对手奥秘 9 场、任务 11 场。
- **团子版 diag 与官方 schema 兼容**（Input 键 330/330；Output 字段集相同）。本局 `Player` 键未腐蚀；`simulationCount=19998` 与团子文本一致。阵容攻血金与模拟五率 **10/10** 对上文本；T5/T6 实际结果偏离 `medianDamage` 属低置信 RNG，己方掉血差分验证了 T7/T8。

## 留下什么

- 数据本身不入库；评估事实已入库。
- 所有者确认后续采集走团子版 + 对战记录对照 → [ADR-0008](../decisions/0008-tuanzi-capture-with-record-crosscheck.md)；`field-capture.md` 已改默认路径。
- 下一步仍是 P2-T0 离线重放（带版本路由与键修复），并修诊断插件匿名化；批量 `eval_tuanzi_crosscheck` 可随后补。
- 团子对战记录不能替代完整 Input。
