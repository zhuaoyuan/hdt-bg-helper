# 本机实测环境

> 这份文档回答：所有者这台机器上实际运行的 HDT 是什么版本、数据放在哪、本机能用哪些工具构建和分析。实测类结论都在这个环境下得出。

```text
实测环境：Windows 10 19045；官方 HDT 1.58.3.8362；BobsBuddy.dll 1.78.1.0
最后核实：2026-09-25
```

## HDT 安装（当前：官方版）

实测与验证环境见 [ADR-0007](../decisions/0007-official-hdt-as-test-environment.md)。所有者会让官方版保持最新，所以下面的版本号会过时，用到时先重新核实。

- 所有者 2026-09-25 安装。程序目录：`%LOCALAPPDATA%\HearthstoneDeckTracker\`（即 `C:\Users\Administrator\AppData\Local\HearthstoneDeckTracker\`），是官方 Squirrel 安装布局：根目录有启动器 `HearthstoneDeckTracker.exe` 和 `Update.exe`，程序本体在 `app-1.58.3\`。两个 exe 的文件版本都是 `1.58.3.8362`。
- 核实当时 HDT 进程正在运行，进程路径是 `app-1.58.3\HearthstoneDeckTracker.exe`。
- 安装版本 1.58.3 与源码基线（v1.58.3 / `509bb0b9`）一致。
- `app-1.58.3\` 下的闭源依赖：

  | 文件 | 文件版本 | 大小（字节） |
  | --- | --- | --- |
  | `BobsBuddy.dll` | 1.78.1.0 | 1,593,856 |
  | `BobsBuddy.Common.dll` | 1.78.1.0 | 4,096 |
  | `HearthDb.dll` | 36.6.0 | 37,211,648 |
  | `HearthMirror.dll` | 32.4.2 | 334,848 |

- 注册表 Uninstall 项里查不到 HDT（官方版和修改版都查不到），不能靠注册表判断安装位置。

## 旧安装：团子版（已停用）

2026-09-25 以前的实测结论和全部历史日志都来自这个版本。

- 程序目录：`C:\Program Files\HDT\HearthstoneDeckTracker.exe`，文件版本 `1.58.1.0`。2026-09-25 核实时仍在磁盘上，只是没有运行。它和官方版共用下文的数据目录，包括 `Plugins/`。
- 同目录下的闭源依赖：

  | 文件 | 文件版本 | 大小（字节） |
  | --- | --- | --- |
  | `BobsBuddy.dll` | 1.76.0.0 | 1,603,584 |
  | `BobsBuddy.Common.dll` | 1.76.0.0 | 4,096 |
  | `HearthDb.dll` | 36.6.0 | 37,211,648 |
  | `HearthMirror.dll` | 32.4.2 | 330,752 |

- **这不是官方构建。** 日志 `hdt_log_1789998252.txt` 第 122 行，在 `BobsBuddyInvoker.RunSimulation` 的 "Simulation Input" 段落中有一行 `【团子专属】模拟对战，对手：<英雄名>`。上游源码（基线 `509bb0b9`）里搜不到"团子"或"模拟对战"。
- 窗口标题为 `Hearthstone Deck Tracker-团子版`，是第三方中文修改版。修改内容的分析见 [`hdt-log-simulation-input.md`](hdt-log-simulation-input.md)。
- 与源码基线的差距：安装版本 1.58.1，源码基线 1.58.3。
- **带模拟的日志都不是 1.58.1 产生的。** exe 的修改时间是 2026-09-23 09:52；上面那份日志第 2 行写的是 `HDT: 1.57.12.0`。唯一来自 1.58.1 的是 `hdt_log_1790324889.txt`（3,084 字节，内容从 2026-09-24 20:41 开始，只有启动记录，没有模拟）。

## HDT 数据目录

`%APPDATA%\HearthstoneDeckTracker`（即 `C:\Users\Administrator\AppData\Roaming\HearthstoneDeckTracker`）：

官方版和团子版共用这个目录。

- `Logs/`：`hdt_log_<unix 时间戳>.txt`，每次启动一个文件。运行中的实例写 `hdt_log.txt`；下次启动时先把旧的 `hdt_log.txt` 改名为 `hdt_log_<本次启动时刻>.txt`，再清理旧日志（基线 `Utility/Logging/Log.cs:34–58`），所以文件名里的时间戳是**下一次**启动的时间，不是该日志本身的开始时间。第一次核实时共 26 个文件；2026-09-25 16:28 官方版启动后是 28 个（多了上面那份 1.58.1 的日志和官方版正在写的 `hdt_log.txt`），最旧的仍是 2026-02-08 的 `hdt_log_1770549057.txt`。**这批历史日志不可再生**：只有团子版会在每个随从后打印 CardId（[`hdt-log-simulation-input.md`](hdt-log-simulation-input.md) 第 4.4 节）。HDT 只保留最近 2 天加之前 25 个日志，超出的会自动删除（见 [`hdt-log-simulation-input.md`](hdt-log-simulation-input.md)），需要长期留存的日志要另外备份。核实时最大的一份是 `hdt_log_1789998252.txt`（2026-09-21，655,722 字节），其中匹配 `BobsBuddy|Simulation|BB:` 的有 4,873 行，包含 `SetupInputPlayer` 的计数器输出和完整的 `----- Simulation Input -----` 段落。
- `BgsLastGames.xml`（682,753 字节，2026-09-21）：酒馆战棋历史对局记录，结构还没分析。
- `Plugins/`：核实时为空。
- 其他：`config.xml`、`DeckStats.xml`、`Replays/` 等。
- 这些文件含对手 BattleTag 等个人信息。所有者已同意在本地读取分析；写进本仓库的摘录必须匿名化。

## 本机构建与分析工具

- .NET SDK：8.0.417、9.0.200（`C:\Program Files\dotnet`）。
- .NET Framework 4.7.2 参考程序集存在（`C:\Program Files (x86)\Reference Assemblies\Microsoft\Framework\.NETFramework\v4.7.2`），可以用 SDK 风格项目编译 `net472` 程序。
- PATH 上没有 `msbuild` 和 `ilspycmd`。
- `https://libs.hearthsim.net/hdt/BobsBuddy.zip` 可以直接下载（HEAD 请求返回 200，`Content-Length` 352,237）。
- 炉石安装目录：`C:\Program Files (x86)\Hearthstone`。
