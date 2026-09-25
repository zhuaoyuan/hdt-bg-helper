# 方案：诊断记录插件（diagnostic logger）

- **状态：** review
- **任务：** P1-T3、P1-T5 的实测依据；兼作 P2-T2 / P2-T3 的原型
- **作者 / 日期：** agent / 2026-09-25
- **相关：** ADR-0004（proposed）、ADR-0006、ADR-0007；Q-002、Q-006、Q-007、Q-009、Q-011、Q-013；`facts/bobsbuddy-simulator-input.md`

## 1. 目标与非目标

**目标：** 写一个 HDT 插件原型。所有者带着它正常打几局酒馆战棋，插件在本机尽可能完整地记录每场战斗的数据。事后 agent 离线分析这些记录，用来：

- 逐个核对数据清单里的字段：从我们自己能拿到的实体数据里，能不能推出 HDT 实际交给 Bob's Buddy 的值；
- 实测 Q-002（反射读 HDT 的模拟输入）、Q-006（战斗中揭示的信息与时序）、Q-007（对手数据缺口）；
- 为 Q-009 / Q-011 / Q-013 提供真实场面，这些实验在独立进程里离线做；
- 为 P2-T1 确定采集时机、数据模型和体积。

**非目标：**

- 不做数据投影、完整性判定、分位计算，插件里也不跑模拟；
- 不做 UI，只在 HDT 插件列表里提供启用和停用；
- 记录格式不承诺兼容，这是原型（`spikes/`），不是正式代码；
- 只支持单人模式。双人模式照常记录，但不保证覆盖。

## 2. 依据

