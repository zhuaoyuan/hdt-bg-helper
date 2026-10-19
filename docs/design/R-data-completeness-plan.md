# 方案：数据完整性候选计划项重评

- **状态：** partially implemented（C1–C4 已实施，2026-10-19/20；C5–C15 未动，Q-022 暂缓）
- **任务：** 横切数据完整性（不单独属于 P3/P4 任务）
- **作者 / 日期：** agent / 2026-10-19；实施记录追加 2026-10-20
- **相关：** [`research/data-architecture-audit-20261018.md`](../research/data-architecture-audit-20261018.md)（缺口清单）、Q-022、[`status.md`](../status.md)、[`raw_placement.py`](../../tools/strength/raw_placement.py)
- **基线：** `main`；实施后 `data/standard/turns.jsonl` **144 局 / 1724 回合**；`strength.jsonl` 池 `1.85.0.0` 663 个己方场面；团子配对 18 局；1.88.6 同版本 roundtrip 978/978。

## 1. 目标与非目标

**目标：** 把“数据完整性”候选重新按 **价值 / 成本 / 数据是否已经存在** 排序，回答三个问题：

1. 现在做哪些，能直接改善 P3 的结论（尤其是 T4 的样本量）？
2. 哪些只是“以后有用”，现在做会分散注意力？
3. 哪些根本不可行，应该从计划里删掉？

**非目标：**

- 不重新讨论分位定义、得分公式、模拟池（ADR-0003 / 0011 / 0015 / 0019 不动）。
- 不承诺“完整八人排名”（见 §3 C9）。
- 不把 P5 的经济/操作数据默认塞进 P4 之前（Q-022）。
- 不在本方案里实现；只给候选、顺序、验收。

## 2. 重新评估的依据（相对 2026-10-18 审计的变化）

1. **“完整八人排名”已判定不可行。** `PLAYER_LEADERBOARD_PLACE` 只在玩家出局时确定；自己提前出局后，剩余玩家的名次不在本局日志里。HDT 自己结束对局时也只取本地 `FinalPlacement`，大厅英雄只收 DbfId、不收名次（`Hearthstone Deck Tracker/GameEventHandler.cs:1069–1084`）。因此 G-02 从“P0 可补投影”降级为“部分不可得”。
2. **本地名次（G-01）是最高 ROI 的单项。** `tools/strength/raw_placement.py` 已能从 `game_end` 快照读出本地玩家最终名次，score-search 已用过 **56 局**；但标准层仍只从团子取（7 局）、`turns.jsonl` 有 803/933 行 `placement=null`。把它投影进标准层，预计能把 P3-T4 的 `n` 从 7 提到 **50+**，直接重开 P3 退出标准第 3 条。这是“数据完整性”里唯一能改变 P3 结论的项。
3. **规则上下文（G-04）已在 raw 里，投影成本低。** `availableRaces` / `Anomaly` / `DamageCap` / `duos` 在 Input 或 `entities@combat_start` 的 context 里；标准层只留了 `duos` 布尔。补上它不会改变当前分位，但让“同规则”筛选和复算成为可能。
4. **标准层“自包含”不是唯一的解。** raw 是唯一事实源；与其把 board/tier/hp 冗余进标准层（G-16），更小的承诺是 **thin standard + raw manifest/备份/保留**（C7）。完整自包含应作为一个 ADR 取舍，不是默认 P0。
5. **dummy-ladder v2 不改变数据需求。** 它证明绝对值读数可用，但没有新增数据字段需求；不进入本计划。
6. **当前主版本验证仍是断的。** 1.88.6 同版本 roundtrip 未跑、1.88.6 两批 `paired=0`；不管补多少字段，没有这一步就不能说“当前版本的数据可信”。

## 3. 候选重评

成本按 agent 工作时间粗估；价值分 P3（当前分位/退出标准）、P4（实时）、P5（决策复盘）。**结论**列是本次重评的建议。

