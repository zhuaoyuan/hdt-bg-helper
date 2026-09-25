# 本机实测环境

> 这份文档回答：所有者这台机器上实际运行的 HDT 是什么版本、数据放在哪、本机能用哪些工具构建和分析。实测类结论都在这个环境下得出。

```text
实测环境：Windows 10 19045；HDT 1.58.1.0（修改版，见下文）；BobsBuddy.dll 1.76.0.0
最后核实：2026-09-25
```

## HDT 安装

- 程序目录：`C:\Program Files\HDT\HearthstoneDeckTracker.exe`，文件版本 `1.58.1.0`。核实当时 HDT 进程正在运行，进程路径就是这个文件。
- 同目录下的闭源依赖：

  | 文件 | 文件版本 | 大小（字节） |
  | --- | --- | --- |
  | `BobsBuddy.dll` | 1.76.0.0 | 1,603,584 |
  | `BobsBuddy.Common.dll` | 1.76.0.0 | 4,096 |
  | `HearthDb.dll` | 36.6.0 | 37,211,648 |
  | `HearthMirror.dll` | 32.4.2 | 330,752 |

- `%LOCALAPPDATA%\HearthstoneDeckTracker`（官方 Squirrel 安装器的默认位置）不存在。
- **这不是官方构建。** 日志 `hdt_log_1789998252.txt` 第 122 行，在 `BobsBuddyInvoker.RunSimulation` 的 "Simulation Input" 段落中有一行 `【团子专属】模拟对战，对手：<英雄名>`。上游源码（基线 `509bb0b9`）里搜不到"团子"或"模拟对战"。
- 与源码基线的差距：安装版本 1.58.1，源码基线 1.58.3。修改版具体改了什么还不知道（Q-010）。

## HDT 数据目录

`%APPDATA%\HearthstoneDeckTracker`（即 `C:\Users\Administrator\AppData\Roaming\HearthstoneDeckTracker`）：

- `Logs/`：`hdt_log_<unix 时间戳>.txt`，每次启动一个文件。核实时最大的一份是 `hdt_log_1789998252.txt`（2026-09-21，655,722 字节），其中匹配 `BobsBuddy|Simulation|BB:` 的有 4,873 行，包含 `SetupInputPlayer` 的计数器输出和完整的 `----- Simulation Input -----` 段落。
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
