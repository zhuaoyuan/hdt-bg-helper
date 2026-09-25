# 2026-09-25 未决问题分工与本机环境摸底

## 目标

在开始调研 Q-001～Q-009 之前，先判断哪些 agent 可以独立完成、哪些需要所有者配合。

## 做了什么

1. 检查本机 HDT 安装、数据目录、.NET 工具链，以及 `BobsBuddy.zip` 能否下载。
2. 在最大的一份 HDT 日志里抽查 Bob's Buddy 相关输出，并在上游源码中搜索其中的非标准输出。
3. 把 9 个问题分成三类（结果见 `status.md` 的"未决问题分工"）。
4. 所有者确认了两件事：
   - 同意 agent 在本地读取 `%APPDATA%\HearthstoneDeckTracker` 下的日志和 `BgsLastGames.xml`，写进仓库的内容必须匿名化；
   - 实测以当前安装的修改版 HDT 为准，结论标注适用范围（ADR-0005）。

## 发现

- 本机 HDT 在 `C:\Program Files\HDT`，版本 1.58.1，`BobsBuddy.dll` 1.76.0；比源码基线 1.58.3 低两个小版本。
- 这是一个修改版：日志的 "Simulation Input" 段落中有一行 `【团子专属】模拟对战，对手：…`，上游源码里没有。改动范围未知，登记为 Q-010。
- 本机已有真实酒馆战棋日志，其中包含完整的 "Simulation Input" 段落和 `SetupInputPlayer` 计数器输出，可以直接用于 Q-004 和 Q-007 的初步分析。
- 本机有 .NET SDK 8/9 和 net472 参考程序集，不装 Visual Studio 也能编译插件原型和 Bob's Buddy 调用样例。
- 详细信息见 `facts/local-environment.md`。

## 留下的东西

- 新增：`facts/local-environment.md`、`decisions/0005-modded-hdt-as-test-environment.md`。
- 更新：`research/open-questions.md`（新增 Q-010）、`facts/README.md`、`decisions/README.md`、`status.md`。
- 仍未提交：git `user.name` 还没配置。
