# 木桩梯队（旁路）

把真实己方场面和一个「7 个攻=血完全相同、无词条」的对手打，用五五开那一档的攻血当作绝对值 `X50`。

不进入主线战力。v1 结论见 `docs/facts/dummy-ladder-20261018.md`，v1 方案见 `docs/design/R-dummy-ladder.md`；v2（模型化估计 + 两阶段/自适应采集）见 `docs/design/R-dummy-ladder-v2.md`。

```powershell
& "C:\Program Files\dotnet\dotnet.exe" build spikes\dummy-ladder\DummySim -c Release -o spikes\dummy-ladder\DummySim\bin\run
& "spikes\dummy-ladder\DummySim\bin\run\DummySim.exe" --bb-dir "C:\Program Files\HDT" --self-test --iterations 500
```

## v1：两档插值 + 固定加密

```powershell
python spikes\dummy-ladder\scan_boards.py
python spikes\dummy-ladder\run_probe.py
python spikes\dummy-ladder\run_refine.py
python spikes\dummy-ladder\score_curves.py spikes\dummy-ladder\out
python spikes\dummy-ladder\run_wide.py
python spikes\dummy-ladder\score_curves.py spikes\dummy-ladder\out-wide
```

## v2：logistic 位置 + CI；粗档 + 自适应 4 + 2 点

```powershell
# 合成自测（不需要 BB/DLL）
python spikes\dummy-ladder\model_estimate.py --selftest
# 不重跑：用 v1 曲线比较两个估计量
python spikes\dummy-ladder\model_estimate.py --curves spikes\dummy-ladder\out-wide\curves.json
# 小样本冒烟，再全量
python spikes\dummy-ladder\run_adaptive.py --limit 20 --out spikes\dummy-ladder\out-adaptive-smoke
python spikes\dummy-ladder\run_adaptive.py --coarse ratio4
python spikes\dummy-ladder\compare_estimators.py
# 实际战果对比（AUC / Spearman；需要 data/standard/turns.jsonl）
python spikes\dummy-ladder\score_model_outcomes.py
# 战果差距的按局聚类 bootstrap
python spikes\dummy-ladder\bootstrap_outcomes.py --bootstrap 5000
# 跨 DLL 稳定性（同一批档位；需要本机 1.85.0.0 与 1.88.6.0 两个 BB 目录）
python spikes\dummy-ladder\cross_dll.py --bootstrap 2000
# 全回合敏感性（t1–t17，输出到 out-adaptive-all）
python spikes\dummy-ladder\run_adaptive.py --coarse ratio4 --turns 1-17 --out spikes\dummy-ladder\out-adaptive-all
python spikes\dummy-ladder\score_model_outcomes.py --curves spikes\dummy-ladder\out-adaptive-all\curves.json
python spikes\dummy-ladder\bootstrap_outcomes.py --curves spikes\dummy-ladder\out-adaptive-all\curves.json --bootstrap 5000
```

`out/`、`out-wide/`、`out-adaptive*/` 等由 `.gitignore` 的 `spikes/**/out*/` 系列规则忽略。模拟用本机 `C:\Program Files\HDT` 的 BobsBuddy 1.88.6.0。
