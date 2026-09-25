# 提示词：写架构决策记录（ADR）

你要记录一项决策。

## 步骤

1. 确认值得写：对照 `docs/decisions/README.md` 中"什么时候写"。
2. 查看已有 ADR，确认不是重复；如果是推翻旧决定，新 ADR 里写明"取代 ADR-NNNN"，并在旧 ADR 状态行加注"superseded by ADR-MMMM"（只改状态行，不改正文）。
3. 复制 `docs/decisions/0000-template.md`，序号取当前最大值 + 1。
4. 填写：
   - **背景**引用事实文档，不凭印象；
   - **决定**写成可以直接执行的陈述；
   - **考虑过的方案**至少两个；
   - **推翻条件**写具体的可观察证据。
5. 状态默认 `proposed`。只有所有者明确确认后才能改为 `accepted`，并在状态行写明确认方式和日期。
6. 更新 `docs/decisions/README.md` 索引；如果决定影响架构，同步更新 `docs/architecture/overview.md`（标注"依赖 ADR-NNNN（提议）"或直接更新）。