- 插件每收到一行 Power.log，都是在 HDT 处理完同一行之后，在同一线程上同步回调（`LogEvents.OnPowerLogLine`）。以 `GameState.` 开头的行等少数几类不经过这个回调（`facts/bobsbuddy-simulator-input.md` 第 8 节第 2 条）。
- 实体模型是公开的（`Core.Game.Entities` 等），但 HDT 的 BLOCK 解析上下文是私有的，插件要自己跟踪 BLOCK（第 8 节第 3、4 条）。
- 没有"战斗开始"事件。单人模式是标签 `2022` 由 1 变 0；公开属性 `GameV2.IsBattlegroundsCombatPhase` 在同一处置真（第 8 节第 5 条，第 5.1 节）。
- HDT 的模拟输入在 `internal class BobsBuddyInvoker` 的私有字段 `_input` 里。实例存在私有静态字典 `_instances` 里，键为 `"{gameId}_{turn}"`。结果在公开属性 `Output` 上（基线 `BobsBuddyInvoker.cs:30, 57, 94, 135`）。战斗中 HDT 会修改 `_input` 并重跑，所以只在开战时读一次不够（第 5.2 节）。
- 可用种族不在日志里，要调用 `BattlegroundsUtils.GetAvailableRaces()` 读内存（第 8 节第 7 条）。
- 官方 HDT 装在 `%LOCALAPPDATA%\HearthstoneDeckTracker\app-<版本>\`，插件目录是 `%APPDATA%\HearthstoneDeckTracker\Plugins`，HDT 自带 `Newtonsoft.Json.dll` 13.0.3（`facts/local-environment.md`，2026-09-25 核实）。
- Hearthstone 自己按会话保留日志目录（本机 `C:\Program Files (x86)\Hearthstone\Logs\` 下有 6 个），每个会话的 Power 日志 26–400 MB（2026-09-25 核实）。**[推断]** 一局酒馆战棋的原始行可能达到几十 MB，所以原始行要压缩。
- 依赖的未决问题：如果反射读不到 `_input`（Q-002 失败），第 3.3 节的记录就缺失。这时仍然能完成原始行和实体快照的记录，只是字段核对要改为和 Bob's Buddy 输入的源码逻辑比，而不是和 HDT 的实际值比。

## 3. 方案

### 3.1 组成

新建 `spikes/hdt-diag-logger/`，以 `spikes/hdt-plugin-skeleton` 为起点：

| 组件 | 作用 |
| --- | --- |
| `DiagPlugin` | 实现 `IPlugin`，注册事件；所有回调都包 `try/catch`，异常只写进自己的记录，绝不抛给 HDT |
| `LineTracker` | 在 `OnPowerLogLine` 里给每行编号（`lineSeq`），跟踪 BLOCK 栈，识别标签 `2022` / `3533` 的变化 |
| `Probes` | 在关键时刻读取数据：实体快照、HDT 的 Bob's Buddy 状态、可用种族、版本信息 |
| `ReflectionDumper` | 把任意对象图转成 JSON 树（见 3.4） |
| `RecordWriter` | 后台线程写文件；回调线程只把数据放进队列 |
| `Anonymizer` | 落盘前替换 BattleTag（见 3.5） |
| `tools/check_capture.py` | 离线覆盖率报告（见第 5 节） |

### 3.2 记录什么、什么时候记

每局一个目录：`%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\<开局时间>_<短 id>\`。

| 文件 / 记录类型 | 时机 | 内容 |
| --- | --- | --- |
| `meta.json` | 开局、结局 | schema 版本、插件版本；HDT、BobsBuddy、HearthDb 的程序集版本；炉石客户端版本（能拿到的话）；Hearthstone 日志目录路径；开局和结局时间 |
| `power.log.gz` | 每行 | `lineSeq`、接收时间、原始行（已匿名化），gzip 流式写入 |
| `records.jsonl` → `event` | 发生时 | `GameEvents` 的开局、结局、回合开始、对手奥秘触发、攻击等公开事件，带 `lineSeq` |
| `records.jsonl` → `combat_flag` | 每行检查 | `IsBattlegroundsCombatPhase` 变化、标签 `2022` / `3533` 变化，带 `lineSeq` |
| `records.jsonl` → `entities` | 战斗开始（`IsBattlegroundsCombatPhase` 变为真的那一行）；回合开始（上一场战斗结束后） | `Core.Game.Entities` 全部实体：`Id`、`CardId`、全部标签（名字和值，无名标签用数字）、`EntityInfo` 的公开字段；双方 `Player` 各列表的实体 id；可用种族、畸变 |
| `records.jsonl` → `hdt_bb` | 每行和每次 `OnUpdate` 检查当前回合的 `BobsBuddyInvoker`；它的 `_state`、`Output` 引用或重跑次数变化时记一次 | `_input` 的对象图、`Output`（含 `damageResults`）、`_state`、重跑次数、攻防英雄等私有标量字段 |
| `records.jsonl` → `perf` / `error` | 周期性、出错时 | 各回调耗时统计、快照和序列化耗时、队列长度；异常信息 |

每条记录带 `lineSeq`，可以把"HDT 状态在第几行变化""插件在第几行拍了快照"排出先后。这正好用来实测第 8 节第 8 条：标签变化触发的动作是不是排队后才执行的。

### 3.3 线程与一致性

- 实体快照和 `_input` 序列化在日志线程（`OnPowerLogLine` 回调）里同步完成：HDT 也在这个线程上修改实体和 `_input`，同步读才能拿到一致的状态。读完的 JSON 树交给后台线程写盘。
- `OnUpdate`（UI 线程）只检查 `Output` 引用是否变化，并做一个标记，真正的序列化推迟到下一行日志的回调里做。战斗结束后日志行变少，可能要等几百毫秒，可以接受。
- **[推断]** HDT 自己的模拟任务在后台读 `_input`，同时日志线程可能修改它，我们的读取和 HDT 有同样的竞争。记录里带上 `_state` 和重跑次数，分析时可以识别出这种情况。

### 3.4 对象图序列化

- 只读**字段**（公开和私有，含自动属性的后备字段），不调用属性的 getter：getter 可能有副作用或开销很大。
- 基本类型、字符串、枚举直接写；集合按元素展开；其他对象分配 `$id`，第二次遇到时写 `$ref`，防止循环引用；限制最大深度和单个集合的元素数，超限时写明被截断。
- 按类型黑名单跳过已知的大对象（如卡牌数据库、`Simulator`、委托、`Task`）。黑名单第一次实跑后再调整。
- 反射得到的 `FieldInfo` 按类型缓存。
- 用 HDT 自带的 `Newtonsoft.Json` 输出（编译时引用，`Private=false`）。

### 3.5 隐私与存放位置

- 记录目录在仓库之外。记录里含 Bob's Buddy 的内部字段名，按 ADR-0006 的约束不入库。
- `AGENTS.md` 规定本地存储也要匿名化：原始行、实体快照、`_input` 里所有 `名字#数字` 形式的 BattleTag，以及玩家实体的名字，都替换成 `player_<加盐哈希前 8 位>`。盐每台机器生成一次，存在记录目录里，不入库。同一个人在不同对局里映射成同一个占位符，便于分析。
- 写进仓库的分析结论只放统计数字和匿名化的摘录。

### 3.6 构建

