# 2026-10-05 P2-T1 数据采集短方案 + ADR

## 做了什么

所有者确认完成 P2-T1 后落地文档：

1. 方案 [`design/P2-data-capture.md`](../design/P2-data-capture.md)（approved）：原始层 = BgHelperDiag 目录；标准层 = 离线导入每回合表；压缩与保留；T2/T3 边界。
2. [ADR-0004](../decisions/0004-capture-light-compute-async.md) 按 P2 重估细化后 **accepted**（两层够用、不单独做 schema 演进框架、局末压缩 records）。
3. 新 [ADR-0010](../decisions/0010-hdt-input-dump-as-primary-source.md) **accepted**：HDT `_input`/`Output` 转储为主，实体快照为后备；P2 不实现 InputBuilder。
4. 同步 [`architecture/overview.md`](../architecture/overview.md)、design/decisions 索引、`roadmap.md`（T1 勾选）、`status.md`；Q-002 注明已升为主数据源依赖。

## 发现 / 决定要点

- 不再设计「实体 → InputBuilder → 模拟」主路径；与 P2-T0 往返证据一致。
- 退出标准数字未改，与方案第 3.3 / 第 5 节对齐。

## 下一步

按 status：优先 P2-T3 离线导入（可与 T2 并行），再 P3-T0。
