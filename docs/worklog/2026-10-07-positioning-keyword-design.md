# 2026-10-07 关键词/邻接感知摆位：方案（未批跑）

## 目标

在 Q-017（身材全局排序不能抬高 \(S\)）之上，评估「关键词钉位 / 邻接启发 / 有限局部交换」是否值得做成摆位提示；先方案、确认前不全量批跑。

## 做了什么

- 必读：status、`facts/positioning-strength.md`、R-positioning 方案、`spikes/positioning/README`、write-design 提示词。
- 核对字段：`Taunt`/`Reborn` 可从 `_data` 读；cleave 依赖 CardID 集；先天亡语无可靠 Input bool（用额外亡语代理）。
- 撰写 `docs/design/R-positioning-keyword.md`（状态 `review`）：4 策略、同 1.85 T3–T7 样本、成本上界、与 R-pos 对照指标、失败判定「不值得做」。
- 登记 Q-018；更新 `design/README.md`、`status.md`。
- **未**改 `tools/strength`、未重跑身材表、未全量模拟。

## 发现

- Q-017 已含 `taunt_left_atk`（嘲讽靠左+攻序）且无 CI+；本轮 `taunt_pin_hp` 改为「有嘲讽才动、组内按血、无嘲讽保原序」，避免再套全局身材排序。
- 局部交换若无硬顶，最坏可达 ~6.7e5 对；方案写死 swap≤6 与 pair 硬顶 2.5e5。

## 留下

- 所有者审阅方案三问（见对话）；通过后再扩展 spike 并批跑。
- Q-018 仍为 open。
