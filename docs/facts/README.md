# 事实库写作规范

> 这份文档回答：什么内容可以写进 `facts/`、怎么写才能让后来的 agent 放心使用。

## 什么算"事实"

只收录关于**外部系统实际行为**的、有证据的内容：HDT 源码、Bob's Buddy 行为、游戏日志格式、实测数据。我们自己的设计选择不属于事实，写进 `decisions/` 或 `design/`。

## 必备元数据

每份事实文档头部写明：

```text
基线：HDT v1.58.3 / 509bb0b9（或实测环境：HDT 版本、游戏补丁、日期）
最后核实：YYYY-MM-DD
```

## 每条事实的写法

- 带来源：`Hearthstone Deck Tracker/BobsBuddy/BobsBuddyInvoker.cs:519`，或"实测：worklog/2026-10-01-xxx.md"。
- 标注确定性：默认是**已核实**；只有推断的，句首加 **[推断]**，并在 `research/open-questions.md` 登记验证方法。
- 写"是什么"，不写"我们打算怎么办"。

## 何时复核

- 执行版本升级流程（`process/prompts/version-upgrade.md`）时，逐份复核基线相关的事实，更新基线和核实日期。
- 实测结果与事实文档矛盾时，以实测为准，修改文档并在 worklog 记录。

## 目录

| 文件 | 内容 |
| --- | --- |
| [`hdt-baseline.md`](hdt-baseline.md) | HDT 版本、构建、插件接口、事件与战斗时机 |
| [`bobsbuddy-simulator-input.md`](bobsbuddy-simulator-input.md) | Bob's Buddy 调用方式、输入数据清单、触发时序、对手可见性（P1 主交付物；P1-T1 / P1-T3 已完成） |
| [`diag-capture-measured.md`](diag-capture-measured.md) | 官方 HDT 诊断记录实测：验收、Q-006 时序、TagTransfer 标签与缺口比例（2026-09-26，3 局 / 27 场） |
| [`bobsbuddy-minion-enchantments.md`](bobsbuddy-minion-enchantments.md) | 随从附着附魔 → BB `Minion` 字段映射全表（上一份的附表） |
| [`local-environment.md`](local-environment.md) | 所有者本机实际运行的 HDT 版本、数据目录、可用工具 |
| [`bobsbuddy-public-api.md`](bobsbuddy-public-api.md) | `BobsBuddy.dll` 公开 API、独立调用实测、版本差异 |
| [`hdt-log-simulation-input.md`](hdt-log-simulation-input.md) | HDT 日志中模拟 Input/Output 段落的内容与缺口、本机修改版 HDT 的改动 |
| [`licensing.md`](licensing.md) | HDT / Bob's Buddy 许可与 HearthSim 条款原文、官方表态 |
