# 提示词：模拟池版本表与对战重刷

> 用途：把「Bob's Buddy 文件版本」和「战力/对战共用的模拟池」拆开。兼容测试通过的实际版本进同一个池；对战与分位按池计算，并按此重刷已有数据。  
> 本文件是任务边界。先写短方案和 ADR，再实现。不要在兼容测试未通过时把版本并池。

## 所有者可粘贴的短指令

```text
按 docs/process/prompts/sim-pool-versions.md 做模拟池版本表，并把已有数据按新池重刷。
1.85.0.0 与 1.88.6.0 的同输入兼容测试已有结论（facts/replay-roundtrip.md §3.2），可直接并入同一模拟池；其它实际版本先各成一池。
先写方案和 ADR，再改代码、迁移缓存、重算该池分位。
不要 push，除非我要求。
```

## 开始前（必读顺序）

1. `AGENTS.md` → `docs/status.md` → `docs/roadmap.md`（P3 段）。
2. [`docs/design/P3-T1-strength-engine.md`](../../design/P3-T1-strength-engine.md) §3.1–3.6、§3.9；[`docs/design/P3-matchup-store.md`](../../design/P3-matchup-store.md)。
3. [`docs/decisions/0011-strength-pool-round-robin.md`](../../decisions/0011-strength-pool-round-robin.md)。本任务**只改「按 bbVersion 分桶」这一条**；留一局循环赛、面板、L0/L1、`insufficient` 不变。L2（把未测试的上一版场面拿来重模拟）仍然关闭，由模拟池成员关系代替。
4. [`docs/facts/replay-roundtrip.md`](../../facts/replay-roundtrip.md) §3：1.78.1→1.85.0 有显著偏差；1.85.0→1.88.6 同输入 100/100 在 3σ 内。§3.3 里「因此不混参照池」被本任务的所有者决定取代，实现时用新 ADR 写明，不要默默改那句事实。
5. 代码：`tools/strength/`（`cache.py` 的 `pairs` / `matchups`，`engine.py` 入池）、`tools/ReplaySim/bb-dirs.json`。

## 名词（实现时沿用，不要再改名）

| 名字 | 字段 | 含义 |
| --- | --- | --- |
| 实际版本 | `bbVersion` | 采集时 `meta.bobsBuddy.fileVersion`，如 `1.85.0.0`、`1.88.6.0`。选哪份 DLL 重放单场 Input 时仍用它。 |
| 模拟池 | `simPool` | 战力参照池和对战缓存的分组键。一个池里可以有多个实际版本。池 Id **等于池内最早的 `bbVersion`**。 |

例：`1.85.0.0` 与 `1.88.6.0` 同池，则 `simPool = 1.85.0.0`。若将来某个新 DLL 不兼容，它单独成池，池 Id 就是那个新的 `bbVersion`。

## 本任务范围（做）

### A. 版本表与维护

1. 仓库内版本表（不要放进 gitignore 的 `data/`）：`tools/strength/sim_pools.json`。每条实际版本一行，至少包含：`bbVersion`、`simPool`、`joinedAt`（日期）、`evidence`（事实文档路径或「未测试，单独成池」）。
2. 初始内容：
   - `1.85.0.0` → 池 `1.85.0.0`（建池版本）。
   - `1.88.6.0` → 池 `1.85.0.0`。证据：`facts/replay-roundtrip.md` §3.2（2026-10-07，同输入 100/100）。**不要为这一对重跑 100 场**，除非该 JSON 结果文件丢失且事实文档不足以引用。
   - 本机出现过、但未与 1.85 做过通过测试的实际版本（至少 `1.78.1.0`；`1.80.1.0` / `1.81.2.0` 若缺 DLL 也一样）各自单独成池，池 Id = 自身 `bbVersion`。不要猜测它们与 1.85 兼容。
3. CLI（名字可按代码风格微调，须能复跑）：
   - 列出实际版本 → 模拟池。
   - `pool-check`：对「候选新实际版本」与「目标池里最新的已安装实际版本」做同输入跨 DLL 重放。样本沿用 Q-011：该候选版本（或目标池）上已有的真实场面，两边 DLL 各跑一次。通过条件与 `facts/replay-roundtrip.md` §3 相同：**五率 3σ 一致，且没有像 1.78→1.85 那样的显著偏差场**。不通过则拒绝并池，新版本单独成池。
   - `pool-join`：只有检查已通过并写进 `facts/` 之后，才改 `sim_pools.json`。禁止无证据改表。
