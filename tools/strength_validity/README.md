# tools/strength_validity（P3-T4）

消费 `strength.jsonl` + 标准层 turns + 诊断 `Player.Health`，评估局均分位与名次 / 下一回合血量的 Spearman 相关，并在名次标签上相对 HDT 比增量。

规格见 [`docs/design/P3-T4-validity.md`](../../docs/design/P3-T4-validity.md)。

## 命令

```powershell
python -m unittest discover -s tools/strength_validity

python -m tools.strength_validity run `
  --bb-version 1.85.0.0 `
  --turns 1-12 `
  --also-all-turns `
  --out data/strength/validity_1.85.json `
  --md data/strength/validity_1.85.md

# 若已有 player-only 分位文件
python -m tools.strength_validity run `
  --bb-version 1.85.0.0 `
  --player-only-strength data/strength/1.85.0.0/strength_player_only.jsonl `
  --player-only-out data/strength/validity_1.85_po.json `
  --out data/strength/validity_1.85.json
```

事实结论写入 `docs/facts/strength-validity-p3t4.md`。
