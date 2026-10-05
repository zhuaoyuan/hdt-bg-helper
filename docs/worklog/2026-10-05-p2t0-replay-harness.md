# 2026-10-05 — P2-T0 离线重放与往返验证

## 做了什么

- 方案：`docs/design/P2-replay-harness.md`（implemented）。
- 实现：`spikes/replay-harness/`——`ReplaySim`（运行时加载 BB）+ `tools/roundtrip.py`（分段过滤、匿名化键修复、3σ 对照、q009/q011/q013）。
- 跑通本机有 DLL 的 BB 1.78.1 + 1.85.0：`data/BgHelperDiag` 上 **261/261** 场同版本往返通过。
- 事实：`docs/facts/replay-roundtrip.md`；关闭 Q-009、Q-011、Q-013。

## 发现

- 匿名化无词边界替换会腐蚀 `ControlledByPlayer`、`Windfury`/`MegaWindfury` 等字段名；只修 `Player` 键不够，未修时对手随从 `controlled` 默认错误可导致五率完全颠倒。
- 跨版本（1.78.1 Input → 1.85.0 DLL）40 场里 3 场显著偏，确认必须按 `meta` 选 DLL。
- 六个 HDT 未赋值 Player 计数器扰动 30/30 不敏感。

## 留下什么

- 1.80.1 / 1.81.2 本机无 DLL，重放跳过；若要全覆盖需补齐历史 BB。
- P2-T2 仍应修插件匿名化（词边界），避免继续产生腐蚀数据。
- 下一步按 status：P2-T3 或 P2-T2 / P2-T1。
