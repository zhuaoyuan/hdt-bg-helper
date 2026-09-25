# 2026-09-25 所有者确认 Q-003

## 目标

把所有者对 `facts/licensing.md` 四个判断点的答复写进仓库，解除 ADR-0002 的许可阻塞。

## 做了什么

1. 新增 [ADR-0006](../decisions/0006-personal-plugin-use-of-hdt-bobsbuddy.md)（accepted）：个人非商业、调用公开 API、实时战力分位均为合理用途；仓库可公开但不入库 HDT / Bob's Buddy 二进制或反编译代码。
2. 将 [ADR-0002](../decisions/0002-bobsbuddy-as-primary-simulator.md) 标为 accepted，使用方式指向 ADR-0006。
3. 关闭 Q-003；`facts/licensing.md` 末节改为记录判断并指向 ADR-0006。
4. 同步 `architecture/overview.md`、`decisions/README.md`、`status.md`。

## 发现

无新的外部事实。所有者的四点答复与调研时列出的问题一一对应，没有附加条件。

## 留下的东西

- 新增：`docs/decisions/0006-personal-plugin-use-of-hdt-bobsbuddy.md`、本日志。
- 许可阻塞已解除。下一步仍是 P1-T1（补全数据清单）。
