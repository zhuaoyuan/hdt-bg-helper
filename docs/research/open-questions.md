# 未决问题与风险登记

> 这份文档回答：还有哪些事情不确定、它们影响什么、准备怎么验证。问题关闭后不删除，写明结论和结论写到了哪里。

状态：`open` 未决 / `investigating` 调研中 / `closed` 已关闭

影响：`高` 可能推翻方案 / `中` 影响设计细节 / `低` 影响有限

## 未决

| 编号 | 问题 | 影响 | 验证方式 | 关联 | 状态 |
| --- | --- | --- | --- | --- | --- |
| Q-002 | 能否通过反射读取 HDT 内部 `BobsBuddyInvoker._input`，作为对照基准或数据源？稳定性如何？ | 中 | **已跨 4 个 HDT / BB 小版本继续成功**（2026-10-04 批：HDT 1.58.3→1.58.6，BB 1.78.1→1.85.0，537/539 场完整 Input+Output，`probeInitError` 全空）。P2-T1 已采纳为**主数据源**（ADR-0010）；残留 invoker、匿名化误伤见 `facts/diag-capture-batch-20261003.md`。字段级改名：1.85.0 新增 `DiscardCounter`。仍 investigating：大版本/反射成员改名时再测（升级冒烟：`check_capture` + roundtrip） | ADR-0010、`spikes/hdt-diag-logger/` | investigating |
| Q-008 | 个人对局数据量能否支撑按"同补丁 + 同回合 + 同规则"筛选的参照池？需要多少局？ | 高 | 估算见 `research/q008-personal-data-volume.md`。**P3-T0 实测**：约 23 局时 bootstrap（场面重采样）中位宽 ≈12–14。**P3-T1 校准**：\(G_\text{min}=6\)；聚类 bootstrap 中位宽本批≈36 点（离散分位主导，见 `facts/strength-calibration.md`）。严格再按种族/畸变分桶仍不可行 | P3、`facts/strength-cross-p3t0.md`、`facts/strength-calibration.md` | investigating |

## 已关闭

