# 2026-10-06 HDT 参考源码 pull（基线升级）

## 目标

补全复盘阵容缺肖像；所有者建议先 pull HDT 仓库再重试。

## 基线

| | 旧 | 新 |
| --- | --- | --- |
| 标签 / 说明 | v1.58.3 | v1.58.8（`CHANGELOG` / tip） |
| commit | `509bb0b9`（2026-09-24） | `78cdc2a7`（2026-10-06） |

相关 diff（节选）：`BobsBuddyInvoker.cs`、`BobsBuddyUtils.cs`、`PowerHandler.cs`、`API/LogEvents.cs`；新增 chrome `rally.png`、`divine-shield-empowered.png`。

## 肖像结论

- **拉取源码仓不会补 CardPortraits。** 肖像查找顺序是：`data/art_cache/portraits` → `%APPDATA%\...\Images\CardPortraits` → HSJSON。
- pull 后上述 9 个缺 id 在 AppData / art_cache 仍为 MISS。
- 去掉 `--offline` 联网重渲：`missingPortraitCount=0`，已写回 `data/boards/20261006_215623_f41aef` 并刷新复盘页。

## 兼容性（未做全量事实复核）

- BB Invoker / PowerHandler 有改动；**尚未**逐条更新 `docs/facts/` 行号。后续若动插件或对照 HDT 源码，再按 `version-upgrade.md` 复核。
- `AGENTS.md` 基线已改为 v1.58.8 / `78cdc2a7`。

## 留下的东西

- 复盘页已用新 PNG：`data/review/20261006_215623_f41aef/index.html`
- 本 worklog；`AGENTS.md` 基线更新