| # | 候选 | 数据是否已存在 | 价值 | 成本 | 风险 / 依赖 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | **本地最终名次投影**（G-01） | 已在 raw（`raw_placement`，56 局） | **P3 高**、P5 中 | 小（读取 + 行字段 + 回填） | 与团子名次语义需对齐；只在有 `game_end` 时可用 | **立即** |
| C2 | **规则块**：`availableRaces`/`Anomaly`/`DamageCap`/`duos`/`hearthDbVersion`/`build`（G-04） | 已在 Input/context/meta | P3 中、P5 中 | 小 | 旧插件/旧局可能缺；用 null 显式表示 | **立即** |
| C3 | **单一 canonical 数据集 + 质量报告刷新**（G-18） | 否（多份 `standard_*`/`.bak`） | P3 中、可复算高 | 小～中 | 要定“当前数据集”是谁；不动历史输出 | **立即** |
| C4 | **1.88.6 同版本 roundtrip + 团子对照**（G-19） | 工具已有；DLL/团子数据依赖 | P3 高 | 小（roundtrip）；团子需所有者提供新局 | 本机无 1.88.6 团子文本时只能做 roundtrip | **立即（roundtrip）；团子等新局** |
| C5 | **`unknowns`/`simQuality`/`rerunCount` + schema 版本**（G-12/G-13/G-20） | 部分在 raw；部分要新增投影 | P5 中、置信度高 | 中 | 字段设计别一次做全；先做分类计数 | **立即（最小版）** |
| C6 | **血量/护甲时间线**（G-08） | 已在 `entities@combat_start/end` | P5 中 | 小～中 | 商店阶段掉血仍缺口；只能给战斗边界 | 下一批 |
| C7 | **raw manifest / 备份 / 保留承诺**（G-17） | 否 | 可复算高、P5 中 | 小～中 | 要所有者定存储位置；离线采集机怎么办 | 下一批（与 C3 绑定） |
| C8 | **数据字典 + 架构同步**（G-22） | 否 | 维护性高 | 小～中 | 需要每次 schema 变化同步 | **立即（最小版：新字段表）** |
| C9 | **完整八人排名**（G-02） | **不可得** | P5 高但无数据 | 大（需新来源） | 客户端不提供剩余玩家名次；HDT stats 也没有 | **砍（除非找到新来源）** |
| C10 | **购物阶段结构化事件**：金币/商店/买卖/刷新/三连/技能（G-07） | 只在 `power.log.gz` 行里 | **P5 高** | 大（插件 + 解析） | 依赖 Q-022；不保证能完整解析 | **等所有者决定（Q-022）** |
| C11 | **方向/关键牌标注写入口**（G-10） | 否 | P5 高 | 中 | 需要新 ADR 取代 ADR-0013 的 v1 边界 | 等 P5 启动 |
| C12 | **战斗细节**：存活随从/每随从伤害（G-09） | raw 行 + 战末快照可部分重建 | P5 中 | 中～大 | 解析复杂；对当前分位无影响 | 缓 |
| C13 | **MMR / 隐藏分** | 未验证 | P5 中 | 中（先 spike） | 可能只有本地历史文件；不适合直接排期 | 只做 spike，不列交付 |
| C14 | **标准层完全自包含**（G-16） | 否 | 可复算高 | 大（冗余 + 一致性） | 与 C7 二选一；需 ADR | 缓（优先 thin + manifest） |
| C15 | **覆盖样本**：畸变/双人/Malorne/Tavish/奥秘 | 靠打局 | 外推有效 | 所有者时间 | 不可控；插件路径已支持 | 观察项，不排期 |

## 4. Wave 1：可复现的最小完整集（现在做）

**原则：** 只做“raw 已有 + 投影/校验”能完成的事，不改插件。

| 交付 | 内容 | 验收 |
| --- | --- | --- |
| W1-1 名次 | 标准层行/局级表写入本地最终 `placement` + `placementSource`（`raw_lb` / `tuanzi`）；7 局团子对照 | 有 `game_end` 的局都有值；7 局 raw vs 团子一致；P3-T4 重跑并报告新 `n` 与结论 |
| W1-2 规则 | `rules` 块写进标准层（`availableRaces`/`anomaly`/`damageCap`/`duos`）与 `strength` 行（至少 `simPool` + `hdtVersion` + `hearthDbVersion` + `build`） | 抽取 10 局人工/自动对照 Input；缺失显式 null，不填默认值 |
| W1-3 数据集 | `data/standard/current.json`（或等价 manifest）：指向 canonical turns/strength/quality 的版本、生成时间、工具版本、游戏数 | 质量报告与 turns 行数一致；旧 `standard_*` 标为历史，不再当入口 |
| W1-4 验证 | 1.88.6 同版本 roundtrip；质量报告记录 `validatedVersions` | 报告 `replay.attempted > 0` 且通过；失败样本列入报告 |
| W1-5 完整性字段 | `unknowns`（未知手牌/未知奥秘/`2717`/对手花费/未支持卡计数）、`simQuality`（`exitCondition`/`simulationCount`/是否超时/`damageResults` 摘要）、`rerunCount`；标准层 schemaVersion 递增 | 字段可被 `review_view`/质量报告读取；旧行有默认/空值，不崩 |
| W1-6 数据字典 | 新字段写进 `docs/architecture/data-model.md`（来源、时机、未知语义、消费者） | 文档与代码字段一一对应；后续 schema 变化必须更新 |

