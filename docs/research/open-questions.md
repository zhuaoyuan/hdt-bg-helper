# 未决问题与风险登记

> 这份文档回答：还有哪些事情不确定、它们影响什么、准备怎么验证。问题关闭后不删除，写明结论和结论写到了哪里。

状态：`open` 未决 / `investigating` 调研中 / `closed` 已关闭

影响：`高` 可能推翻方案 / `中` 影响设计细节 / `低` 影响有限

## 未决

| 编号 | 问题 | 影响 | 验证方式 | 关联 | 状态 |
| --- | --- | --- | --- | --- | --- |
| Q-002 | 能否通过反射读取 HDT 内部 `BobsBuddyInvoker._input`，作为对照基准或数据源？稳定性如何？ | 中 | 写原型插件尝试；关注 HDT 源码注释提到的"第三方插件保存/恢复 input"。源码层已知：`BobsBuddyInvoker` 是 `internal`，实例存在私有静态字典里，键为 `<gameId>_<回合>`（`facts/bobsbuddy-simulator-input.md` 第 8 节）。Q-004 结论是日志只能近似重建输入，所以反射仍是拿到 HDT 完整输入的唯一途径 | P1-T2、P2-T5 | open |
| Q-006 | 战斗中揭示的信息（第 5 节列表）插件能否在同一时机拿到？是否需要自行解析日志？ | 高 | 源码层结论（2026-09-25）：HDT 没有为这些更新提供公开事件；`LogEvents.OnPowerLogLine` 在 HDT 处理完同一行后同步回调，实体状态已更新；但 BLOCK 上下文是私有的，插件需要自己跟踪 BLOCK_START / BLOCK_END；也没有"战斗开始"事件，需要自己识别标签 2022 / 3533 由 1 变 0。详见 `facts/bobsbuddy-simulator-input.md` 第 8 节。**还需 P2 原型实测**：标签变化触发的动作是否排队执行、插件看到某一行时 HDT 的更新是否已完成 | P1-T1、P2-T3 | investigating |
| Q-007 | 对手玩家级计数器（如 `NUM_RESOURCES_SPENT_THIS_GAME` 从不下发）有哪些拿不到或只能推算？会让多大比例的快照变成 `partial`？ | 高 | 源码层清单已完成（2026-09-25，`facts/bobsbuddy-simulator-input.md` 第 9 节）：`ResourcesSpentThisGame`、未知手牌、未知奥秘、依赖对手手牌的附魔数值、对手 Tavish 装填随从拿不到或只能推算；13 个整局计数器依赖 `Bacon_TagTransferPlayerE` 附魔。**还需实测**：TagTransfer 附魔实际携带哪些标签；各项缺失在真实对局中的出现比例 | P1-T3、P2-T6 | investigating |
| Q-008 | 个人对局数据量能否支撑按"同补丁 + 同回合 + 同规则"筛选的参照池？需要多少局？ | 高 | 初步估算（2026-09-25，`research/q008-personal-data-volume.md`）：活跃期约 77 局/月，一个补丁窗口约 45 局；严格分桶下只有回合 ≤12、每桶约 30 个样本能在一个补丁内攒够，再按种族或畸变分桶基本不可行。**P3-T1 设计时需要据此放宽分桶**（跨补丁合并、相邻回合合并、计入对手场面等），并请所有者确认今后的对局频率 | P3 | investigating |
| Q-009 | 单场模拟 1.5–5 秒、占半数核心；P3 批量模拟的总耗时是否可接受？ | 中 | 已有数据：白板 7 对 7 在 6 线程下约 150 ms 完成 1 万次（`facts/bobsbuddy-public-api.md`）；HDT 日志中 968 次真实模拟耗时中位 2.3 秒，45% 因时间预算结束（`facts/hdt-log-simulation-input.md`）。下一步：用日志近似重建的真实场面在本机独立进程里测，并请所有者给出可接受的耗时标准 | P3、P4 | investigating |
| Q-011 | 离线批量模拟（P3）该用哪个版本的 `BobsBuddy.dll` 和 CardDefs？与采集时版本不一致时，结果会偏多少？ | 中 | 已知 1.78.8 删除了 1.76.0 中 Aberration 等下架卡牌的实现，HDT 运行时会下载最新 CardDefs（`facts/bobsbuddy-public-api.md`）。日志里没有记录 BB 版本，不能拿新版结果和日志里的旧 Output 直接比。本机官方 HDT 1.58.3 自带 BB 1.78.1，且会自动更新（ADR-0007），所以采集到的数据会跨多个 BB 版本。验证方式：把同一批日志重建的场面分别在 1.76.0、1.78.1、1.78.8 下模拟，统计失败和偏差；确认采集时能否记录 BB 版本与 CardDefs 版本 | P2-T1、P3 | open |
| Q-013 | HDT 从未赋值的 BB 公开字段（如 `Player.DeepBluesCounter`、`AnySpellCounter`、`BackToBackCounter`，`Minion.SecondaryRace`、`AvengeCounter` 等）是否会在开战时被 BB 读取、影响模拟结果？ | 中 | 清单见 `facts/bobsbuddy-simulator-input.md` 第 7 节。验证：在独立进程中对同一场面分别设置和不设置这些字段，比较结果；影响显著的字段要列入采集清单或标注为已知偏差 | P1-T5、P2-T4 | open |

