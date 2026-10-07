# 2026-10-07 关键词/邻接摆位：实现与全量跑

## 目标

按 `R-positioning-keyword.md` 默认选项实现并批跑 Q-018。

## 做了什么

- 扩展 `spikes/positioning/`：关键词规则、`cleave_ids`（反射自本机 BB 1.85）、`local_swap_b6`（预算 6 + pair 硬顶 2.5e5）、`--keyword` CLI。
- 单测通过；T5 规则三策略 limit=8 冒烟 35/35 ok。
- 全量：1.85 T3–T7、四策略；输出 `data/positioning/1.85.0.0/keyword/`；进程约 113 min。
- 事实 `facts/positioning-keyword.md`；关闭 Q-018。

## 发现

- 三规则无 CI+；合并效应小/偏负 → **固定关键词提示不值得做**。
- `local_swap_b6` 五回合均 CI+（合并 +0.01），pairsPlanned 合计 ~183k、无截断；属同池选序，按方案标乐观偏差，不直接产品化。
- 本批裂解极少、额外亡语 0，限制规则可挖空间。

## 留下

- 可选：H3（搜索子样本 / 评估全池）若要再议「搜索型摆位辅助」。
- 主线仍停在 T5 人核 / T4 攒局。
