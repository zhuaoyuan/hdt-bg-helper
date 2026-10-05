# 方案：离线重放与往返验证

- **状态：** implemented
- **任务：** P2-T0
- **作者 / 日期：** agent / 2026-10-05
- **相关：** ADR-0002、ADR-0006、ADR-0008；`facts/bobsbuddy-public-api.md`、`facts/diag-capture-batch-20261003.md`、`facts/diag-capture-measured.md`、`facts/replay-roundtrip.md`；Q-009、Q-011、Q-013

## 实现记录

- 交付在 `spikes/replay-harness/`（尚无 `src/`）。
- 验收：BB 1.78.1 + 1.85.0 共 261/261 场同版本往返通过；Q-009/011/013 见 `facts/replay-roundtrip.md`。
- 相对方案补充：匿名化修复不止 `Player` 键，还包括 `ControlledByPlayer`、`Windfury`/`MegaWindfury`、`DuosInputPlayer*`；3σ 判定加了 `1.5/n` 量级地板以避免 0 vs 0.001 假阴性。
- 1.80.1 / 1.81.2 仍 `skipped_no_dll`。

## 1. 目标与非目标

**目标**

1. 从诊断记录的 HDT `_input` 反射转储还原 BB `Input`，按 `meta.bobsBuddy.fileVersion` 在**独立进程**调用同版本 `BobsBuddy.dll`，与记录的 `Output` 对照胜/平/负率。
2. 处理已知脏数据：残留 invoker（只取 `combat_phase=true` 分段内记录）、匿名化误改的 `Player` / `$type`。
3. 用同一套工具跑 Q-009（耗时）、Q-011（跨 BB 版本）、Q-013（未赋值字段扰动）并写回 `docs/facts/`。

**非目标**

- 不从实体快照 / Power.log 重建 Input（那是后备路径，归 P2-T1/T3）。
- 不修诊断插件匿名化（P2-T2）。
- 不产出每回合标准层表（P2-T3）。
- 不要求 `damageResults` 逐条一致；不要求本机已有全部历史 BB DLL 才能宣称 T0 完成——缺 DLL 的版本标 `skipped_no_dll`。

## 2. 依据

| 依据 | 用法 |
| --- | --- |
| Q-001 / `bobsbuddy-public-api.md` | 独立进程可调 `SimulationRunner.SimulateMultiThreaded` |
| `ReflectionDumper` 只转储字段 | 还原走字段反射；属性（如 `baseAttack`）依赖 `_data` 等字段 |
| `diag-capture-measured.md` | 对照只用本场 `2022=0` 之后 / 本场 combat 分段内的 `hdt_bb` |
| `diag-capture-batch-20261003.md` §4.1–4.3 | 匿名化键修复；版本路由；`DiscardCounter` 等跨版本字段 |
| 本机 DLL | `app-1.58.3` → BB 1.78.1；`app-1.58.6` / 团子 → BB 1.85.0。1.80.1 / 1.81.2 暂缺 |

**假设：** 按字段回填 + 工厂/`$type` 构造随从，足以复现 HDT 当场五率（抽样误差内）。若不成立：记录失败模式，再决定是否改为「只信任 Output、Input 仅作交叉模拟原料」。

## 3. 方案

```mermaid
flowchart LR
  A[records.jsonl + meta.json] --> B[Python: 分段 / 修键 / 抽 Combats]
  B --> C[每场 _input JSON]
  C --> D[ReplaySim.exe --bb-dir]
  D --> E[模拟 Output + 耗时]
  E --> F[与记录 Output 对照 / 报告]
```

### 3.1 组件

| 组件 | 位置 | 职责 |
| --- | --- | --- |
| 编排与报告 | `spikes/replay-harness/tools/roundtrip.py` | 扫目录、过滤、修键、按版本调进程、统计、Q-009/011/013 模式 |
| 模拟进程 | `spikes/replay-harness/ReplaySim/` | net472 x64；`--bb-dir` 加载该目录的 BB/HearthDb；JSON→Input→模拟→JSON |
| DLL 目录表 | `spikes/replay-harness/bb-dirs.json`（本机路径，可覆盖） | `fileVersion` → 含 `BobsBuddy.dll` 的目录 |

代码放在 `spikes/`：`src/` 尚未建立；T0 的验收物是可重复跑的工具 + 事实文档。

### 3.2 选哪一条 `hdt_bb`

对每个 `combat_phase=true … false` 分段：

1. 丢掉分段外的全部 `hdt_bb`（消除上一局残留）。
2. 在分段内取 `state == "Combat"` 且 `hasInput` 且 `hasOutput` 的记录；若有多条，取 `reRunCount` 最大、同值取 `lineSeq` 最大（最接近开战补录后的终态）。
3. 匿名化修复后再交给 ReplaySim。

### 3.3 匿名化键修复

对 `_input`（及嵌套）递归：

- 键 `player_<8hex>` → `Player`；`player_<8hex>Teammate` → `PlayerTeammate`
- `$type` 字符串里的 `.player_<8hex>` → `.Player`
- 不改其它 `player_<hash>` 显示名占位（实体名等）

### 3.4 Input 还原（ReplaySim）

