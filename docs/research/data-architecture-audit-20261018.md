# 数据架构复核：应该记录、但现在不完整的项

- **日期：** 2026-10-18
- **性质：** 只读复核（代码 + 文档 + 本机 `data/`），**未改代码、未改数据**
- **分支：** `explore/dummy-ladder`（复核时）
- **说明：** 本文是审计与建议，不是事实条目。引用的现状都有代码/数据/文档依据；推测处标 **[推断]**。

## 0. 结论（先看这个）

1. **战斗快照本身不是主要短板。** 上一次全量质量报告（55 局 / 640 回合，2026-10-05）里，非直接拔线回合 `ready` 为 631/638 = **98.9%**；当前 `data/standard/turns.jsonl` 已到 **933 行**，`strength.jsonl` 池 `1.85.0.0` 有 **663** 个己方场面。
2. **`ready` 只保证“能复现 HDT 当场那次模拟的输入”，不保证“真实对局状态完整”。** 两者被同一个词覆盖了：`ready` 的定义只看单人、有 Combat Input/Output、非中途启用（`tools/standard_layer/status.py:16`）；系统性盲区（对手未知手牌、`2717`、对手花费等）只写 `gapFlags`、**不降级**（`status.py:25–29`）。所以 98.9% 不能回答“我们是否记录了该记录的全部数据”。
3. **真正的缺口分三类：**
   - **上下文没落进标准层**：名次、终局八人排名、规则上下文（畸变/种族/伤害上限/补丁）、英雄名、血量/护甲时间线。很多已经在原始层里，但标准层/引擎没有投影。
   - **非战斗阶段没有结构化**：商店、金币、购买/出售/刷新/三连、英雄技能使用、方向和关键牌标注。原始 `power.log.gz` 有行，但没有解析器；插件也不在购物阶段拍快照。
   - **血缘/质量/版本不完整**：标准层不自包含、原始层分散且最先被删、质量报告过期、最新版本没有同版本重放和团子对照、`schemaVersion` 长期为 1、没有数据字典。
4. **对当前 P3 分位：** 缺的主要不是 Input 字段，而是**名次/规则/样本/验证**；`ready` 指标本身是可信的（P2 有 78/78 对照），但其覆盖面停在 1.85 之前。
5. **对最终目标（P5 决策复盘）：** 现在不够。愿景明确要求“现在就采集当回合金币、酒馆状态和操作事件”（[`early_discussion.md`](../context/early_discussion.md) 第四节），这条**尚未实现**。如果继续只采集战斗快照，P5 会缺“当时有哪些选择”的决策上下文。

## 1. 当前架构（实际在跑的）

