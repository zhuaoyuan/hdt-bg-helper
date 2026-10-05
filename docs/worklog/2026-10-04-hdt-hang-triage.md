# 2026-10-04 — HDT 开局无响应排查

## 背景

所有者反馈：最近游戏开始时 HDT 无响应；完全卸载重装后仍无改善。需确认是否本项目诊断插件（`HdtDiagLogger` / BgHelperDiag）导致。

## 本机现状（排查时）

| 项 | 值 |
| --- | --- |
| 团子版 | `C:\Program Files\HDT\HearthstoneDeckTracker.exe` 1.58.6.0 |
| 官方版 | `%LOCALAPPDATA%\HearthstoneDeckTracker\app-1.58.6\` 1.58.6.9003 |
| 另有拷贝 | 事件日志显示曾运行 `Downloads\HDT\`（排查时目录已不在） |
| AppData 插件 | `%APPDATA%\HearthstoneDeckTracker\Plugins\HdtDiagLogger.dll`（2026-09-25） |
| 同步副本 | 团子/`Program Files\HDT\Plugins\`、官方 `app-1.58.6\Plugins\` 均有同名 dll |
| `plugins.xml` | 空列表（默认不启用任何插件） |

说明：官方卸载/重装通常不删 `%APPDATA%\HearthstoneDeckTracker`，插件 dll 会残留并在启动时 `SyncPlugins` 拷进安装目录的 `Plugins\`。

## Windows 事件日志（Application Hang 1002）

今日至少 6 次，**全部为 `Hang Type: Cross-thread`**：

| 报告时间 | 进程路径 | Waiting (s) | 进程启动时刻（FILETIME） |
| --- | --- | --- | --- |
| 20:28:54 | `Downloads\HDT\`（团子） | 14 | ~20:03 |
| 21:22:08 | `Downloads\HDT\`（团子） | 17 | ~21:12 |
| 21:41:57 | 官方 `app-1.58.6` | 5 | ~21:41 |
| 21:46:40 | 官方 `app-1.58.6` | 5 | ~21:46 |
| 21:52:44 | `Program Files\HDT` | 16 | ~21:52 |
| 23:03:54 | `Program Files\HDT` | 22 | ~22:06（整晚会话） |

官方版与团子版都挂过 → 不是团子独有。

## 与插件的关系

### 有插件且启用的会话（`hdt_log.txt`，22:06 起，团子）

- 22:06:15 启用 `BG Helper Diagnostic Logger` 0.1.0。
- 完整打完两局：`20261004_220813_62725a`（15 回合）、`20261004_224035_3a513e`（12 回合），`endReason=game_end`，`errors=0`。
- 插件自测耗时（第二局 final perf）：`hdt_bb_dump` max ≈ 44 ms；`line` max ≈ 56 ms；`entities` max ≈ 28 ms。不足以单独造成数十秒 UI 假死。
- 第二局结束后：
  - 23:03:16 插件 `finished`、对局上传成功。
  - 23:03:26 回到 `BACON`。
  - 23:03:33 起 HearthMirror RPC 大量失败：`ScryMemoryAccessException`（读 `0x10`/`0x48`）、随后 `ScryInitializationException` 刷屏；日志停在 23:03:34。
  - 23:03:54 Windows 报告 Hang（Waiting 22 s → 约从 23:03:32 起无响应），与 Mirror 风暴对齐。

### 插件未启用的邻近会话

`hdt_log_1791122161/2495/2767`（21:55–22:05）只有 `Loading Plugins...`，**没有** `Loading/Enabled BG Helper Diagnostic Logger`。`plugins.xml` 一直为空 → 默认不启用。

官方版 21:41 / 21:46 的 Hang 发生在这些会话之前，且当时设置同样是空的 → **很大概率当时插件未启用仍发生 Cross-thread Hang**。

## 其他线索（非插件）

- 当前日志内 `AssetDownloader.DownloadFileAsync` 失败约 167 次；`ApiWrapper.GetCompsGuides` IOException 数次（国服访问 HSReplay 资源不稳定）。
- 同机多份 HDT（Downloads / Program Files / LocalAppData）交替启动，共享同一 AppData。
- 卸载重装不改善：与「根因在 AppData/Mirror/网络」或「根因不在安装目录」都相容；不能据此认定是插件。

## 结论

1. **本项目插件不是主要嫌疑。** 依据：官方版在插件默认未启用时也有同类型 Hang；插件启用后仍能完整打完两局；末次 Hang 时间点对齐 HearthMirror 崩溃式读内存，而非 `game_start` / 插件重活。
2. **更可疑：HearthMirror（Scry）跨线程卡死**，可能叠加炉石进程状态异常、国服网络资源超时。Hang Type 一律为 `Cross-thread`。
3. 插件仍建议做一次 **A/B 对照** 以彻底排除（见下），因 dll 仍在 AppData 且可被手动启用。

## 建议的对照实验（所有者）

1. 退出所有 HDT / 炉石。
2. 将 `%APPDATA%\HearthstoneDeckTracker\Plugins\HdtDiagLogger.dll` 移出（例如改名为 `.dll.bak`）；同时删掉各安装目录 `Plugins\HdtDiagLogger.dll`（否则会被旧副本搞混；若只移 Roaming，启动时 SyncPlugins 可能从 Roaming 再拷入——故必须先移 Roaming）。
3. 只用**一份** HDT（建议先官方或先团子，不要混开），再开一两局酒馆。
4. 若仍 Hang → 与本插件无关，转向 Mirror/炉石/网络；若不再 Hang → 再把插件放回并在 Options 里确认启用状态，复现一次以定性。

可选并行：暂时关掉 HDT 的 HSReplay/攻略相关联网功能或观察资源下载失败是否同步减少。

## 后续（2026-10-05）

所有者反馈：重启电脑后，无论是否开启 `HdtDiagLogger`，均未再出现未响应。无法稳定复现，**排查暂时搁置**；若再次出现再继续（优先抓 Hang 时刻的 HearthMirror 日志与 Application Hang 1002）。
