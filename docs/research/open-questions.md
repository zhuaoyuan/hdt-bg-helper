# 未决问题与风险登记

> 这份文档回答：还有哪些事情不确定、它们影响什么、准备怎么验证。问题关闭后不删除，写明结论和结论写到了哪里。

状态：`open` 未决 / `investigating` 调研中 / `closed` 已关闭

影响：`高` 可能推翻方案 / `中` 影响设计细节 / `低` 影响有限

## 未决

| 编号 | 问题 | 影响 | 验证方式 | 关联 | 状态 |
| --- | --- | --- | --- | --- | --- |
| Q-002 | 能否通过反射读取 HDT 内部 `BobsBuddyInvoker._input`，作为对照基准或数据源？稳定性如何？ | 中 | 写原型插件尝试；关注 HDT 源码注释提到的"第三方插件保存/恢复 input" | P1-T2、P2-T5 | open |
| Q-004 | HDT 日志中"Simulation Input / Output"段落是否足以重建输入？能否作为采集正确性的对照基准？ | 中 | 在真实对局后读取 HDT 日志，对照 `RunSimulation` 中的日志输出代码 | P1-T4 | open |
| Q-006 | 战斗中揭示的信息（第 5 节列表）插件能否在同一时机拿到？是否需要自行解析日志？ | 高 | P1-T1 梳理触发点；P2 原型实测 | P1-T1、P2-T3 | open |
| Q-007 | 对手玩家级计数器（如 `NUM_RESOURCES_SPENT_THIS_GAME` 从不下发）有哪些拿不到或只能推算？会让多大比例的快照变成 `partial`？ | 高 | P1-T3 逐字段标注可见性；P2 实测统计 | P1-T3、P2-T6 | open |
| Q-008 | 个人对局数据量能否支撑按"同补丁 + 同回合 + 同规则"筛选的参照池？需要多少局？ | 高 | P3-T1 估算；必要时考虑其他合规数据来源 | P3 | open |
| Q-009 | 单场模拟 1.5–5 秒、占半数核心；P3 批量模拟的总耗时是否可接受？ | 中 | 初步数据：白板 7 对 7 在 6 线程下约 150 ms 完成 1 万次（`facts/bobsbuddy-public-api.md`）。还需要用日志重建的真实场面测，并请所有者给出可接受的耗时标准 | P3、P4 | investigating |
| Q-010 | 本机安装的修改版 HDT（1.58.1）相对上游改了什么？是否改动了 `BobsBuddyInvoker`、日志格式或插件接口？ | 中 | 对比真实日志中 `BobsBuddyInvoker` 的输出与源码日志语句；必要时对比安装目录和上游同版本程序集的类型/方法差异 | ADR-0005、Q-002、Q-004 | open |
| Q-011 | 离线批量模拟（P3）该用哪个版本的 `BobsBuddy.dll` 和 CardDefs？与采集时版本不一致时，结果会偏多少？ | 中 | 已知 1.78.8 删除了 1.76.0 中 Aberration 等下架卡牌的实现，HDT 运行时会下载最新 CardDefs（`facts/bobsbuddy-public-api.md`）。验证：用同一批日志重建的场面分别在两个版本下模拟，统计失败和偏差；确认采集时能否记录 BB 版本与 CardDefs 版本 | P2-T1、P3 | open |

## 已关闭

| 编号 | 问题 | 结论 | 结论位置 |
| --- | --- | --- | --- |
| Q-001 | `BobsBuddy.dll` 中 `Input`、`Player`、`Minion`、`SimulationRunner` 等类型是否公开，插件能否自行构造输入并调用模拟？ | 能。核心类型全部 `public`、可直接构造；独立 net472 x64 进程里调用 `SimulateMultiThreaded`，在 1.76.0 和 1.78.8 上都得到符合预期的结果。两个版本间核心 API 只有 `Player.MagnetizeCounter` 一处签名变化（2026-09-25） | `facts/bobsbuddy-public-api.md`、`spikes/bobsbuddy-api/` |
| Q-003 | HDT 自身和 `BobsBuddy.dll` 的许可条款是否允许个人插件引用和调用？ | 两者均为专有软件，条款只授予个人非商业使用。所有者确认：本机个人非商业使用相容；调用公开 API 与实时显示战力分位均为合理用途；仓库可公开但不得含 HDT/BB 二进制或反编译代码（2026-09-25） | `facts/licensing.md`、ADR-0006、ADR-0002 |
| Q-005 | 插件构建时如何引用 HDT 和闭源 DLL（安装目录、版本对齐、CI 能否构建）？ | 本地构建已验证：.NET SDK 的 net472 x64 类库以 `Private=false` 引用安装目录的 HDT exe 和 DLL 即可，不需要 Visual Studio。CI：GitHub Releases 只到 v1.55.6，拿不到新版二进制文件，是否需要 CI 由所有者决定。在 HDT 中实际加载留到 P2 原型（2026-09-25） | `facts/hdt-baseline.md` 的"插件加载""插件构建"、`spikes/hdt-plugin-skeleton/` |
