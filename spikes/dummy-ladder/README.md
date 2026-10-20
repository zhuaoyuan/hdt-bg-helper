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

## 对手侧 X50（同一 v2 管线）

```powershell
# 冒烟
python spikes\dummy-ladder\run_adaptive.py --pool 1.88.6.0 --turns 6 --side opponent --limit 6 --out spikes\dummy-ladder\out-opp-smoke
# 全量：81 局 / 937 板，约 3.6 分钟
python spikes\dummy-ladder\run_adaptive.py --pool 1.88.6.0 --turns 1-17 --side opponent --out spikes\dummy-ladder\out-opp-188
# 校验：A 己方侧回归 / B 侧对称性 ground truth / C 量纲，结果写 out-opp-188/validation.json
python spikes\dummy-ladder\verify_side_opp.py
```

`--side opponent` 时 job 带 `"measureSide": "opponent"`，DummySim 用 7 个木桩替换 `Input.Player`、保留真实 `Input.Opponent`（`player` 模式则相反，行为不变）。DummySim 的输出**始终**是木桩侧（`Input.Player`）的 win/tie/loss，所以 `merge_rows` 在 opponent 模式下把 win/loss 对调，估计量依旧拟合「真实板视角」的 P(win)。

注意：把一个己方 minion 搬到他侧时必须把 `ControlledByPlayer` 递归改成 `false`（`verify_side_opp.py` 的 `swap_false` 变体）；保留 `true` 会让战斗退化（木桩 1/1 也能 99.5% 胜）。真实 dump 的对手 minion 本来就是 `false`，因此主流程不受影响。

对手侧结论（1.88.6.0，966 board 中 38 块对手空场被跳过、另补 9 块己方空场，共 937 板）：interior 799 / below 136 / above 2，中位 CI 宽 0.148 log2；与己方 X50 分回合中位数比值 0.82–1.24（t13 后样本稀疏），Spearman(log2 X50, 场面 sum(atk+hp))=0.98。详见 `out-opp-188/validation.json`。