| 层 | 物理位置 | 写入者/工具 | 粒度 | 关键内容 |
| --- | --- | --- | --- | --- |
| **L0 原始层** | `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\<时间>_<id>\`；仓库外另有 `data/BgHelperDiag/` 历史归档 | HDT 插件 `HdtDiagLogger` 0.2.0 | 每行 + 战斗阶段快照 | `meta.json`、`records.jsonl[.gz]`、`power.log.gz`、`salt.txt`；记录类型：原始行、`create_game`、`combat_tag`、`combat_phase`、`entities`（开战/战末/局末）、`hdt_bb`（反射转储）、`event`、`perf`、`error` |
| **L1 标准层** | `data/standard/turns.jsonl` + `quality_report.{json,txt}` | `python -m tools.standard_layer` | 每场战斗一行 | `gameId`/`turn`/`combat`、双方英雄（名+CardId）、`inputRef`、Output 摘要、实际战果/伤害/名次、`status`、`gapFlags`、版本 |
| **L2 模拟/战力层** | `data/strength/cache.sqlite`、`data/strength/<pool>/strength.jsonl`、`strength_opp.jsonl`、`score-policy*` | `tools/strength`、`tools/ReplaySim` | 每个场面（side × turn） | 模拟对局缓存、\(S\)/分位/CI/宽度、`simPool`、引擎版本、对照 HDT 五率 |
| **L3 复盘层** | `data/review/<game>/index.html`、`model.json`、`boards/` | `tools/review_view`、`tools/board_render` | 每局 | 时间线、双方分位、双方酒馆等级、阵容 PNG、`notes.json`（只读） |
| **旁路产物** | `data/progress/`、`data/strength/validity_*`、`data/strength/1.85.0.0/score-policy*`、`data/boards*` | 各分析脚本 | — | 趋势图、有效性评估、得分公式搜索结果、阵容图 |

**实际数据流与文档描述的差异：** 架构图说 L1 标准层是 L2 的输入（[`architecture/overview.md`](../architecture/overview.md) 第 1 节），但实际 `tools/strength/pool.py:90–111` 是**重新扫描 L0 原始目录**来收集场面；L1 只提供 `(gameId, turn)` 的状态元数据。复盘页的双方酒馆等级同样是回头重读 L0（`tools/review_view/boards.py:12–34`）。也就是说：**L0 是唯一事实源，L1 不是自包含的**。

## 2. 完整性口径：先区分两件事

| 口径 | 回答的问题 | 当前指标 | 结论 |
| --- | --- | --- | --- |
| **可复现性完整** | 这个快照能不能重跑出 HDT 当场那次模拟的 Input/Output？ | `ready` 98.9%、同版本 roundtrip 261/261、团子 78/78 | 对已覆盖版本**较强** |
| **真实状态完整** | 对局中发生的一切，我们是否都记下来了，且知道哪些不知道？ | 无统一指标；`gapFlags` 只覆盖 4 类 | **弱**，且没有把“未知”系统化 |

举两个例子：

- 对手 `ResourcesSpentThisGame` 在 HDT Input 中恒为 0（游戏不下发），但 `detect_gaps` 没有这个 flag（`tools/standard_layer/gaps.py:29–68`）。标准层无法区分“真的花了 0”与“未知按 0 处理”。
- 对手 `2717`（`FriendlyMinionsDeadLastCombatCounter`）在 TagTransfer 上从不出现；只有“玩家实体上非零、Input 为 0”时才记 `gap_2717_entity_nonzero_input_zero`，且这是观测项，不影响 `ready`。

这两类属于 BB 输入自带的视野盲区，**不应该**为了好看降 `ready`；但应该在标准层有机器可读的 `unknowns` 字段，供 P5 复盘和置信度使用。

## 3. 缺口清单

优先级：**P0** 现在就该补（低成本、影响当前结论/下一步）；**P1** P4/P5 前补；**P2** 鲁棒性与覆盖。

### 3.1 对局级上下文

| ID | 优先级 | 缺口 | 现状与证据 | 影响 |
| --- | --- | --- | --- | --- |
| G-01 | **P0** | **名次（placement）没有写进标准层/复盘层** | 标准层 `placement` 只从团子配对取（`tools/standard_layer/__main__.py:48–50`）；当前 `turns.jsonl` 有 **803/933** 行 `placement=null`（约 86%），只有 130 行非空。原始层已有读取器 `tools/strength/raw_placement.py:37–88`，从 `game_end` 快照读本地玩家 `PLAYER_LEADERBOARD_PLACE`，但**只供 score-search 用（56 局），没有写回标准层/复盘页** | P3-T4 仍只能用 7 局团子名次；复盘页 `#名次` 常显示 `—`；P5 缺主标签 |
| G-02 | **P0** | **终局八人排名/英雄/血量没有落盘** | 排行榜实体在 `entities@game_end` 里齐全，`reconstruct` 只用它算战斗胜负（`result.py:79–92`），`raw_placement` 只读本地玩家名次；没有“本局全部玩家最终名次”记录 | 无法做大厅强度、名次预测、对手分位分层；P5 的“本局定位”缺 |
| G-03 | **P1** | **MMR/隐藏分变化未采集** | 插件 meta 只有版本/时间/错误计数（`GameSession.cs:54–65`），没有 MMR；本机 `BgsLastGames.xml` 结构未分析（[`local-environment.md`](../facts/local-environment.md)） | 愿景要求“可获取的 MMR 变化”；没有它无法验证“决策是否真的提升了水平” |
| G-04 | **P0** | **规则上下文没有进标准层/战力行** | `Anomaly`、`availableRaces`、`DamageCap`、`duos` 在 Input/实体快照里有（[`bobsbuddy-simulator-input.md`](../facts/bobsbuddy-simulator-input.md) 第 2 节），标准行只保留 `duos` 布尔（`__main__.py:74–81`）；`strength.jsonl` 只有 `simPool` 和 `turn` | 参照池无法按“同规则”筛选；复算时无法证明“当时是什么大厅” |
| G-05 | P2 | **座位/大厅玩家身份不保留** | 原始行用匿名化名字，标准层只有每回合对手英雄；没有座位号或跨回合大厅玩家标识 | “幽灵对手”“重复遇到同一对手”只能靠 CardId 猜；不影响当前分位，但影响 P5 的“运气/对局难度”归因 |
| G-06 | P2 | **英雄名缺失且未回填** | 546/933 行 `myHero=null`（早期 `_playerHeroName` 未取到），但 `myHeroCard` 都在；`cards.zhCN.json` 可映射 | 复盘页显示、按英雄分桶都要额外查卡表；对账时多一步 |

