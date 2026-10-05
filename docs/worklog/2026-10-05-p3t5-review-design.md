# 2026-10-05 P3-T5 复盘视图原型方案

## 做了什么

- 写了 [`design/P3-T5-review-view.md`](../design/P3-T5-review-view.md)；新增 [ADR-0013](../decisions/0013-offline-static-review-html.md)。
- 所有者确认三点后：方案 → `approved`，ADR-0013 → `accepted`；同步 architecture / design / decisions 索引与 `status.md`。
- **本部分仅文档提交；不开始 `tools/review_view` 落地。**

## 所有者决定（2026-10-05）

1. 接受离线静态 HTML（不要 Streamlit / HDT 内嵌赛后窗）。
2. v1 不做方向/关键牌标注（只留只读 `notes.json` 口子）。
3. **不与 P3-T3 并行**：先 T3，再用真实 `strength.jsonl` 实现 T5。

## 留下什么

- 下一步编码：P3-T3（见 `process/prompts/p3-t3-percentile.md`）。
- T5.1–T5.4 待 T3 完成后另开会话。
