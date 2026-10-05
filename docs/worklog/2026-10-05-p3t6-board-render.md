# 2026-10-05 P3-T6 局面阵容图离线渲染

## 目标

按 `design/P3-board-render.md`（approved）与 ADR-0012 实现无状态单侧随从横排 PNG 渲染。

## 做了什么

1. 分支 `feat/P3-T6-board-render`（自 `main`）。
2. **T6.1** `board.py`：`entities@combat_start` 首选、BB Input 后备；`--check`；`combat.analyze_combat` 增补 `context`。ed11e0：24/24 侧 `(基卡,攻,血,金色,嘲讽,圣盾)` 一致。
3. **T6.2** `art.py` / `chrome.py` / `cards.py`：肖像 cache→HDT CardPortraits→HSJSON；chrome `--chrome-dir`→安装/源码探测→自绘；基础攻血可选。
4. **T6.3** `render.py` + CLI：`python -m tools.board_render --game ed11e0 --side both --compose`；联网缺肖像 0；`--offline` 与自绘 chrome 均可出图。
5. **T6.4** 更新 status / roadmap / 方案「实现记录」；验收 5 交所有者。

## 发现

- 官方 Squirrel 安装目录**没有**松散 `Resources/Minion/*.png`（嵌入 exe）；本机源码检出有完整 PNG，探测会命中该路径。用户仍可用 `--chrome-dir` 指定。
- 部分场面实体带 `WINDFURY=1`（如 Crackling Cyclone），与 BB `_data.Windfury` 一致；图上自绘「风怒」字标正确。
- HSJSON `cards.json` 下载需本机 `https_proxy`（`127.0.0.1:1081`）时可达。

## 留下的东西

| 项 | 路径 |
| --- | --- |
| 代码 | `tools/board_render/` |
| 样本图（不入库） | `data/boards/20261005_104908_ed11e0/` |
| 方案 | `docs/design/P3-board-render.md` → implemented |
| 提交 | `feat:` T6.1 / T6.2 / T6.3；本文件为 `docs:` |

## 所有者待办

- ~~挑 ≥3 张单侧图对照团子阵容或 HDT 悬停~~ → **2026-10-05 所有者确认没问题**；roadmap 已打勾。
- 可选：合并 `feat/P3-T6-board-render` → `main`。