### 3.2 非战斗阶段与决策数据（P5 的核心缺口）

| ID | 优先级 | 缺口 | 现状与证据 | 影响 |
| --- | --- | --- | --- | --- |
| G-07 | **P1（建议先决策）** | **商店/金币/操作事件完全没有结构化** | 插件只挂了公开事件：开局/结束/回合开始/奥秘触发/攻击（`DiagPlugin.cs:51–58`）；`entities` 快照只在 `combat_phase` 切换和局末拍（`GameSession.cs:89–95, 185–208`）。购物阶段只有逐行 `power.log.gz`，没有解析器 | 无法回答“这回合该买什么/该升几本/该不该刷”；P5 的方向与关键牌标注缺输入 |
| G-08 | **P1** | **血量/护甲不是时间线** | 标准层只有 BB Output 的 `friendlyHealth`/`opponentHealth`（`combat.py:178–192`），是开战快照有效血量；没有护甲拆分、战后血量、商店阶段掉血（英雄技能/护甲） | P5 归因（决策 vs 运气）需要“每回合开始/结束血线”；现在只能从下一场 Input 反推 |
| G-09 | P1 | **战斗细节只留结果和伤害** | 标准行只有 `result`/`damage`；存活随从、每个随从的伤害/死亡、被谁击杀都没有投影 | “这波为什么输/赢”无法复盘；只能再看原始行或重跑模拟 |
| G-10 | P1 | **方向/关键牌标注没有写入口** | ADR-0013 v1 明确不做方向标注；`notes.json` 只读加载（`review_view/join.py:211–214`），页面没有写入路径 | 愿景的“允许你标注方向选择、关键牌与判断”没有落地 |
| G-11 | P2 | **英雄选择/技能使用/任务饰品选择未结构化** | 英雄技能激活、任务/饰品在 Input 和实体快照里有；但“什么时候用/选了哪个”只在 `power.log.gz` 的行里 | P5 的“升本/技能节奏”复盘缺事件序列 |

**关于原始层的可恢复性：** 上述行为大多**已经写在 `power.log.gz`** 里，所以不是“永久丢失”，而是“没有结构化和校验”。但 P2 的保留策略写明磁盘紧张时**先删 `power.log.gz`**（[`P2-data-capture.md`](../design/P2-data-capture.md) §3.5）；一旦删除，商店/操作就真丢了。因此 G-07 是“要么现在采，要么保证 raw 长期保留”的二选一，建议由所有者决定（见 Q-022）。

