# 2026-10-11 落地对战得分搜索

## 做了什么

- 按 `docs/process/prompts/score-policy-search.md` 从 `main` 开了分支 `feat/score-policy`。公式和选点没有改。
- Q-020：用诊断记录里 HDT 已经跑完的真实对战比较 `damageResults` 和 `DamageCap`。正的上限会截断样本。事实在 `facts/damage-results-cap-q020.md`。因此 \(\alpha=\beta=0\)，没有补伤害分位，也没有重跑胜平负。
- 平权曲线写在 `tools/strength/score_policy.py`。合成测试锁住：任意回合 \(0.2/0.8/0\) 的胜平负部分高于 \(0.6/0.1/0.3\)。
- 在现有 `pairs` 上搜了 \(t_1\in\{9,12,15\}\)，旁路在 `data/strength/1.85.0.0/score-policy/`。没有写 `strength.jsonl`。

## 发现

- 有名次且能算出最后 3 场分位的局是 **11**。三个新点和旧公式（平权 0.5）的 Spearman 都是 **−0.009**，区间很宽且含 0。分位的平均高度有微小移动，11 局的排序没有变。
- ADR-0018 的三条有效条件都不成立。搜索到此停止。退出标准第 1、3 条和复盘页上的分位仍是旧得分。

## 留下什么

- 现行分位文件不动。有名次的局凑到至少 12 之后才能再搜；伤害项仍不要用被上限截断的样本。
