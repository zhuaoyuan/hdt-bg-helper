# 离线重放往返验证与 Q-009 / Q-011 / Q-013

> 这份文档回答：诊断记录里的 `_input` 反射转储能否在独立进程还原为 BB `Input` 并复现记录中的胜/平/负率；真实场面的独立进程耗时；跨 BB 版本偏差；HDT 未赋值字段开战时是否影响结果。

```text
样本：data/BgHelperDiag，BB 1.78.1.0（8 局 / 85 场）+ 1.85.0.0（15 局 / 176 场）= 23 局 / 261 场有 Output 的 Combat
（同批另有 1.80.1 / 1.81.2 共 24 局因本机无对应 BobsBuddy.dll 未跑，标 skipped_no_dll）
工具：spikes/replay-harness/（ReplaySim + tools/roundtrip.py）
DLL：%LOCALAPPDATA%\HearthstoneDeckTracker\app-1.58.3（BB 1.78.1）、app-1.58.6（BB 1.85.0）
对照：记录 Output 的 win/tie/loss × simulationCount；判定为合并二项 SE 的 3σ，并加 1.5/n 量级地板
最后核实：2026-10-05
```

## 1. 往返验证（同版本 DLL）

| 项 | 结果 |
| --- | --- |
| 尝试场次 | 261（另 1 场分段内无 Output） |
| 通过 | **261 / 261（100%）** |
| hydrate / 模拟失败 | 0 |
| 残留 invoker | 已排除：只取 `combat_phase=true…false` 分段内、`state=Combat` 且 `hasOutput`、最大 `reRunCount` 的一条 |

匿名化误伤修复（导入侧，不改原始文件）后才能对腐蚀局通过。本批见到的结构性碰撞：

| 腐蚀形态 | 还原 |
| --- | --- |
| 键 `player_<8hex>` / `…Teammate` | `Player` / `PlayerTeammate` |
| `$type` = `BobsBuddy.Simulation.player_<8hex>` | `BobsBuddy.Simulation.Player` |
| `ControlledByplayer_<8hex>` | `ControlledByPlayer`（未修时对手随从默认 `controlled=true`，五率可完全颠倒） |
| `player_<8hex>fury` / `Megaplayer_<8hex>fury` | `Windfury` / `MegaWindfury` |
| `DuosInputplayer_<8hex>` | `DuosInputPlayer`（及 Teammate） |

未修时同样本曾出现约 27 场 mismatch（多集中在名含 `Player`/`Wind` 的局）。修后 100% 通过。

复现：

```text
dotnet build spikes/replay-harness/ReplaySim -c Release -p:HdtDir=%LOCALAPPDATA%\HearthstoneDeckTracker\app-1.58.6 -o spikes/replay-harness/ReplaySim/bin/run
python spikes/replay-harness/tools/roundtrip.py --root data/BgHelperDiag --versions 1.78.1.0 1.85.0.0
```

## 2. Q-009：独立进程耗时

每场单独拉起 `ReplaySim`（含加载 BB/HearthDb + hydrate + 模拟）。迭代次数取记录的 `simulationCount`（本批多为 10000），线程数 `ProcessorCount/2`，`maxDuration=5000`。

| 指标 | 模拟 `elapsedMs` | 墙钟 `wallMs`（含进程启动与 hydrate） |
| --- | ---: | ---: |
| 场次 | 261 | 261 |
| min / p50 / p90 / max | 109 / 411 / 679 / 1046 | 1265 / 1596 / 1876 / 2224 |
| 全部合计 | ≈111 s | ≈418 s |
| 每局合计（仅模拟）max | ≈8.1 s | — |
| 超过「每局 ≤ 10 分钟」 | **0** | **0** |

结论：真实场面独立进程模拟耗时与 HDT 进程内日志（约 74–854 ms）同量级；即使用「一场一进程」的笨编排，23 局全部远低于赛后后台 10 分钟/局的默认标准。P3 批量若常驻进程或批量喂入，hydrate/启动开销还可再降。

## 3. Q-011：跨 BB 版本

对采集版为 1.78.1 的场面，用同 Input 在 1.78.1 与 1.85.0 上各跑一次（样本 40 场）。

| 结果 | 场次 |
| --- | ---: |
| 五率在 3σ（含地板）内一致 | 37 |
| 显著偏差 | **3**（Δwin 约 0.05 / 0.08 / **0.23**） |

结论：**重放与批量模拟必须按 `meta.bobsBuddy.fileVersion` 选 DLL**；用新版 DLL 跑旧场面会在少数局出现不可忽略的五率漂移。1.80.1 / 1.81.2 本机暂无 DLL，未测；策略不变。

## 4. Q-013：未赋值标量扰动

在 30 场（双方至少 2 随从）上：基线重放 vs 将双方 `DeepBluesCounter` / `AnySpellCounter` / `BackToBackCounter` 均设为 7 后再跑。

| 结果 | 场次 |
| --- | ---: |
| 五率无显著变化（insensitive） | **30 / 30** |

结论：就本批真实场面与上述六个标量而言，开战时把它们从 0 改成非 0 **不改变**模拟五率。与「HDT 从不赋值、Input 上恒为 0」一致；**不要求**为这些字段单独采集。未覆盖 `Minion.SecondaryRace` / `AvengeCounter` 等随从侧未赋值成员（工厂创建时通常已带好种族相关状态）。

## 5. 限制

- CardDefs 使用 bb-dir 旁 `HearthDb.dll` 内置数据，未再加载 `%APPDATA%\...\CardDefs`；本批往返仍 100% 通过。
- 随从具体子类名若也被匿名化误伤（本批仅见 7 处 Pirate `*teNavigator`），仍靠 `CardID` + `MinionFactory.CreateFromCardId` 创建。
- 输出对照不含 `damageResults` 逐条一致。
