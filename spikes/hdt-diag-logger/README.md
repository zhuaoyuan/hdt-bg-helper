# Spike：诊断记录插件（HdtDiagLogger）

**目的：** 所有者带着这个插件正常打酒馆战棋，插件在本机尽可能完整地记录每场战斗，供 agent 离线分析数据清单（P1-T3 / P1-T5）并实测 Q-002、Q-006、Q-007。方案见 [`docs/design/P1-diagnostic-logger.md`](../../docs/design/P1-diagnostic-logger.md)。

**状态（2026-09-25）：** 已实现并通过 HDT 之外的离线测试；已部署到插件目录，**还没有在 HDT 里实际运行过**。

## 使用

1. 编译并部署（部署前关闭 HDT：HDT 运行时会锁住已加载的插件 DLL）：

   ```powershell
   spikes\hdt-diag-logger\build.ps1 -Deploy
   ```

   脚本自动找 `%LOCALAPPDATA%\HearthstoneDeckTracker` 下最新的 `app-*` 目录编译，再把 DLL 复制到 `%APPDATA%\HearthstoneDeckTracker\Plugins`。
2. 启动 HDT，在"选项 > 追踪器 > 插件"里启用 "BG Helper Diagnostic Logger"。HDT 日志里应出现 `[BgHelperDiag] loaded 0.1.0; HDT=…, BobsBuddy=…`。如果还有一行 `BobsBuddyInvoker probe unavailable`，说明反射失败（Q-002）。
3. 正常打酒馆战棋。每局一个目录：`%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\<开局时间>_<短 id>\`。插件设置里的按钮可以打开这个目录。
4. 检查记录：

   ```powershell
   python spikes\hdt-diag-logger\tools\check_capture.py          # 最新一局
   python spikes\hdt-diag-logger\tools\check_capture.py --all    # 所有对局
   ```

   输出只有计数、id 和匿名化后的值，可以贴进仓库。

## 每局记录的文件

| 文件 | 内容 |
| --- | --- |
| `meta.json` | schema 版本；插件、HDT、BobsBuddy、HearthDb 的版本；炉石 build；游戏类型；行数、记录数、错误数；反射初始化错误 |
| `power.log.gz` | HDT 转给插件的每一行 Power.log：`行号 \t 毫秒 \t 原始行`（已匿名化）。对局结束后才压缩；HDT 中途被关闭时留下未压缩的 `power.log` |
| `records.jsonl` | 每行一条记录，公共字段 `seq`、`lineSeq`（记录时已收到的行数）、`ms`、`type` |

`records.jsonl` 的 `type`：

| type | 时机 | 内容 |
| --- | --- | --- |
| `event` | HDT 公开事件 | `session_start`、`turn_start`、`opponent_secret_triggered`、`player_minion_attack`、`opponent_minion_attack`、`in_menu`、`replay_buffered_lines` |
| `create_game` / `combat_tag` | 对应日志行 | `combat_tag`：标签 2022 / 3533 的 `TAG_CHANGE` |
| `combat_phase` | `GameV2.IsBattlegroundsCombatPhase` 变化 | `value` |
| `entities` | 战斗开始、战斗结束（下一回合开始）、对局结束 | 全部实体的 id、CardId、名字、全部标签、`EntityInfo` 的简单属性；双方玩家各区域的实体 id；回合、畸变、可用种族 |
| `hdt_bb` | HDT 最新两个 `BobsBuddyInvoker` 的状态、重跑次数、输入对象或结果对象发生变化时；战斗开始 / 结束 / 对局结束时强制记录 | 整个 invoker 对象图（含 `_input` 和 `Output`），序列化规则见方案 3.4 |
| `perf` | 每 5 分钟、对局结束 | 各类回调耗时直方图、所在线程 id、写入队列长度 |
| `error` / `writer_error` | 出错时 | 异常文本（每局最多 20 条；HDT 线程上出错 100 次后停止记录） |

## 离线测试（不需要 HDT 运行）

```powershell
cd spikes\hdt-diag-logger\DumpTest
& "C:\Program Files\dotnet\dotnet.exe" build -c Release
.\bin\Release\net472\DumpTest.exe
python ..\tools\check_capture.py --root out\fake_root --hs-logs none
```

2026-09-25 结果（BB 1.78.1）：7 对 7 白板的 `Input` 共 210 个节点、约 37 KB JSON，首次序列化 12–22 ms（含 JIT 和反射缓存），之后约 1 ms；两次序列化结果一致，模拟前后 `Input` 的序列化结果也一致；`Output` 约 23 KB（含每次模拟的伤害结果）。唯一被跳过的类型是每个随从引用的 `Simulator`。匿名化和写入器检查通过。`out/` 里是从闭源 DLL 派生的输出，不入库。

## 已知限制

- 只保证单人模式；双人模式照常记录，检查脚本不区分队友。
- 在 `OnGameStart` 之前到达的日志行会先放进缓冲区（最多 5,000 行），开局时从最后一个 `CREATE_GAME` 起补写。补写行的 `ms` 是补写时刻。
- 匿名化会替换所有出现的已知玩家名（最短 2 个字符）。如果玩家名碰巧是某个卡牌名的一部分，那段卡牌名也会被替换。
