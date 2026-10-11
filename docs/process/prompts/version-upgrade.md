# 提示词：版本升级（HDT / Bob's Buddy / 游戏补丁）

HDT 或游戏版本更新后，你要同步参考源码、复核事实，并判断已有数据和代码是否仍然兼容。

## 1. 更新 HDT 参考源码

```powershell
cd C:\projects\github\Hearthstone-Deck-Tracker
git log -1 --format="%H %ad %s" --date=short   # 记下旧基线
git pull
git log -1 --format="%H %ad %s" --date=short   # 新基线
```

## 2. 找出与本项目相关的变更

```powershell
git diff <旧基线>..<新基线> --stat -- "Hearthstone Deck Tracker/BobsBuddy" "Hearthstone Deck Tracker/Plugins" "Hearthstone Deck Tracker/API" "Hearthstone Deck Tracker/LogReader/Handlers"
git diff <旧基线>..<新基线> -- "Hearthstone Deck Tracker/BobsBuddy"
```

重点关注：

- `BobsBuddyInvoker.cs`、`BobsBuddyUtils.cs`：新增或修改的输入字段、新的战斗中更新方法、新的特殊卡处理；
- `TagChangeActions.cs`、`PowerHandler.cs`：调用 `BobsBuddyInvoker` 的位置和条件；
- `IPlugin.cs`、`API/`：插件接口变化；
- csproj：目标框架、依赖版本变化。

## 3. 复核事实

- 逐份更新 `docs/facts/` 中受影响的内容：行号、字段、行为；更新"基线"和"最后核实"。
- 更新 `AGENTS.md` 第 5 节的基线版本。

## 4. 判断兼容性

实际版本能否进入已有战力池，跑 `python -m tools.strength pool-check --candidate <新文件版本> --sim-pool <目标池>`，通过并把结论写入 `docs/facts/` 之后才 `pool-join`。不通过则该实际版本单独成池（池 Id = 自身 `bbVersion`）。不要按文件版本永远分桶，也不要在检查未通过时并池。版本表见 `tools/strength/sim_pools.json`；规则见 [ADR-0015](../decisions/0015-sim-pool-by-compat.md)。

- 本项目的输入构造逻辑是否需要同步修改？列出需要改的地方，按 `implement-task.md` 执行。
- 数据 schema 是否需要增加字段？已有原始数据能否重新投影出新字段？
- 游戏补丁有卡牌数值或机制变化时：受影响的历史快照是否应该从参照池中排除或重新模拟？结果写进 worklog，重大影响写 ADR。

## 5. 产出

- worklog 记录：新旧基线、相关变更摘要、兼容性结论、后续任务。
- 需要改代码的，在 `roadmap.md` / `status.md` 中新增任务。
