# AGENTS.md — Agent 工作总入口

本项目是 **agent 驱动** 的工程：大部分调研、设计、编码、验证由 AI agent 完成，人类（项目所有者）负责方向、验收和关键决策。本文件是每个 agent 会话的**第一份必读文件**。

## 1. 项目一句话

开发一个 Hearthstone Deck Tracker（HDT）的**酒馆战棋插件**：采集个人对局中足以驱动战斗模拟器的完整数据，基于历史数据 + 战斗模拟构建**自适应的战力分位评估引擎**，并在实时对局中显示，最终服务于**提升玩家本人的决策与复盘水平**（不是做代打 AI）。

## 2. 每次会话开始时（按顺序）

1. 读 [`docs/status.md`](docs/status.md) —— 当前阶段、进行中的任务、下一步、阻塞项。**唯一的"现在在哪"事实源。**
2. 读 [`docs/roadmap.md`](docs/roadmap.md) 中与当前任务相关的阶段与退出标准。
3. 按任务需要读 `docs/facts/`（已核实事实）、`docs/decisions/`（已做决定）、`docs/research/open-questions.md`（未决问题）。
4. 选择对应的流程提示词：[`docs/process/prompts/`](docs/process/prompts/README.md)。

## 3. 每次会话结束前（必须）

- 更新 `docs/status.md`（完成了什么、下一步是什么、有无阻塞）。
- 在 `docs/worklog/` 新增或追加当天记录（做了什么、发现了什么、留下什么）。
- 新核实的事实 → `docs/facts/`；新的决定 → `docs/decisions/`；新的疑问/风险 → `docs/research/open-questions.md`。
- 不要把只存在于对话里的结论留在对话里：**没写进仓库的结论等于没有**。

## 4. 仓库地图

| 路径 | 内容 | 写入规则 |
| --- | --- | --- |
| `AGENTS.md` | 本文件，agent 入口与规则 | 规则变化时更新 |
| `docs/status.md` | 当前状态、下一步 | 每次会话结束更新 |
| `docs/roadmap.md` | 阶段、里程碑、任务 ID、退出标准 | 阶段变化或任务增删时更新 |
| `docs/context/` | 愿景、术语、原始讨论存档 | 原始讨论只读；愿景变化需所有者确认 |
| `docs/facts/` | 已核实事实（带来源与核实版本） | 只写有证据的内容，见 `docs/facts/README.md` |
| `docs/decisions/` | 架构决策记录（ADR） | 新决定新增文件，已接受的 ADR 不改写，只能被新 ADR 取代 |
| `docs/architecture/` | 系统整体架构（当前有效版本） | 随已接受的 ADR 同步更新 |
| `docs/design/` | 各模块/里程碑的技术方案 | 实现前先写方案，见模板 |
| `docs/research/` | 未决问题与风险登记、调研（spike）记录 | 问题关闭时注明结论与去向 |
| `docs/process/` | SDLC 流程与各阶段提示词 | 流程改进时更新 |
| `docs/worklog/` | 按日期的工作日志 | 只追加 |
| `src/`、`tests/`、`tools/` | 代码（尚未创建，规划见 `docs/architecture/overview.md`） | 按设计文档实现 |
| `spikes/` | 为验证可行性写的一次性原型（尚未创建） | 每个原型附 README 说明目的与结论；不作为正式代码依赖 |

## 5. 外部依赖与参考

- **HDT 源码（只读参考）**：`C:\projects\github\Hearthstone-Deck-Tracker`，上游 `https://github.com/HearthSim/Hearthstone-Deck-Tracker`。
  - 当前事实基线：**v1.58.3，commit `509bb0b9`（2026-09-24）**。所有 `docs/facts/` 中引用的 HDT 代码行号均以此为准。
  - 不要修改该仓库。只有在执行"版本升级"流程（`docs/process/prompts/version-upgrade.md`）时才 `git pull`，并同步更新基线。
- **Bob's Buddy**（HDT 内置战斗模拟器）：闭源 `BobsBuddy.dll`，由 HDT 构建脚本从 `https://libs.hearthsim.net/hdt/BobsBuddy.zip` 下载，随 HDT 安装包分发。详见 `docs/facts/bobsbuddy-simulator-input.md`。

## 6. 工作规则

1. **事实与推断分开。** 写进 `docs/facts/` 的内容必须带来源（文件路径+行号+commit，或实测记录）。推断、猜测写进 `open-questions.md` 并标注如何验证。
2. **先方案后代码。** 超过"单文件小改动"的实现，先在 `docs/design/` 写方案（可以很短），列出验收方式。
3. **有取舍就写 ADR。** 存在可选方案、且影响超过当前任务的决定，写 ADR。agent 可以把 ADR 写成 `proposed`；变成 `accepted` 需要所有者确认（所有者已明确授权的除外，需在 ADR 中注明）。
4. **验收优先于功能。** 每个里程碑都要有可重复执行的验证手段（测试、数据质量报告、与 HDT 自身 Bob's Buddy 结果的对照）。
5. **范围红线（不做）：** 自动操作游戏或宏；爬取 HSReplay 会员页面；上传或公开他人 BattleTag 等个人信息（本地存储时匿名化）。
6. **小步提交。** 每个可独立验证的改动一个 commit，消息用约定式前缀：`feat:` `fix:` `docs:` `chore:` `test:` `refactor:`。不要擅自 push。
7. **语言约定。** 文档用简体中文；代码标识符、commit 前缀、文件名用英文。

## 7. 环境注意事项（已踩过的坑）

- 系统：Windows 10，默认 Shell 是 **Windows PowerShell 5.1**：不支持 `&&` / `||`，串联命令用 `;` 或 `if ($?) { ... }`。
- HDT 目标框架：`net472`、`x64`、C# 10。插件需与之匹配（见 `docs/facts/hdt-baseline.md`）。
- 本项目目录的上级 `C:\projects\github` 本身也是一个（无提交的）git 仓库，本项目有自己独立的 git 仓库，注意 git 命令的工作目录。
