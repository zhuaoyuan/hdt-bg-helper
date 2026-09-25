# 2026-09-25 项目初始化

## 目标

基于早期讨论和所有者确认的优先级，初始化一个适合 agent 持续迭代的项目结构（P0）。

## 做了什么

1. 把 HDT 克隆到 `C:\projects\github\Hearthstone-Deck-Tracker`，只读参考，基线 v1.58.3 / `509bb0b9`。
2. 摸底 HDT 中与本项目最相关的代码：
   - `Plugins/IPlugin.cs`、`API/GameEvents.cs`：插件接口与公开事件；
   - `BobsBuddy/BobsBuddyInvoker.cs`（全文）、`BobsBuddy/BobsBuddyUtils.cs`（第 30–160 行）：模拟器输入构造；
   - `LogReader/Handlers/TagChangeActions.cs`（第 186–245 行）：战斗开始的触发点；
   - `Bootstrap/Bootstrap.csproj`、`bootstrap.ps1`：闭源依赖的来源。
3. 建立文档体系（见 [ADR-0001](../decisions/0001-agent-driven-docs-structure.md)）：`AGENTS.md`、状态、路线图、背景、事实、ADR、架构、方案模板、未决问题、SDLC 流程与 8 份提示词。
4. 把 `early_discussion.md` 从项目根目录移到 `docs/context/early_discussion.md`，内容未改。
5. 在项目目录初始化独立 git 仓库（默认分支 `main`）。

## 发现

- **Bob's Buddy 是闭源 DLL**，构建时从 `libs.hearthsim.net` 下载，仓库里没有源码。
- **HDT 的输入构造代码是 `internal`**，插件不能直接调用，需要在本项目重新实现或通过反射访问（Q-001、Q-002）。
- **战斗快照不是一个瞬间**：HDT 在战斗过程中会根据揭示的信息（对手手牌、奥秘、Tavish 装填、多种附魔、Auto Assembler / 螃蟹亡语等）更新输入并重新模拟，每场最多约 11 次。采集工具必须同样捕获这些信息。
- **对手部分计数器拿不到**：例如 `NUM_RESOURCES_SPENT_THIS_GAME` 从不下发给对手，HDT 只能从 Malorne 反推（Q-007）。
- HDT 源码注释提到"第三方插件在战斗中保存/恢复 input"，说明已有插件通过反射访问 HDT 内部的模拟器输入（Q-002）。
- HDT 本身会把模拟结果与实际战斗结果对照并上报，这给了我们一个现成的正确性对照思路：**往返验证**（P2-T5）。
- 环境：默认 Shell 是 Windows PowerShell 5.1，不支持 `&&`；上级目录 `C:\projects\github` 是一个没有提交的 git 仓库。

## 留下的东西

- 全部文件都是新增的，见仓库根目录与 `docs/`。
- 数据清单草稿 `docs/facts/bobsbuddy-simulator-input.md`，待补全部分列在文末。
- **初始提交未完成**：本机 git 全局配置里没有 `user.name`（只有 `user.email`）。需要所有者配置后再提交：

  ```powershell
  git config --global user.name "你的名字"
  cd C:\projects\github\hdt-bg-helper
  git add -A
  git commit -m "chore: bootstrap agent-driven project structure"
  ```
