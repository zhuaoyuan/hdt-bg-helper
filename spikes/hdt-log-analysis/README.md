# Spike：HDT 日志与本机历史数据分析（Q-004、Q-010、Q-008）

**目的：**

- Q-004：HDT 日志里的 `----- Simulation Input -----` / `Output` 段落能不能重建 Bob's Buddy 的 `Input`，`Output` 能不能当往返验证的对照基准。
- Q-010：本机修改版 HDT 相对上游改了什么。
- Q-008：本机现有的个人对局数据量有多大。

**结论摘要（2026-09-25）：**

- Q-004：**不能完整重建。** 日志有随从（名字、攻/血、关键词、金色、`ScriptDataNum1..4`、部分附魔与额外亡语）、英雄技能、手牌概要、任务、奥秘名，以及约一半玩家级计数器；**没有**英雄血量/护甲/酒馆等级、饰品、目标、畸变、可用种族、伤害上限，也没有约一半计数器。`Output` 只有胜/平/负、双方致死率、次数、时长和结束原因，没有伤害分布。详见 [`docs/facts/hdt-log-simulation-input.md`](../../docs/facts/hdt-log-simulation-input.md)。
- Q-010：安装的是第三方中文修改版（"团子版"），加了拔线（断网跳过战斗动画）、对战记录、帧率修改、自带更新器等功能，并在 `RunSimulation` 里插入了额外日志。没有发现修改模拟输入构造逻辑的证据，但没有上游同版本二进制可比，不能完全排除。插件黑名单仍在。详见同一份事实文档。
- Q-008：日志覆盖 81 局（2026-02 到 2026-09），修改版"对战记录"覆盖 307 局（2025-10 到 2026-09），`BgsLastGames.xml` 69 局。全部为单人模式。估算见 [`docs/research/q008-personal-data-volume.md`](../../docs/research/q008-personal-data-volume.md)。

## 内容

| 文件 | 说明 |
| --- | --- |
| `hdtlog.py` | 日志解析库：按会话切分、识别 12/24 小时制时间戳、提取模拟段落（Input 各段、Output、触发原因） |
| `srctemplates.py` | 用 `git show <rev>:<path>` 只读取出上游 `BobsBuddyInvoker.cs` 的日志语句，转成匹配模板；含日志 HDT 版本到上游提交的映射 |
| `analyze_logs.py` | Q-004 / Q-010：字段覆盖、模拟次数、重跑、Output 统计、源码语句与日志行对照、修改版额外日志模板、校准 |
| `analyze_volume.py` | Q-008：`BgsLastGames.xml`、日志、修改版"对战记录"三个来源的对局量统计 |
| `MetadataProbe/` | .NET 8 控制台程序，用 `System.Reflection.Metadata` 只读元数据：类型名、`BobsBuddyInvoker` 方法名、用户字符串及引用它的方法。不加载、不执行、不反编译 |
| `compare_types.py` | 把 `MetadataProbe` 的类型/方法清单与上游 `ef8ab6e8`（v1.58.1）源码对比 |
| `out/` | 所有原始输出（含对手英雄名、账号 ID、IP 等个人信息，被 `.gitignore` 的 `spikes/**/out/` 规则排除，不入库） |

## 复现

需要 Python 3.10（本机 `python` 可用，只用标准库）和 .NET SDK。PowerShell 5.1 里 Python 的中文输出会乱码，脚本把结果写进 `out/` 下的 UTF-8 文件。

```powershell
cd spikes\hdt-log-analysis
$env:PYTHONIOENCODING = "utf-8"

python analyze_logs.py        # -> out\analyze_logs_summary.txt, out\log_report.json, out\sims.jsonl, out\mod_lines_raw.txt
python analyze_volume.py      # -> out\volume_report.json（同时打印）

& "C:\Program Files\dotnet\dotnet.exe" run --project MetadataProbe -- "C:\Program Files\HDT\HearthstoneDeckTracker.exe" out\metadata
python compare_types.py       # -> out\metadata\types_not_in_upstream.txt
```

读取的数据（全部只读）：

- `%APPDATA%\HearthstoneDeckTracker\Logs\hdt_log_*.txt`
- `%APPDATA%\HearthstoneDeckTracker\BgsLastGames.xml`
- `C:\Program Files\HDT\对战记录\*.txt`（修改版写的每日对战记录；不在最初授权清单里，只做了计数统计，见事实文档）
- `C:\Program Files\HDT\HearthstoneDeckTracker.exe`（只读元数据）
- `C:\projects\github\Hearthstone-Deck-Tracker`（只用 `git show` / `git grep`，不切换工作区）

## 已知局限

- 源码模板匹配按日志里的 HDT 版本选上游提交；上游没有 1.49.x 以外的标签时用提交号（`VERSION_REV`）。`Log.Debug` 在发布版里不输出，所以"源码有、日志没有"的列表里会带上它。
- 同一场战斗的重跑可能与前一次模拟并发，`Output` 段落会乱序；解析器把 `Output` 挂到最近一个 `Input` 上，约 2% 的段落（21/968）因此没有配上 `Output`，个别配对可能错位。做往返验证时应只用"每场战斗只有一个 Input 段落"的样本。
- `MetadataProbe` 找 `ldstr` 用的是字节扫描，不做完整 IL 解码，可能有误报（只影响"字符串被哪个方法引用"一列）。