- `HdtDir` 默认值改成官方版路径。官方版目录名随版本变化（`app-1.58.3`），所以另写 `build.ps1`：自动找最新的 `app-*` 目录，编译后复制到插件目录。
- 在插件列表里的显示名是 "BG Helper Diagnostic Logger"。

## 4. 考虑过的替代方案

| 方案 | 为什么没选 |
| --- | --- |
| 不写插件，事后直接复制 Hearthstone 的 Power.log | 拿不到 HDT 实际的模拟输入、可用种族（在内存里）、HDT 状态变化的时序；原始日志已经包含在本方案里 |
| 只序列化 HDT 的 `_input` | 没法评估"我们自己采集"这条路，而 P2 正是要走这条路 |
| 只在战斗开始时拍快照 | 漏掉战斗中的补录和重跑（第 5.2 节），正是要实测的部分 |
| 用 Newtonsoft 的默认序列化直接输出对象 | 会调用 getter，遇到循环引用和巨大对象图会失控 |
| 插件里直接跑 Bob's Buddy | 违反 ADR-0004 的"采集轻量"原则；离线在独立进程里跑即可 |

## 5. 验收方式

所有者打 1 局后先做一次检查，通过后再打剩下的 3–5 局。

1. **加载：** 官方 HDT 能加载并启用插件，HDT 日志里有插件的版本行；停用后不再写记录。
2. **不影响 HDT：** HDT 自己的 Bob's Buddy 面板照常出结果；所有者没有感觉到卡顿；`perf` 记录里单行回调耗时中位数和 p99、单次快照和序列化的耗时都写进报告（第一局之后再定上限，初步期望单次快照 < 50 ms）。
3. **覆盖率：** `check_capture.py` 对每局输出一张表，每场战斗一行：有没有开战实体快照、有没有 `hdt_bb` 记录（几次）、有没有 `Output`、有没有战斗后快照、有没有错误。缺失都要写明原因。
4. **原始行完整：** Hearthstone 还保留着当局会话日志时，比对同一局在 Power.log 里的行数（扣除第 2 节列出的那几类不经过回调的行）与 `power.log.gz` 的行数，两者应该相等。
5. **匿名化：** 在记录目录中搜索 `#\d{4,6}` 形式的 BattleTag，应该一个也找不到。
6. **体积：** 报告每局的磁盘占用。

## 6. 风险与回退

| 风险 | 应对 |
| --- | --- |
| HDT 更新后内部字段改名，反射失败 | 反射失败只写 `error` 记录，其余记录照常；按字段名查找，找不到时列出实际存在的字段 |
| 快照或序列化太慢，拖慢 HDT | 先看 `perf`；回退顺序：实体快照只保留 `PLAY`/`HAND`/`SECRET`/`SETASIDE` 区域 → 降低序列化深度 → 序列化移到后台线程（接受一致性损失） |
| 原始行体积过大 | gzip；还不够时只在酒馆战棋对局中记录（本来就只记这些） |
| 插件异常影响 HDT | 所有入口 `try/catch`；连续出错超过阈值时自动停止记录 |
| 读到不一致的 `_input` | 记录 `_state` 和重跑次数，分析时标出 |

## 7. 任务拆分

1. 插件工程和构建脚本：`build.ps1`、`meta.json`、加载日志。**需要所有者启用一次，确认官方版能加载**（同时完成 Q-005 剩下的加载验证）。
2. `RecordWriter` + `LineTracker` + 原始行 gzip + `event` / `combat_flag` 记录。
3. 实体快照。
4. `ReflectionDumper` + `hdt_bb` 记录（Q-002）。
5. `Anonymizer`，以及 `check_capture.py` 的覆盖率、行数比对和匿名化检查。
6. 所有者打 1 局 → 验收检查 → 调整 → 再打 3–5 局。最好能覆盖不同种族，以及有奥秘、有饰品、有战斗中触发效果（如 Tavish 装填、手牌相关附魔）的场面。
7. 分析：逐项核对数据清单，实测 Q-006 / Q-007，把结论写回 `facts/`，然后进入 P1-T3 / P1-T5。

## 8. 需要所有者确认

1. **用反射读 HDT 的内部字段**（`BobsBuddyInvoker._instances`、`_input` 等）：只读，不修改 HDT，也不反编译方法体。ADR-0006 只写了调用公开 API。建议在批准本方案时一并确认这属于 ADR-0006 的合理用途；如果你认为需要，我另写一份 ADR。
2. **本地记录的匿名化方式**：按 3.5 节，你自己的 BattleTag 也一并替换。
3. **记录目录**：`%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\`。