## 已关闭

| 编号 | 问题 | 结论 | 结论位置 |
| --- | --- | --- | --- |
| Q-001 | `BobsBuddy.dll` 中 `Input`、`Player`、`Minion`、`SimulationRunner` 等类型是否公开，插件能否自行构造输入并调用模拟？ | 能。核心类型全部 `public`、可直接构造；独立 net472 x64 进程里调用 `SimulateMultiThreaded`，在 1.76.0 和 1.78.8 上都得到符合预期的结果。两个版本间核心 API 只有 `Player.MagnetizeCounter` 一处签名变化（2026-09-25） | `facts/bobsbuddy-public-api.md`、`spikes/bobsbuddy-api/` |
| Q-003 | HDT 自身和 `BobsBuddy.dll` 的许可条款是否允许个人插件引用和调用？ | 两者均为专有软件，条款只授予个人非商业使用。所有者确认：本机个人非商业使用相容；调用公开 API 与实时显示战力分位均为合理用途；仓库可公开但不得含 HDT/BB 二进制或反编译代码（2026-09-25） | `facts/licensing.md`、ADR-0006、ADR-0002 |
| Q-004 | HDT 日志中"Simulation Input / Output"段落是否足以重建输入？能否作为采集正确性的对照基准？ | 不能完整重建，只能近似。日志有随从（名字、攻血、关键词、金色、`ScriptDataNum`、附魔名）、场上顺序、英雄技能、任务、奥秘名和约一半计数器；缺英雄血量/护甲/等级、饰品、目标、畸变、可用种族、伤害上限和另一半计数器。Output 只有胜/平/负率、致死率、次数和耗时，没有伤害分布；可以作为 P2-T5 胜/平/负的对照，但只宜用每场只有一个 Input 段落的样本，并接受缺失字段带来的偏差（2026-09-25） | `facts/hdt-log-simulation-input.md`、`spikes/hdt-log-analysis/` |
| Q-005 | 插件构建时如何引用 HDT 和闭源 DLL（安装目录、版本对齐、CI 能否构建）？ | 本地构建已验证：.NET SDK 的 net472 x64 类库以 `Private=false` 引用安装目录的 HDT exe 和 DLL 即可，不需要 Visual Studio。CI：GitHub Releases 只到 v1.55.6，拿不到新版二进制文件，是否需要 CI 由所有者决定。在 HDT 中实际加载留到 P2 原型（2026-09-25） | `facts/hdt-baseline.md` 的"插件加载""插件构建"、`spikes/hdt-plugin-skeleton/` |
| Q-010 | 本机安装的修改版 HDT（1.58.1）相对上游改了什么？是否改动了 `BobsBuddyInvoker`、日志格式或插件接口？ | 不再需要回答。已知部分：第三方"团子版"，日志在上游格式之外插入额外行，新增拔线、对战记录等功能；没发现改动模拟输入逻辑或插件接口的证据，但无法完全排除。所有者已换用官方版（ADR-0007），插件不再面向修改版。剩余影响只在历史日志：它们来自团子版 1.49.2 – 1.57.12，用于近似重建场面时要注明来源，不用作 P2-T5 的精确对照（2026-09-25） | `facts/hdt-log-simulation-input.md` 第 5 节、ADR-0007 |
| Q-012 | 继续用修改版 HDT 作为验证环境（ADR-0005）是否合适？ | 不继续。所有者 2026-09-25 安装官方 HDT 1.58.3 并承诺保持最新，ADR-0005 被 ADR-0007 取代。团子版对战记录中 372 场拔线战斗没有结果，这批数据只用于对局量统计 | ADR-0007、`facts/local-environment.md` |