**预期结果：**

- P3-T4 的样本从 7 局增加到 **50+**，P3 退出标准第 3 条可以真正重评（这是本轮最大收益）。
- 复盘页能显示名次/规则；以后任何“同规则参照池”都有字段基础。
- 数据血缘可查：知道当前 turns/strength 是哪次导入、哪个 raw 根。

**不做：** 不实现 InputBuilder，不把 board 冗余进标准层，不改 `strength.jsonl` 的分位算法。

## 5. Wave 2：P4/P5 前的低成本补强

1. **C6 血量/护甲时间线**：从 `entities@combat_start/end` 抽双方 HP/护甲（战斗边界；商店阶段掉血仍缺失，明确标注）。
2. **C7 raw manifest/备份**：每个 raw 局记录来源根、文件大小/哈希、导入状态；给“删哪份 raw 会破坏哪些标准行”一个索引。
3. **C12 战斗细节**（可选）：先做“存活随从 + 双方伤害”摘要，不做逐事件重放。
4. **C15 覆盖监控**：质量报告继续统计畸变/双人/奥秘/任务/Trinket 正例，不排期。

## 6. Wave 3：P5 启动时再定

- **C10 经济/操作**：Q-022 决定“现在采”还是“只保 raw”。若现在采，优先事件级最小集（回合阶段、金币、Tier、商店 5 张、买/卖/刷新/三连），不追求完整 power 解析。
- **C11 标注写入口**：单独 ADR，和复盘 UI 一起做。
- **C13 MMR**：先 spike 找源；找不到就保持 `unknown`。

## 7. 明确砍掉 / 降级的候选

| 候选 | 处理 | 理由 |
| --- | --- | --- |
| C9 完整八人排名 | **砍**（从 P0 删除） | 客户端结束时不提供剩余玩家名次；HDT 自身也只存本地 FinalPlacement。除非找到新来源（观战续记/第三方 API），否则不做 |
| C14 标准层完全自包含 | **缓** | 与 C7 二选一；优先 thin standard + raw manifest。若将来 raw 必须离线归档，再写 ADR 决定是否冗余 |
| C10 经济/操作 | **等 Q-022** | 成本最大、对 P3 无直接收益；不能在未决定前默认排期 |
| C15 覆盖样本 | **不排期** | 靠所有者遇到时自然采集；插件已支持 |

## 8. 对现有结论的影响

- **P3-T4**：W1-1 是唯一可能把 `n=7` 提升到可用样本的改动；如果 raw 名次覆盖 50+ 局，退出标准第 3 条应重跑，不再写“无法判定”。
- **P3 分位本身**：不变；W1 只补标签/上下文，不改 `strength.jsonl` 的 S/Q。
- **P4**：不受阻塞；但 W1-3/W1-6 让以后升级/迁移有据可查。
- **P5**：仍被 C10/C11 阻塞；本计划只把“决策复盘需要的非战斗数据”作为待决项，不假装已覆盖。

## 9. 需要所有者决定

1. **Wave 1 是否按本方案执行？**（尤其是 W1-1 名次投影 + W1-4 1.88.6 验证）
2. **Q-022**：经济/操作数据现在采，还是只保证 raw 保留？
3. **C7 的 raw 保留位置/备份策略**：仓库外目录、离线采集机、保留多久？
4. **C13 MMR** 是否值得先花半天 spike 找源？

## 10. 验收总表（可执行）

