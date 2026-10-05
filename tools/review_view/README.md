# tools/review_view（P3-T5）

离线静态 HTML 赛后复盘页：标准层回合 × `strength.jsonl` × 阵容图。

```powershell
python -m unittest discover -s tools\review_view -p "test_*.py" -v

python -m tools.board_render --game ed11e0 --side both --offline --out data\boards
python -m tools.review_view --game ed11e0 `
  --turns data\standard\turns.jsonl `
  --strength data\strength\1.85.0.0\strength.jsonl `
  --boards data\boards `
  --out data\review

start data\review\20261005_104908_ed11e0\index.html
```

输出：`data/review/<gameId>/index.html` + `model.json` + `boards/`（从 `--boards` 复制）。  
默认会按需计算对手分位并缓存到 `data/strength/<bb>/strength_opp.jsonl`。可选 `--no-opp-strength`、`--render-boards`、`--serve`、`--allow-missing-strength`。
