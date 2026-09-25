# 2026-09-25 换用官方版 HDT，关闭团子版相关事项

## 目标

所有者已安装官方 HDT，今后会一直更新到最新版本，询问和团子版有关的事项能否关闭。

## 做了什么

1. 核实本机官方版的安装位置、版本、自带 DLL 版本、运行中的进程路径和日志目录（结果见 `facts/local-environment.md`）。
2. 新写 ADR-0007（accepted，所有者对话确认）取代 ADR-0005；ADR-0005 状态改为 superseded。
3. 关闭 Q-010（不再需要回答）和 Q-012（不继续用修改版）；Q-011 补充官方版自带 BB 1.78.1。
4. 给 `facts/hdt-log-simulation-input.md` 加适用范围说明，给 `facts/bobsbuddy-public-api.md` 补充官方版的 BB 版本。

## 发现

- 官方版装在 `%LOCALAPPDATA%\HearthstoneDeckTracker\app-1.58.3`，文件版本 1.58.3.8362，和源码基线一致；自带 BobsBuddy.dll 1.78.1.0，比 `BobsBuddy.zip` 里的 1.78.8 旧。
- 官方版和团子版共用 `%APPDATA%\HearthstoneDeckTracker`（日志、插件目录）。团子版程序目录 `C:\Program Files\HDT` 仍在磁盘上。
- 日志文件名里的时间戳是**下一次**启动的时刻：HDT 启动时先把旧的 `hdt_log.txt` 改名，再按"最近 2 天 + 之前 25 个"清理（`Log.cs:34–58`）。现有 28 个文件，最旧的 2026-02-08 那份还在。
- 团子版历史日志里每个随从后面的 CardId 行只有团子版才打印，官方版日志没有，所以这批历史日志不可再生，备份更紧迫。

## 留下的东西

- 新增：`decisions/0007-official-hdt-as-test-environment.md`、本日志。
- 更新：`decisions/0005-…`（状态行）、`decisions/README.md`、`research/open-questions.md`、`facts/local-environment.md`、`facts/hdt-log-simulation-input.md`、`facts/bobsbuddy-public-api.md`、`status.md`。
- 待办：官方版产生带模拟的日志后，复核 `facts/hdt-log-simulation-input.md` 第 2–4 节。

## 追加：不保留历史日志；诊断记录插件方案

- 所有者决定不特意保留团子版历史日志和对战记录，理由是版本已和当前不同。状态文档中的备份提醒已删除。
- 所有者提议：先做一个尽可能完整记录对局数据的辅助插件，带着它打几局，再根据记录分析数据清单和采集工具的待办。agent 同意，因为 Q-002、Q-006、Q-007 本来就只能靠真实对局实测。
- 写了 [`design/P1-diagnostic-logger.md`](../design/P1-diagnostic-logger.md)（状态 `review`）。插件记录四类数据：原始 Power.log 行、开战和战后的全实体快照、通过反射读取的 HDT 模拟输入与结果、环境版本。
- 写方案时核实的事实：
  - 官方版自带 `Newtonsoft.Json.dll` 13.0.3 和 `System.Text.Json.dll` 8.0。
  - Hearthstone 在 `C:\Program Files (x86)\Hearthstone\Logs\` 下按会话保留日志，本机有 6 个会话目录，每个的 Power 日志 26–400 MB。
  - `BobsBuddyInvoker.Output` 是公开属性（`BobsBuddyInvoker.cs:135`），但类本身是 `internal`。
- 方案第 8 节有 3 项需要所有者确认，其中用反射读 HDT 内部字段不在 ADR-0006 明确覆盖的范围内。
