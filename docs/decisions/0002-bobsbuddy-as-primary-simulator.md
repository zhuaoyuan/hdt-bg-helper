# ADR-0002：以 Bob's Buddy 作为首选战斗模拟器

- **状态：** accepted（所有者 2026-09-25 确认 Q-003 / ADR-0006；Q-001 已关闭）
- **日期：** 2026-09-25
- **相关：** P1-T2、Q-001、Q-002、Q-003、ADR-0006

## 背景

战力分位的计算完全依赖一个能对任意两个场面进行战斗模拟的模拟器。模拟器的机制覆盖面和版本跟进速度，直接决定"版本自适应"能否成立。

已知事实（见 `facts/bobsbuddy-simulator-input.md`）：

- Bob's Buddy 随 HDT 发布，HDT 团队持续跟进新版本卡牌，并用远程配置控制最低版本和开关。
- HDT 会把模拟结果与实际战斗结果对比，发现不一致就上报。这是持续的质量反馈。
- 它是闭源 DLL；HDT 中构造输入的代码是 `internal`，插件无法直接复用。

## 决定

首选 Bob's Buddy 作为战斗模拟核心。自行构造 `Input` 调用 `SimulationRunner`；把 HDT 中"实体 → 输入"的转换逻辑在本项目中重新实现（或在确认可行的前提下通过反射复用）。调用方式受 [ADR-0006](0006-personal-plugin-use-of-hdt-bobsbuddy.md) 约束：只用本机已安装的 DLL，不分发、不入库、不反编译方法体。

## 考虑过的方案

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| **Bob's Buddy** | 版本跟进最快；与 HDT 显示的结果一致；有线上校准反馈 | 闭源；API 未必稳定；许可证为专有软件，按 ADR-0006 约束使用 |
| 开源模拟器（如 twanvl/hearthstone-battlegrounds-simulator） | 可读可改 | 作者说明存在机制偏差；版本跟进无保证 |
| 自研模拟器 | 完全可控 | 工作量巨大，与"提升玩家水平"的目标不匹配 |

## 后果

- 正面：可以用 HDT 当场显示的胜率做往返验证（P2-T5），有现成的正确性对照。
- 代价：需要在本项目中维护一份转换逻辑，并在每次 HDT 升级时对照 `BobsBuddyInvoker` / `BobsBuddyUtils` 的变更同步（见版本升级流程）。
- 跟进：P1-T2 确认公开 API（已完成，见 `facts/bobsbuddy-public-api.md`）；Q-003 / ADR-0006 已确认使用范围；Q-011 确定离线模拟时 Bob's Buddy 与 CardDefs 的版本策略（新版 DLL 会删除下架卡牌的实现）。

## 推翻条件

- `SimulationRunner` / `Input` 无法在 HDT 流程之外构造或调用；
- 许可证不允许；
- 实测发现模拟器对我们关心的场面覆盖率过低。
