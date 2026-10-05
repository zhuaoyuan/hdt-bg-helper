# 2026-10-05 — 局面阵容图渲染可行性调研

## 目标

核实：当前可达的 HDT 代码与数据资源，是否足以基于本项目诊断原始数据，渲染出类似「悬停对手头像看上次阵容」的局面图。

## 做了什么

1. 在 HDT 基线源码中定位链路：`SnapshotBattlegroundsBoardState` → `BattlegroundsBoardState` → Overlay 悬停 → `BattlegroundsOpponentInfo` / `BattlegroundsMinion` / `AssetDownloaders`。
2. 对照诊断样本 `20261005_104908_ed11e0`：`entities@combat_start` 与 `invoker._input` 同回合对手场面字段对齐。
3. 实测 HSJSON 肖像 URL 可访问；本机 HDT CardPortraits 缓存存在。
4. 结论写入 [`facts/hdt-past-opponent-board-render.md`](../facts/hdt-past-opponent-board-render.md)。

## 发现

- 用户记忆中的功能存在，且快照与 BB 输入是两条独立路径（事实库原先已提到 `3533` 快照）。
- 「略去状态信息」与当前源码不完全一致：上次阵容条仍画嘲讽/圣盾/亡语等角标与攻血；省略的是附魔细则等。
- BB `_data` 无亡语 bool；entities 有 `DEATH_RATTLE`。金色：实体 `cardId` 带 `_G`，BB 用 `Golden` 标志。
- 无法把 HDT 叠加层当离线库直接调用；资源贴图嵌在 HDT 程序集里。

## 留下的东西

- 新事实：`docs/facts/hdt-past-opponent-board-render.md`
- 未写实现代码；未开 ADR（尚无产品取舍）

## 追加：写方案（同日）

- 新增 [`design/P3-board-render.md`](../design/P3-board-render.md)（review），任务编号 P3-T6，已加进 roadmap 和方案索引。
- 补充实测：金色随从肖像 `…/256x/BG36_200_G.jpg` 与英雄头像 `…/heroes/latest/256x/BG23_HERO_306.png` 直连都返回 200；本机已装 Pillow 10.4 和 `msyh.ttc`。
- 发现：本机**没有** HDT 的 `CardDefs` 缓存目录（源码 `CardDefsManager.cs:24–40` 的路径）。`api.hearthstonejson.com` 的 `cards.json` 直连超时，走代理 `127.0.0.1:1081` 才返回 200（约 10 MB）。方案把基础攻血定为可选：取不到只是不做绿色高亮。
- 没有写 ADR：方案里的取舍（自绘还是复用 HDT 贴图、双方还是只画对手）只影响这一个工具，在方案里列给所有者决定即可。

## 追加：所有者确认三点（同日晚）

所有者确认后写入 [ADR-0012](../decisions/0012-board-render-side-unit.md)（accepted），方案改为 **approved**：

1. 核心是无状态**单侧**渲染单元（己方/对手/双方/跨局都由调用方组合）。
2. **允许**本机只读加载 HDT 边框/角标贴图（不入库）；找不到再自绘。
3. v1 **只画随从**；英雄、五率、战果等后续解耦。

下一步：按方案 §7 实现 T6.1。