### 3.3 模拟输出、未知字段与重跑

| ID | 优先级 | 缺口 | 现状与证据 | 影响 |
| --- | --- | --- | --- | --- |
| G-12 | **P0** | **未知字段没有机器可读表示** | `gapFlags` 是字符串列表，只有 `opp_unknown_hand`、`opp_secrets`、`gap_2717_*`、`duos_input_present`、`anon_player_key`、`no_input`（`gaps.py:29–68`）；没有未知数量、未知类别、对手花费、未支持卡等 | 下游无法判断“这个分位/这条记录哪些输入是不可信的”；P5 无法按可信度过滤 |
| G-13 | **P0** | **模拟质量字段被丢掉** | `output_summary` 只留五率/致死率/次数/伤害中位/有效血量（`combat.py:178–192`）；`myExitCondition`、`damageResults` 分布、`timeAlloted`、未支持交互/异常都没进标准层 | 无法区分“模拟完成”与“超时/不支持的近似”；Q-020 的 `damageResults` 分析只能回读 raw |
| G-14 | P1 | **战斗中重跑/揭示过程没有投影** | 原始层 `hdt_bb` 每次状态变化都 dump（`HdtBobsBuddyProbe.cs:81–145`）；标准层 `pick_combat_bb` 只取最高 `reRunCount` 的一条（`combat.py:104–133`），没有记录重跑次数、揭示了哪些手牌/奥秘 | 复盘无法看“战斗中信息如何改变胜率”；`partial`/置信度也无法据此细化 |
| G-15 | P2 | **对手未知手牌/奥秘只有 flag，没有计数** | `gapFlags` 形如 `opp_unknown_hand:3`（`gaps.py:10–20`），但标准层没有单独的 `unknownHandCount`/`unknownSecretCount` 字段 | 分析时需要解析字符串；统计/分层不便 |

### 3.4 标准层、血缘、质量与版本

| ID | 优先级 | 缺口 | 现状与证据 | 影响 |
| --- | --- | --- | --- | --- |
| G-16 | **P0** | **标准层不自包含** | 行里只有 `inputRef`/`output` 摘要（`__main__.py:52–82`），没有场面、双方 Tier、血量、规则；`tools/strength` 和 `review_view` 都回读 L0（`pool.py:90–111`、`boards.py:12–34`） | raw 一旦被删/移动，标准层不能独立算分位或复盘；也无法做“只有标准层”的分享/迁移 |
| G-17 | **P0** | **原始层分散、无 manifest、无校验** | 至少两个根：仓库 `data/BgHelperDiag` 与 `%APPDATA%\...\BgHelperDiag`；10-05 及之后的新局在后者（[`combat-result-reconstruction.md`](../facts/combat-result-reconstruction.md) 样本说明）。没有记录“哪些局已导入、从哪个根、何时、用什么工具版本”；没有 checksum/大小/备份清单 | 同一局可能重复导入或漏导入；删旧 raw 时无法知道哪些标准行会失效；异地采集/换机时不可复现 |
| G-18 | **P0** | **质量报告过期且分散** | 最新全量 `data/standard/quality_report.*` 是 **55 局 / 640 回合**（2026-10-05）；`turns.jsonl` 已 933 行；1.88.6 的 80 行在 `standard_188_late` 单独报告（6 局、paired=0）；还有 `standard_20261010`、`standard_replay_sample`、`standard_paired7`、`standard_ed11e0` 等多份输出和 `.bak` | 没有单一“当前数据集”与当前质量；回归/对比时容易用错版本 |
| G-19 | **P0** | **最新版本没有同版本重放/团子对照** | 旧报告 `replay.attempted=0`；Q-002 仍 investigating“1.88.6 同版本 roundtrip 尚未跑”；1.88.6 的两批数据（各 6 局）`paired=0`。P2 的 78/78 只覆盖到 1.85 | `ready` 的“可信”结论没有延续到当前主版本；P3 数据质量只能靠 1.85 的旧证据 |
| G-20 | **P0** | **schema 版本没有演进记录** | 插件 0.1.0 → 0.2.0（匿名化修复 + 局末压缩），`schemaVersion` 仍为 1（`GameSession.cs:18, 56`）；导入侧还有键名修复（`combat.py:16–51`），但行里没有 `anonymizerVersion`/`importVersion` | 消费方无法区分“0.1.0 腐蚀过的旧行”和“0.2.0 干净行”；以后改 schema 没有迁移依据 |
| G-21 | P2 | **匿名校验/展示字段混入 token** | 1.88.6 行里见到 `oppHero` 形如 `无限巨龙player_7e690796`（`turns.jsonl` 第 663 行）：这是匿名化后的玩家名 token 与英雄名拼在一起，不是泄露，但会破坏“按英雄名”分组和展示；0.1.0 的键名腐蚀只在导入侧修复 | 按 `myHero`/`oppHero` 分桶会出错；导出/展示需要清洗或改用 CardId |
| G-22 | **P1** | **架构文档没有数据字典** | `docs/architecture/overview.md` 虽然提到 ADR-0015（模拟池），但“最后更新”仍写 2026-10-05；没有 ADR-0016/0017/0019（得分公式）、score-policy、对手分位、dummy-ladder；也没有任何一份“存储 schema/字段清单” | 新人/新 agent 只能从代码反推字段；改 schema 时不知道谁依赖 |