4. 短方案 `docs/design/P3-sim-pool.md`（状态实现完成后改为 `implemented`）和 ADR（`accepted`，注明所有者于派发本提示词时确认方向）。ADR 写清：取代 ADR-0011 的「参照池按 BB 文件版本分桶」；不取代留一局循环赛。E5 / 旧 L2 的 \|ΔQ\| 门槛**不是**并池条件——并池条件是同输入五率兼容。旧 L2 保持关闭。
5. 更新 [`version-upgrade.md`](version-upgrade.md)：HDT/BB 升级后的兼容性判断改为「跑 `pool-check`，再决定并池或新池」，不要只写「按文件版本永远分桶」。

### B. 对战与分位改为按模拟池

1. 入池、面板、L0/L1、`G_min`、`matchups` 的场面身份都按 **`simPool` + 回合**，不再按单独的 `bbVersion`。同一池里，1.85 的场面和 1.88.6 的场面互相作为同伴和对手。
2. 缓存：
   - `pairs` 仍存次数，键改为 `simPool | assemblerVersion | 规范化 Input`（不再把 DLL 文件版本放进 `pairKey`）。同一拼装输入在池内只留一份次数。
   - `matchups` 主键改为 `(simPool, rowBoardId, colBoardId)`，仍只指向 `pairKey`。
   - 场面行保留原来的 `bbVersion`，以便知道这局是用哪份 DLL 采集的。
3. **新的**跨实际版本对（池内一边是 1.85 场面、一边是 1.88.6 场面，且缓存没有这份 Input）：用该池**已安装成员里最新的 DLL** 模拟（当前是 `1.88.6.0`）。迭代次数仍是 500。
4. 分位输出写到 `data/strength/<simPool>/strength.jsonl`。行内同时保留 `bbVersion`（采集版本）和 `simPool`。不要覆盖删除旧的 `data/strength/1.85.0.0/` 与 `data/strength/1.88.6.0/`；在 status 里注明它们是并池前的结果。

### C. 按新池重刷已有数据

顺序固定，避免整池重模拟：

1. 读现有 `data/strength/cache.sqlite`。对将进入池 `1.85.0.0` 的旧 `pairs`：按 `(rowBoardHash, colBoardHash, shellHash, assemblerVersion)` 归并。同一 Input 在 1.85 与 1.88.6 各有一行时，**把次数相加合并**（与现有 `merge_pair` 相同），不要丢弃、不要为了换 DLL 重跑。
2. 归并后，只模拟仍然缺失的池内对（主要是 1.85 场面 × 1.88.6 场面，以及薄回合才需要的 L1）。先打出缺对数量和粗算耗时，再开跑。
3. 对该 `simPool` 重算分位（`missingAfter=0`）。第二次对同一池 `backfill --dry-run`：`pairsMissing=0`。
4. 其它单独成池的实际版本：不重算、不删它们已有的 `pairs`。迁移时不要把 1.78 的次数并进 1.85 池。

## 明确不做

- 不把 1.78.1 / 1.80.1 / 1.81.2 并入 1.85 池。
- 不启用旧 L2，不用 E5 的分位差门槛决定并池。
- 不重跑 E1–E5 校准，不改 `iterations`、`K`、`G_min`、`w_relax`。
- 不重写复盘 HTML（除非重刷分位时顺手；默认留给后续）。
- 不 `git push`。`cache.sqlite` 与 `strength.jsonl` 仍不入库。

## 验收

```powershell
python -m unittest discover -s tools/strength
```

- 单测：版本表把 1.88.6 映到池 `1.85.0.0`；1.78.1 不映到该池；`pairKey` 含 `simPool`、不含 DLL 文件版本；同 Input 两行次数合并；未通过检查时 `pool-join` 不改表。
- 本机：池 `1.85.0.0` 的分位文件存在，候选数大于并池前 1.88.6 单独的 277（因为 1.85 的己方场面进入同一池）。`missingAfter=0`。dry-run 回填 `pairsMissing=0`。
- `docs/facts/` 记下并池成员与证据路径；`docs/status.md` 与当日 worklog 写明旧的按文件版本分位文件已停用、新路径在哪。

## 风险

- 同输入五率接近，不等于混池后的分位与「只用 1.88.6」完全相同。重刷后的分位以新文件为准，并在 worklog 写一行：与旧 `strength/1.88.6.0/strength.jsonl` 比，共同场面的分位差中位数（不必设门槛，记下来即可）。
- 跨版本缺对可能很多。缺对规模先打印；若粗算超过 2 小时，停下来在 worklog 写数字，等所有者决定是否只先并「同回合、双方都已在池内」的子集。不要静默砍掉某个版本的场面。
