# 当前版本对局战力时序

离线 HTML。横轴是模拟池内对局顺序号（`gameId` 从早到晚）。

- **各回合**：己方分位、对手场面分位（0–100）
- **全局综合战力**：该局有分位的回合的算术平均
- **生存回合**：标准层该局最大回合；标准层没有该局时，用分位文件里的最大回合

己方用 `data/strength/<simPool>/strength.jsonl`。对手默认读已有的 `strength_opp.jsonl`。`--compute-opp` 用对战缓存补点估计，不跑新模拟，也不覆盖已有对手分位。

```powershell
python -m tools.progress_view --sim-pool 1.85.0.0 --compute-opp
```

输出：`data/progress/1.85.0.0.html`（在 gitignore 的 `data/` 下）。