### 3.5 样本覆盖（结构没问题，但不能当作已覆盖）

- 历史实测 27 场：畸变 0、双人 0、Malorne 0、对手 Tavish 装填 0、对手 `4803`/Volumizer/元素额外攻血 0、任务 1、对手奥秘 1（[`diag-capture-measured.md`](../facts/diag-capture-measured.md) §4、§6）。
- `2717`：55/640 回合出现“实体非零、Input 为 0”的不一致（旧报告），最近 1.88.6 两批仍有 10/80、3/73；`opp_unknown_hand` 旧报告 395/640（62%），1.88.6 批次约 2/3 的回合有未知手牌。
- 团子对照只有 7 局；1.88.6 的批次 `paired=0`。P3-T4 的“配对局 n=7”结论没有变（见 `status.md`）。
- 双人模式从未验证；`isDuos` 相关字段和 `DuosInputPlayer` 的采集/解析没有正例。

这些**不影响**“BB Input 能复现 HDT 当场模拟”的现有结论（Q-013 等），但会限制“分位/名次/决策”的外推。应该登记为**覆盖缺口**，而不是当成已记录。

## 4. 建议补法（按优先级）

### P0：现在就能做，且大多不需要改插件

1. **从原始层提取对局级事实**：终局排行榜 → `placement`、八人名次/英雄/血量；每场战斗前后的排行榜血量 → HP/护甲时间线。`power_replay.py` 与 `tools/strength/raw_placement.py` 已有本地玩家名次的读取基础，只差标准层投影与“八人”扩展。
2. **规则块进标准层和战力行**：`anomaly`、`availableRaces`、`damageCap`、`duos`、`hdtVersion`、`hearthDbVersion`、`hearthstoneBuild`、`simPool`。这是“可复算”和“同规则参照池”的最小集。
3. **机器可读完整性**：`unknowns`（分类计数：未知手牌/未知奥秘/`2717`/对手花费/未支持卡）、`simQuality`（`exitCondition`、`simulationCount`、是否超时、`damageResults` 摘要）、`rerunCount`。`ready` 保留原定义，作为“可复现性”字段；另加 `stateCompleteness`（`complete`/`partial`/`blindSpots`）。
4. **标准层自包含**：至少把 `board`（双方随从列表/顺序）、`tier`、`hp`、`rules`、`unknowns` 写进行；或者明确“标准层永远依赖 raw 归档”，并给 raw 做 manifest + 校验 + 保留承诺。两者选一，写进 ADR。
5. **单一 canonical 数据集**：`data/standard/current/`（或 `dataset.json`）指明当前使用的 turns/strength/quality 版本；不再以多份 `standard_*` 目录并存作为常态；质量报告每次导入自动重生成。
6. **补当前主版本验证**：1.88.6 同版本 roundtrip（Q-002 收尾）+ 至少 1 局团子对照；把结果写进 `facts/`，并让质量报告记录 “validatedVersions”。
7. **schema 演进**：插件版本、匿名化版本、导入版本、schemaVersion 一起写进每行/每文件；补一份 `docs/architecture/data-model.md`（字段、来源、时机、未知语义、消费者）。

