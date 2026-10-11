# score-policy spike

Q-020：用本机诊断记录里 HDT 已经跑完的真实对战，比较 `Output.damageResults` 和同一条 Input 的 `DamageCap`。

```text
python spikes/score-policy/q020_scan.py
```

脚本只读 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag`，往标准输出打汇总（回合、上限、胜平负、样本极值、攻击合计）。不写仓库、不打印随从或玩家名。

结论见 `docs/facts/damage-results-cap-q020.md`：正的上限会截断伤害样本。