- `python -m tools.standard_layer` 重新导入后：`turns.jsonl` 有 `placement`、`rules`、`unknowns`、`simQuality`；`quality_report` 的 games/turns 与文件一致。
- 7 局团子对照：raw `placement` 与团子 `place` 全部一致（或列出不一致样本）。
- `python -m tools.strength_validity`（或现有 T4 命令）重跑：输出新的 `n_games`、placement 相关 verdict；与旧 `n=7` 对比。
- 1.88.6 roundtrip：`attempted > 0`、`within3sigma` 全部通过；失败样本有记录。
- `docs/architecture/data-model.md` 覆盖新字段；`status.md` 与本计划同步。

## 11. 附：C5 与 C8 到底是什么

这两项容易被误读成“再加两个字段/再写一篇文档”，其实解决的是不同问题。

### C5：让“这条数据可不可信”变成字段

现在标准层一行大概是：

```json
{
  "status": "ready",
  "gapFlags": ["opp_unknown_hand:3"],
  "output": {"simulationCount": 19998, "winRate": 0.51, "...": "..."},
  "inputRef": {"lineSeq": 3213, "reRunCount": 0}
}
```

问题：

- `ready` 只回答“有 Input/Output”，不回答“模拟跑完没有、有没有未支持交互、输出了多少条伤害分布”。
- `gapFlags` 是给人看的字符串，只能靠解析 `opp_unknown_hand:3` 才知道数量；而且没有对手花费、未支持卡、`2717` 双处不一致等类别。
- `inputRef.reRunCount` 只是**选中那条 dump** 的重跑计数；标准层不记录“这场战斗中途更新过几次、揭示过什么”。
- 旧行（插件 0.1.0）和新行（0.2.0）混在一起，没有 `importVersion`/`anonymizerVersion`，无法按来源过滤。

C5 把这些变成机器可读字段，例如：

```json
"unknowns": {
  "oppUnknownHand": 3,
  "oppUnknownSecrets": 1,
  "oppResourcesSpentUnknown": true,
  "counter2717Mismatch": true,
  "unsupportedCards": []
},
"simQuality": {
  "simulationCount": 9996,
  "exitCondition": "CompletedSimulations",
  "lowSample": false,
  "timeout": false,
  "unsupportedInteraction": false,
  "damageResultsAvailable": true
}
```

**用途：** 复盘页可以显示“这回合结论基于 3 张未知手牌”；P5 可以按可信度过滤；质量报告可以自动统计“多少回合是超时/低样本”。它**不改变分位**，只改变“我们敢不敢把这个分位当完整数据用”。

### C8：把“字段契约”写下来

现在字段只存在于代码/`turns.jsonl` 里：`placement`、`gapFlags`、`status`、`inputRef`、`output` 各是什么含义、什么时候写、`null`/`0` 是“无”还是“未知”、谁在消费，没有一处集中说明。

C8 要的是一张表，例如：

| 字段 | 层 | 来源 | 何时写 | `null`/`0` 的含义 | 消费者 |
| --- | --- | --- | --- | --- | --- |
| `placement` | 标准行/局级 | `game_end` 排行榜 / 团子 | 导入时 | `null` = 没有 `game_end`；不是“第 0 名” | T4、复盘页 |
| `availableRaces` | 规则块 | Input/`entities` context | 导入时 | `null` = 内存读取失败/未初始化；不是“没有种族” | 参照池筛选、复盘 |
| `gapFlags` | 标准行 | `gaps.py` | 导入时 | 字符串列表；`0`/缺失含义见对应 flag | 质量报告 |
| `simQuality` | 标准行 | Output/invoker dump | 导入时 | `exitCondition` 空 = 未记录 | 复盘、质量门 |

同时把 `docs/architecture/overview.md` 与 ADR-0015/0016/0017/0019、score-policy、对手分位、`strength.jsonl` 的关系同步。

**用途：** 以后加字段时知道谁依赖；删 raw、改 `gapFlags`、换分位公式时知道会影响哪些下游。**不写代码，但决定 C5 加的字段会不会又变成“代码里有、没人知道含义”的黑盒。**

### 关系与优先级

- **C5 是“数据内容”，C8 是“数据说明书”**；C5 不加字段的话，C8 只能记录旧缺口；C8 不写的话，C5 的新字段又会变成新的黑盒。建议同一个 PR 做。
- 它们**不是 P3-T4 的前提**：要更瘦的 Wave 1，可以先做 C1–C4，C5 只做 `unknowns` + `simQuality.exitCondition` 最小版，C8 只写新增字段表，不重写整个架构文档。

## 12. 实施记录（2026-10-19/20，C1–C4）