1. 建立 `$id` → 节点表；解析时解析 `$ref`。
2. `new Simulator()`（live）；`new Input()`；用已有 `Player`/`Opponent` 实例填字段，不 new 第二套再替换（避免 `_input` 环断开）。
3. 跳过：`$id`/`$type`/`$ref`/`$skipped`/`$error`/`$truncated`/`$entity`/`$card`/`$dbCard`；字段名 `Simulator`；随从/附魔上的空壳 `FriendlySide`/`OpposingSide`/`TeammateSide`/`FriendlyHand`（dump 里常是空 List，应在加入 `Side` 后由 BB 接线或指向真实列表）。
4. 集合：清 `items` 后逐个还原再 `Add`。
5. 随从/手牌/饰品/任务等：优先 `MinionFactory.CreateFromCardId(CardID, ControlledByPlayer)`（或对应 Factory）；若 `$type` 为具体子类且工厂类型不符，再 `Activator` 用公开构造；然后按字段覆盖（含 `_data`、`_enchantments`）。
6. 枚举按名解析；可空值类型按目标字段类型转换。

### 3.5 模拟与对照

- 迭代次数：默认用记录 `Output.simulationCount`（常见 ~10000 / ~19998）；线程数 `max(1, ProcessorCount/2)`；`maxDuration` 默认 5000 ms（与 HDT 上限同级，可调）。
- 对照：`winRate`/`tieRate`/`lossRate`（及可选 `myDeathRate`/`theirDeathRate`）。判定：差值落在两次独立二项抽样合并标准误的 3σ 内（n₁=记录 sims，n₂=重放 sims；对 win/tie/loss 各检，全部通过才算 OK）。
- 报告字段：gameId、turn、bbVersion、Δ、是否通过、耗时、失败原因（hydrate / simulate / mismatch / no_dll）。

### 3.6 附带实验

| 问题 | 做法 |
| --- | --- |
| Q-009 | 对可用 DLL 的全部 `ready` 场测量墙钟；汇总每场/每局；对照「每局 ≤ 10 分钟」默认标准 |
| Q-011 | 同一 `_input` 用采集版 DLL 与另一可用版 DLL 各跑一次，量化五率差；缺 DLL 的采集版跳过 |
| Q-013 | 同场面基线重放 vs 将 `DeepBluesCounter`/`AnySpellCounter`/`BackToBackCounter`（及清单中其它未赋值标量）设为非 0 后再跑；看五率是否变化 |

## 4. 考虑过的替代方案

| 方案 | 不选原因 |
| --- | --- |
| 从实体快照重建 Input | 工作量大、且本任务已有完整 `_input` 转储 |
| 进程内多版本 AssemblyLoadContext | net472 宿主别扭；独立进程更贴 P3 批量形态 |
| 只对比团子文本五率 | 不能证明「我们还原的 Input」可驱动 BB；团子对照留给 T3 |

## 5. 验收方式

```powershell
# 构建（示例，bb-dir 指向含 BobsBuddy.dll 的目录）
& "C:\Program Files\dotnet\dotnet.exe" build spikes/replay-harness/ReplaySim -c Release

# 往返：仅本机有 DLL 的版本
python spikes/replay-harness/tools/roundtrip.py --root data/BgHelperDiag --bb-map spikes/replay-harness/bb-dirs.json

# 实验
python spikes/replay-harness/tools/roundtrip.py --root data/BgHelperDiag --mode q009
python spikes/replay-harness/tools/roundtrip.py --root data/BgHelperDiag --mode q011
python spikes/replay-harness/tools/roundtrip.py --root data/BgHelperDiag --mode q013 --limit 20
```

通过标准：

1. BB 1.78.1 与 1.85.0 队列上，成功重放的场次中，五率 3σ 通过率 ≥ 95%（排除 truncate/dump 错误）。
2. Q-009/011/013 各有一份 `docs/facts/` 结论（或合并为一篇 `facts/replay-roundtrip.md` 内分节）。
3. 缺 1.80.1/1.81.2 DLL 时报告 `skipped_no_dll`，不算失败。

## 6. 风险与回退

| 风险 | 缓解 |
| --- | --- |
| 嵌套 `$ref`/附魔/手牌实体还原失败 | 先保证 Side 随从+英雄技能+标量；失败场记原因；不全局停 |
| CardDefs 与采集时不一致 | 优先用 bb-dir 旁 `HearthDb.dll`；若偏差大，再加载 `%APPDATA%\...\CardDefs`（记入风险） |
| 缺中间 BB 版本 | 不阻塞 T0；Q-011 用 1.78.1↔1.85.0 |
| 还原后五率系统性偏离 | 停扩 P3-T0 交叉模拟依赖；改查 hydrate 缺口 |

## 7. 任务拆分

1. 本方案 + `bb-dirs.json` 模板。
2. ReplaySim：加载 DLL、hydrate、模拟、stdout JSON。
3. `roundtrip.py`：分段、修键、对照、汇总。
4. 跑 1.78.1 + 1.85.0 全量往返；修 hydrate 直到通过率达标或记明失败模式。
5. Q-009 / Q-011 / Q-013 实验 + `docs/facts/replay-roundtrip.md`；更新 status / worklog / open-questions / roadmap。
