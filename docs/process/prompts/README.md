# 流程提示词

> 这份文档回答：每个研发环节该让 agent 怎么做；所有者怎么用这些提示词给 agent 派任务。

## 使用方式

所有者给 agent 下指令时，指明任务编号和提示词即可，例如：

```text
执行 P1-T1，按 docs/process/prompts/research-spike.md。
```

```text
为 P2-T1 写方案，按 docs/process/prompts/write-design.md。
```

agent 读到提示词后按其中的步骤执行。每份提示词都默认 agent 已按 `AGENTS.md` 读过 `status.md`。

## 索引

| 提示词 | 用途 |
| --- | --- |
| [`research-spike.md`](research-spike.md) | 调研外部系统行为，核实事实，关闭未决问题 |
| [`write-design.md`](write-design.md) | 为任务写技术方案 |
| [`write-adr.md`](write-adr.md) | 记录一项决策 |
| [`implement-task.md`](implement-task.md) | 按方案实现、测试、提交 |
| [`verify-data.md`](verify-data.md) | 检查采集数据质量，做往返验证 |
| [`review.md`](review.md) | 提交前自审 |
| [`version-upgrade.md`](version-upgrade.md) | HDT / Bob's Buddy / 游戏版本更新后的同步与复核 |
| [`session-handoff.md`](session-handoff.md) | 会话收尾交接 |

## 维护

提示词效果不好时（agent 反复犯同一类错误），直接修改对应提示词，并在 worklog 里写明改了什么、为什么。
