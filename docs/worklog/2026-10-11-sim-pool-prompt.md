# 2026-10-11 模拟池版本表：只写提示词

## 目标

把所有者的并池想法写成可派发的任务提示词，本会话不改战力代码、不重算。

## 做了什么

新增 [`docs/process/prompts/sim-pool-versions.md`](../process/prompts/sim-pool-versions.md)。

- 实际版本仍是 `bbVersion`（DLL `fileVersion`）。
- 战力与对战的分组键改叫 **模拟池** `simPool`，池 Id 取池内最早的实际版本。
- 并池门槛是同输入跨 DLL 的五率 3σ（沿用 Q-011），不是旧 L2 / E5 的分位差。
- 初始并池只包含已有结论的 `1.85.0.0` 与 `1.88.6.0`。1.78.1 等保持各自一池。
- 重刷时合并已有次数，只补跨实际版本的缺对，再用池内最新 DLL 模拟。

索引与 `version-upgrade.md` 加了指向。status 写明：提示词未执行前仍按文件版本分桶。

## 留下的东西

未实现 `sim_pools.json`、未迁移 `cache.sqlite`、未重算分位。