| 编号 | 问题 | 结论 | 结论位置 |
| --- | --- | --- | --- |
| Q-015 | 交叉模拟迭代次数可降到多少？ | **默认 500。** E1：相对 4000 基线，500 满足 \|ΔQ\| p95≤3、Spearman(S)≥0.99、bootstrap 宽不增；250 未过。300 对 @20000 显示 4000 已贴近真值（2026-10-05） | `facts/strength-calibration.md`、`design/P3-T1-strength-engine.md` §3.9 |
| Q-016 | 新 BB 版本冷启动能否用上一版本场面作参照（当前 DLL 重模拟）？ | **不能启用 L2。** E5：1.81.2 参照给 1.85 候选打分，\|ΔQ\| p95≈13.6 >5；与 Q-011 跨版本偏差一致。冷启动显示 `insufficient`（2026-10-05） | `facts/strength-calibration.md`、ADR-0011 |
| Q-009 | 单场模拟 1.5–5 秒、占半数核心；P3 批量模拟的总耗时是否可接受？ | **可接受（按默认标准）。** 真实场面独立进程模拟 `elapsedMs` 中位 411 ms（261 场，max 1046 ms）；每局全部回合模拟合计 max ≈8 s，远低于「每局 ≤ 10 分钟」。一场一进程墙钟中位 ≈1.6 s/场，仍无局超预算（2026-10-05） | `facts/replay-roundtrip.md` §2 |
| Q-011 | 离线批量模拟该用哪个版本的 `BobsBuddy.dll`？与采集时不一致会偏多少？ | **必须用采集时同版本。** 1.78.1 场面用 1.85.0 重跑：40 场中 3 场五率显著偏（Δwin 最高约 0.23）。默认策略不变；缺 DLL 的版本跳过重放（2026-10-05） | `facts/replay-roundtrip.md` §3 |
| Q-013 | HDT 从未赋值的 BB 公开字段开战时是否影响模拟结果？ | **对本批测的六个 Player 计数器：不影响。** 30 场将双方 `DeepBluesCounter`/`AnySpellCounter`/`BackToBackCounter` 设为 7 后五率均无显著变化。不要求单独采集这些字段；随从侧未赋值成员未全测（2026-10-05） | `facts/replay-roundtrip.md` §4 |
| Q-001 | `BobsBuddy.dll` 中 `Input`、`Player`、`Minion`、`SimulationRunner` 等类型是否公开，插件能否自行构造输入并调用模拟？ | 能。核心类型全部 `public`、可直接构造；独立 net472 x64 进程里调用 `SimulateMultiThreaded`，在 1.76.0 和 1.78.8 上都得到符合预期的结果。两个版本间核心 API 只有 `Player.MagnetizeCounter` 一处签名变化（2026-09-25） | `facts/bobsbuddy-public-api.md`、`spikes/bobsbuddy-api/` |
| Q-003 | HDT 自身和 `BobsBuddy.dll` 的许可条款是否允许个人插件引用和调用？ | 两者均为专有软件，条款只授予个人非商业使用。所有者确认：本机个人非商业使用相容；调用公开 API 与实时显示战力分位均为合理用途；仓库可公开但不得含 HDT/BB 二进制或反编译代码（2026-09-25） | `facts/licensing.md`、ADR-0006、ADR-0002 |
| Q-004 | HDT 日志中"Simulation Input / Output"段落是否足以重建输入？能否作为采集正确性的对照基准？ | 不能完整重建，只能近似。日志有随从（名字、攻血、关键词、金色、`ScriptDataNum`、附魔名）、场上顺序、英雄技能、任务、奥秘名和约一半计数器；缺英雄血量/护甲/等级、饰品、目标、畸变、可用种族、伤害上限和另一半计数器。Output 只有胜/平/负率、致死率、次数和耗时，没有伤害分布；可以作为 P2-T5 胜/平/负的对照，但只宜用每场只有一个 Input 段落的样本，并接受缺失字段带来的偏差（2026-09-25） | `facts/hdt-log-simulation-input.md`、`spikes/hdt-log-analysis/` |
| Q-005 | 插件构建时如何引用 HDT 和闭源 DLL（安装目录、版本对齐、CI 能否构建）？ | 本地构建已验证：.NET SDK 的 net472 x64 类库以 `Private=false` 引用安装目录的 HDT exe 和 DLL 即可，不需要 Visual Studio。CI：GitHub Releases 只到 v1.55.6，拿不到新版二进制文件，是否需要 CI 由所有者决定。在 HDT 中实际加载留到 P2 原型（2026-09-25） | `facts/hdt-baseline.md` 的"插件加载""插件构建"、`spikes/hdt-plugin-skeleton/` |
| Q-010 | 本机安装的修改版 HDT（1.58.1）相对上游改了什么？是否改动了 `BobsBuddyInvoker`、日志格式或插件接口？ | 不再需要回答。已知部分：第三方"团子版"，日志在上游格式之外插入额外行，新增拔线、对战记录等功能；没发现改动模拟输入逻辑或插件接口的证据，但无法完全排除。所有者已换用官方版（ADR-0007），插件不再面向修改版。剩余影响只在历史日志：它们来自团子版 1.49.2 – 1.57.12，用于近似重建场面时要注明来源，不用作 P2-T5 的精确对照（2026-09-25）。**补充（2026-10-04）**：团子 HDT 1.58.6.0 + 诊断插件采到的 `_input` dump 与官方同 BB 版本 schema 兼容，且与团子对战记录文本阵容/五率 10/10 对齐；这不推翻「历史 Power 日志不作精确对照」，但说明**当前团子+插件路径的 diag 记录可与官方批次混用** | `facts/hdt-log-simulation-input.md` 第 5 节、ADR-0007、`facts/diag-tuanzi-compat-20261004.md` |
| Q-012 | 继续用修改版 HDT 作为验证环境（ADR-0005）是否合适？ | 不继续。所有者 2026-09-25 安装官方 HDT 1.58.3 并承诺保持最新，ADR-0005 被 ADR-0007 取代。团子版对战记录中 372 场拔线战斗没有结果，这批数据只用于对局量统计 | ADR-0007、`facts/local-environment.md` |
| Q-006 | 战斗中揭示的信息插件能否在同一时机拿到？标签变化动作是否排队、插件看到某一行时 HDT 是否已更新完？ | **已更新完。** `OnPowerLogLine` 在 `Handle` + `InvokeQueuedActions` 之后。27/27 场第一次 `_input` 在 `GameEntity` 标签 `2022` 1→0 的同一行。`3533` 1→0 只置战斗阶段（早 54–105 行）。无公开 BB 更新事件；BLOCK 仍要自己从原始行重建。`creationTag` 行不触发排队执行，本批未单独对照 | `facts/bobsbuddy-simulator-input.md` 第 8 节、`facts/diag-capture-measured.md` 第 2 节 |
| Q-014 | 拔线回合的实际战果（胜/平/负、伤害）能从哪些上下文还原？准确率多少？ | **能，准确。** 两路信号：HDT invoker 转储的 `LastAttackingHero`/`Attack`（重连回合恒为空，必须跳过）；排行榜英雄 `HEALTH-DAMAGE+ARMOR` 差分，重连回合取 END 后 `FULL_ENTITY` 重发结束处。团子有战果的 47 回合推荐流程 47/47、只用排行榜 46/46（+1 幽灵判"非负"）；拔线 9 回合全部还原，有 BB 预测的 7 回合方向 7/7 一致。限制：对手为幽灵时拔线只能判"非负"；中途启用无日志（2026-10-05） | `facts/combat-result-reconstruction.md`、`spikes/hdt-diag-logger/tools/eval_q014_reconstruct.py` |
| Q-007 | 对手玩家级计数器有哪些拿不到？TagTransfer 实际带哪些标签？缺口比例？ | **花费不可见**（27/27 对手为 0）。**TagTransfer 每场都有**；携带 `2358`/`3088`/`3236`/`4639`/`4799`/`3962`/`3670`/`BACON_ELEMENTAL_PLAY_COUNTER`，与 Input 一致。**`2717` 从不在 TF 上**，Input 恒 0，玩家实体 9/27 场有非零（33%）。3.6 附魔、饰品、神祇、英雄技能激活本批可见。手牌/奥秘/`4803`/Volumizer/Malorne/双人的长期 `partial` 比例样本不够，留给 P2-T6 | `facts/diag-capture-measured.md` 第 3–4 节、`facts/bobsbuddy-simulator-input.md` 第 9 节 |
| Q-017 | 简单身材加权摆位规则相对原摆位，能否系统性提高同回合池上的 \(S\)？ | **不能（本批）。** BB 1.85 T3–T7、308 场面、7 策略：无一格 CI 下界>0；均值多为略负；`rev_orig` 显著为负（原摆位好于整板反转）。未覆盖关键词邻接/搜索最优序（2026-10-07） | `facts/positioning-strength.md`、`design/R-positioning-strength.md` |
| Q-018 | 关键词钉位 / 邻接启发 / 有限局部交换，相对原摆位能否系统性抬高同回合池 \(S\)？摆位提示是否值得做？ | **规则：不能 / 不值得做固定提示。** 三规则无一 CI+。**`local_swap_b6`：** 五回合均 CI+（合并 \(\overline{\Delta S}\approx+0.01\)），但同池选序有乐观偏差，**不**直接产品化；若继续则做 H3 留出复核（2026-10-07） | `facts/positioning-keyword.md`、`design/R-positioning-keyword.md` |