所有者 2026-10-19 决定：Q-022 暂缓；Wave 1 只做 C1–C4。C5/C8 及以后未动。

### C1 本地终局名次：已实施

- 新增 `tools/standard_layer/placement.py`：从 `game_end` 实体快照读本地英雄的 `PLAYER_LEADERBOARD_PLACE`；`0`/缺失按未知处理，不写成“第 0 名”。
- 标准行新增：`placement`（优先团子，团子内部不一致时回退 raw）、`placementRaw`、`placementTuanzi`、`placementTuanziValid`、`placementSource`（`tuanzi` / `raw_lb`）。
- 结果（`data/standard/turns.jsonl`，144 局 / 1724 回合）：`placement` 1724/1724，`rawVsTuanzi` 14/18，`tuanziInconsistent=1`（`20261005_070312_6ab052`：团子写第 1 名，但该局第 10 回合“我被抬走”，回退 raw=6）。
- **重要限制：** 原始 `PLAYER_LEADERBOARD_PLACE` 是**动态名次**，不是每局都等于最终名次；3 局 raw 与团子仍差 1 名（`20ad61` 5/4、`ed11e0` 6/5、`d7b573` 4/3），原因未定。`placementRaw` 只能当近似标签。
- T4 重跑（`maxTurn=12`，B/perm=2000）：
  - 1.85：n=31，分位 vs −名次 rho **0.070**（p=0.707）；HDT 五率 vs −名次 rho **0.507**（p=0.0036）。
  - 1.88.6：n=25，分位 rho **0.277**（p=0.179）；HDT rho **0.678**（p=0.0002）。
  - `exit3`：两版均 **fail**（不再是 sample insufficient）；1.85 的 tuanzi-only 敏感性 n=13、rho 0.069，方向不变。
  - **结论：** 样本量补上后，P3-T4 退出第 3 条从“无法判定”变为“未通过”；ADR-0003 的材料是“建议讨论推翻”，不是自动推翻。

### C2 规则块：已实施

- `tools/standard_layer/combat.py` 新增 `rules_block`：`availableRaces`（Input 的序列化 `List<Race>` 已归一成字符串数组，context 兜底）、`anomalyDbfId`、`damageCap`、`duos`；缺失保持 `null`。
- 标准行 `meta` 增加 `hearthDbVersion`、`hearthstoneBuild`；`rules` 覆盖：race 1724/1724、anomaly 0、damageCap 1710/1724、duos 0。
- `tools/strength/pool.py` 把 `rules`/`meta` 带进 `Board.label`；`engine.evaluate_candidate` 输出 `rules`、`rulesSource=engine`、`versions`。
- 已有 `strength.jsonl` 用 `tools/strength/backfill_rules.py` 迁移：663/663 行补上 `rules`/`versions`/`rulesSource=standard_layer`，迁移前后 S/分位/CI 等 identity 字段哈希不变。

### C3 canonical 数据集 + 质量报告：已实施

- `tools/standard_layer` 每次导入写 `data/standard/dataset.json`：版本、生成时间、roots、turns/quality 的 sha256/大小、counts、placement、rules、versions。
- 质量报告刷新为 **144 局 / 1724 回合**（旧 55 局/640 回合报告保留为历史）；`ready` 1710、`missing` 14、`ready`（非直接拔线）99.4%、团子 strict 204/204。
- 旧 `data/standard_*` 目录保留为历史，不再作为 canonical 入口；入口是 `data/standard/dataset.json` + 同目录 turns/quality。

### C4 1.88.6 同版本 roundtrip：已实施

- 从 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag` 读 1.88.6 局，`BobsBuddy.dll` = `C:\Program Files\HDT`（1.88.6.0）。
- **978/978 场通过**（81 局，3σ）；JSON：`data/strength/roundtrip_188_full.json`。
- 1.88.6 的团子文本仍缺（这 81 局 `paired=0`），所以“团子对照”未做；同版本 Input→Output 往返已不是缺口。

### 未完成 / 发现

- C5/C8 未做（所有者只批准 C1–C4）；Q-022 暂缓。
- C1 的 3 局 raw/tuanzi 差 1 名未解释；`PLAYER_LEADERBOARD_PLACE` 动态语义需要补事实/校验后再把 `placementRaw` 当强标签。
- T4 的负结果需要所有者决定：改指标/放宽、还是先修名次标签再重跑。


