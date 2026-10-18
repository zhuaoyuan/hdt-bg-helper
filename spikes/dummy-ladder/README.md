# 木桩梯队（旁路）

把真实己方场面和一个「7 个攻=血完全相同、无词条」的对手打，用五五开那一档的攻血当作绝对值 \(X_{50}\)。

不进入主线战力。结论见 `docs/facts/dummy-ladder-20261018.md`，方案见 `docs/design/R-dummy-ladder.md`。

```powershell
& "C:\Program Files\dotnet\dotnet.exe" build spikes\dummy-ladder\DummySim -c Release -o spikes\dummy-ladder\DummySim\bin\run
& "spikes\dummy-ladder\DummySim\bin\run\DummySim.exe" --bb-dir "C:\Program Files\HDT" --self-test --iterations 500
python spikes\dummy-ladder\scan_boards.py
python spikes\dummy-ladder\run_probe.py
python spikes\dummy-ladder\run_refine.py
python spikes\dummy-ladder\score_curves.py spikes\dummy-ladder\out
python spikes\dummy-ladder\run_wide.py
python spikes\dummy-ladder\score_curves.py spikes\dummy-ladder\out-wide
```

`out/` 与 `out-wide/` 被 `spikes/**/out/` 忽略。模拟用本机 `C:\Program Files\HDT` 的 BobsBuddy 1.88.6.0。
