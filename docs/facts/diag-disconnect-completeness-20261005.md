# 拔线场次下诊断记录完整性（2026-10-05）

> 这份文档回答：团子版「拔线」出现时，HdtDiagLogger 采到的对局数据还是否完整、缺什么。

```text
实测环境：团子版 HDT 1.58.6.0 / BobsBuddy 1.85.0.0 / 插件 0.1.0
样本：对战记录 2026年10月05日.txt（3 局）；BgHelperDiag
  20261005_070214_bdd811 / 20261005_070312_6ab052 / 20261005_072336_c88ca9
工具：spikes/hdt-diag-logger/tools/check_capture.py、eval_tuanzi_crosscheck.py
最后核实：2026-10-05
证据：docs/worklog/2026-10-05-disconnect-diag-completeness.md
```

## 结论

| 拔线形态（团子文案） | diag 是否仍有开战前 BB Input/Output | 其它缺口 |
| --- | --- | --- |
| `我直接拔线~`（无阵容行） | **通常没有**本回合 Combat dump | `combat_end` 实体数可骤降至个位数；可出现额外 `create_game`（重连） |
| `我拔线了，插件并不知道结果~`（有阵容+模拟） | **可以有**（本批 T8/T10 均有，且攻血多重集与团子一致） | 团子无实际战果；重连后血量差分可能断开 |
| 插件中途启用（`enabled_mid_game`） | 仅局末残留 invoker 可能可对上最后 1–2 回合 | 无 power 日志、无 combat 分段；更早回合全缺 |

本批：`6ab052`（无拔线）10/10 完整；`c88ca9`（有拔线）10/11，唯 T9「直接拔线」缺 Combat Output；`bdd811` 为局1 中途启用残局，非完整对局；`20ad61`（德雷阿佳丝，连续拔线）**11/12**，唯 T10「直接拔线」缺 Combat Output，其余有阵容回合与团子攻血多重集一致。

## 对应关系（已用英雄 CardId / 阵容多重集核对）

- 局1 泽瑞拉拔线局 → `bdd811`（残）
- 局2 雷诺 `TB_BaconShop_HERO_41` → `6ab052`
- 局3 奥拉基尔 `TB_BaconShop_HERO_76` → `c88ca9`
- 局4 德雷阿佳丝 `BG36_HERO_000` → `20261005_082741_20ad61`