### P1：P4/P5 前

8. **购物阶段结构化事件**（G-07）：`turn_start(shopping/combat)`、金币、酒馆等级、商店 5 张、购买/出售/刷新/三连、英雄技能使用、任务/饰品选择。最小实现可以先只记事件和关键数字，不解析全部 power 行。
9. **血量/伤害时间线**（G-08）与**战斗细节**（G-09）：每回合 begin/end HP、护甲、商店阶段掉血；战斗后存活随从和每随从伤害。
10. **标注写入口**（G-10）：`notes.json` 升级为可写的 `annotations.jsonl`（方向、关键牌、判断），复盘页只读渲染；需要新 ADR 取代/补充 ADR-0013 的“v1 不做方向标注”。

### P2：鲁棒性

11. 收集覆盖正例：畸变、双人、Malorne、Tavish、对手奥秘、`4803`/Volumizer；`2717` 双处记录（TF + 玩家实体）；对手花费显式 `unknown`。
12. 处理 G-17/G-18/G-20/G-21：manifest、备份、单一输出、schema 迁移说明、匿名化残留清理。

## 5. 对现有结论的影响

- **不推翻** ADR-0003 / ADR-0011 / ADR-0015：分位定义、留一局循环赛、模拟池的结论仍成立；它们依赖的是“Input 可复现”，这一点没变。
- **限制** P3-T4 与任何“名次/决策”结论：名次标签只有 7 局团子配对；标准层不能独立给出名次；P5 需要的商店/金币/操作数据没有结构化。
- **P4 实时集成**不受直接阻塞（它需要当前 Input 和分位缓存），但会继承 G-16/G-17 的数据血缘问题。
- **P5**被 G-07/G-08/G-10 直接阻塞；其中 G-07 是“现在补 vs 以后从 raw 解析”的范围选择，建议所有者先定。

## 6. 需要所有者决定

1. **Q-022（新增）：** P5 的经济/操作数据是否在 P4 之前补成结构化事件，还是只保证 `power.log.gz` 长期保留、以后再解析？
2. 标准层是**自包含**（冗余存 board/tier/hp/rules）还是**明确依赖 raw 归档**（轻量、但必须做 manifest/备份）？
3. 名次/MMR 是否现在就要（影响 P3-T4 和“水平是否提升”的验证），还是 P5 再说？

## 7. 复核方式

- 本机 `data/standard/turns.jsonl`：933 行；`placement=null` 803 行；`myHero=null` 546 行；`bbVersion=1.88.6.0` 277 行（grep 统计，2026-10-18）。
- `data/standard/quality_report.json`：55 局 / 640 回合，`ready` 631、`missing` 9，`replay.attempted=0`，`gapPositives` = `opp_unknown_hand` 395、`gap_2717_entity_nonzero_input_zero` 55、`no_input` 9。
- `data/standard_188_late/quality_report.txt`：6 局 / 80 回合，`paired=0`，`gap positives` 49 + 10。
- `data/standard_20261010/quality_report.txt`：6 局 / 73 回合，`paired=0`，`gap positives` 51 + 3。
- 代码位置见各表“证据”列；文档位置见文内链接。
