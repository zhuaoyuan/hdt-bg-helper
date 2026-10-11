# 提示词：对战得分第二轮搜索

> 用途：按 [`R-score-policy-search-v2.md`](../../design/R-score-policy-search-v2.md) 与 [ADR-0019](../../decisions/0019-score-search-shape-and-midgame.md)（accepted）搜索平权形状。

## 所有者可粘贴的短指令

```text
执行对战得分第二轮搜索，严格按 docs/process/prompts/score-policy-search-v2.md。
形状、标签和确认门以 docs/design/R-score-policy-search-v2.md、ADR-0019 为准，不要改。
未过确认门不要覆盖 strength.jsonl。不要 push。
```

## 开始前

1. `AGENTS.md` → `docs/status.md`。ADR-0019 已接受；若状态被改回 proposed，停下来问所有者。
2. 方案 §3、§5、§7。Q-020 与 `facts/score-policy-search-raw-place-20261011.md`。
3. 从当前分支继续，或从 `main` 建分支 `feat/score-policy-v2`。不要基于「上一轮 \(t_1=15\) 已经字面有效」去替换分位文件。

## 顺序

1. 实现 10 条曲线和方案 §5 的合成测试。一个 commit。
2. 估伤害摘要的回填时间。超过 2 小时则停在工作日志里，不要开跑。通过才写入败局摘要，不改胜平负次数。一个 commit。
3. 拟合半选曲线，确认半按方案 §3.4 判定。结果写入 `data/strength/1.85.0.0/score-policy-v2/`，并写 `docs/facts/`。一个 commit。
4. 只有第 3 步采用了曲线，才搜 \(\beta\)。再一个 commit。
5. 只有确认门通过，才备份并替换 `strength.jsonl`，并按 ADR-0018 重做退出第 1、3 条和复盘页上的分位。

## 明确不做

- 加第 11 条曲线，或按回合自由设权。
- 把造成伤害、伤害起始回合、升满回合数放进网格。
- 用 0.006 的差距或上一轮旁路结果替换现行分位。
- 确认门未过时改 T4 结论或重做复盘。
- `git push`。
