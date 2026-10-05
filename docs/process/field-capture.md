# 继续采集（诊断插件 + 可选团子对照）

> 打酒馆战棋、把诊断记录带回来；若用团子版，再带上对战记录文本做交叉验证。不需要在打本机上装 Git / .NET / Python（验收可在有仓库的机器上做）。
>
> 插件版本：HdtDiagLogger **0.2.0**（P2-T2）。采集环境默认见 ADR-0008（团子版 + 对战记录对照）；插件字段语义仍以官方 HDT 为准（ADR-0007）。

## 结论：插件够不够用

**对「继续打、继续记」够用。** 请尽量用 **0.2.0**（修了匿名化误伤、局末压缩 `records`）；旧 DLL 也能记，但新数据质量更好。

它已经稳定做到：

- 官方 / 团子 HDT 均能加载（共用 `%APPDATA%\HearthstoneDeckTracker\Plugins`）；不卡顿；BattleTag 落盘前匿名化（0.2.0 起不再误改 JSON 里的 `Player` / `$type` 等）。
- 每场战斗记下开战实体快照、HDT 交给模拟器的 Input、模拟 Output、战后快照、整局 Power 行。
- 官方批与团子单局均验收通过；团子一局与对战记录阵容/五率 10/10 对齐（`facts/diag-tuanzi-compat-20261004.md`）。

下列事项**不要为它们停手**（分析侧处理，或靠多打补样本）：

- 实体快照仍拍在标签 `3533`，HDT 真正做模拟是约 80 行之后的 `2022`（本批数字仍一致）。
- 新对局开头会倒出上一局残留 Input（导入时丢掉即可）。
- 双人 / 畸变 / 战斗中补录样本还很少——这靠多打，不靠改插件。

---

## 出发前：从本机拷走这两样

关 HDT 之后，拷到 U 盘 / 网盘（**只要插件 DLL，不要拷 HDT 或 Bob's Buddy 的任何文件**）：

| 拷什么 | 本机位置 |
| --- | --- |
| `HdtDiagLogger.dll`（约 43–45 KB） | `%APPDATA%\HearthstoneDeckTracker\Plugins\HdtDiagLogger.dll` |
| 本说明（可选） | 仓库 `docs/process/field-capture.md` |

可选：同一目录下的 `salt.txt`。带上则两台机器上同一个人会映射成同一个 `player_xxxxxxxx`；不带则新机器自己生成一份盐，分析仍然可用，只是跨机器对不上同一个人。

---

## 装 HDT + 插件

### A. 默认：团子版（推荐，便于对照）

1. 使用已安装的团子版 HDT（本机常见目录 `C:\Program Files\HDT`）。**可以照常拔线**（ADR-0009）：拔线回合的战果由 agent 在分析时尽量从上下文还原，还原不了也可以接受。
2. 确认炉石 **Power** 日志已开。
3. 把 `HdtDiagLogger.dll` 放到 `%APPDATA%\HearthstoneDeckTracker\Plugins\`（官方与团子共用此目录）。
4. 若 DLL 来自网盘：右键 → 属性 → 「解除锁定」。
5. 启动团子版 → 选项 → 插件 → 启用 **BG Helper Diagnostic Logger**。
6. HDT 日志应有：`[BgHelperDiag] loaded 0.2.0; HDT=…, BobsBuddy=…`
7. 团子对战记录目录（本机）：`C:\Program Files\HDT\对战记录\`，按日文件名如 `yyyy年MM月dd日.txt`。

### B. 备选：官方版

按 [hsdecktracker.net](https://hsdecktracker.net/) 安装官方 HDT，同样把插件放进上述 `Plugins\`。官方版**没有**同等对战记录文本，交叉验证只能靠 diag 自身一致性 / 日后重放。

点插件旁的 **Open records folder** 应打开 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\`。

---

## 怎么打

正常打酒馆战棋即可。**先启用插件，再排队**；中途才打开插件的那一局可能不完整。

每打完一局、回到菜单后，`BgHelperDiag\` 下应多一个文件夹，形如 `20261004_200638_13406d\`，里面至少有：

| 文件 | 说明 |
| --- | --- |
| `meta.json` | 用记事本打开：`errors` 应为 `0`；`probeInitError` 应为 `null` 或空；`pluginVersion` 应为 `0.2.0` |
| `records.jsonl.gz` | 0.2.0 局末压缩（约数 MB / 局）。若中途杀了 HDT，可能留下未压缩的 `records.jsonl`，也要保留 |
| `power.log.gz` | 对局正常结束后才会出现。若中途杀了 HDT，会留下未压缩的 `power.log`，也要保留 |

**优先补样本（遇到就打，不必刻意重开）：** 带任务、对手有奥秘、Malorne、场上有畸变、战斗中有「装填 / 手牌变化」一类效果。双人可以打，插件会记，但不保证覆盖。构造模式不用管，插件不会为它们建目录。

**不要做：** 把 `records.jsonl[.gz]` / 完整 Input 发到聊天或公开仓库；为「对手花费对不上」反复重打。

---

## 打完后：把记录带回来

1. 拷走 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\` 里新增的对局文件夹（可连同 `salt.txt`；不要覆盖分析机已有盐文件）。
2. **团子对照：** 拷走当日 `对战记录\yyyy年MM月dd日.txt`（可多日一并拷）。放到仓库侧建议路径：
   - `data/BgHelperDiag/<game_id>/`
   - `data/tuanzi/<yyyy年MM月dd日>.txt`
3. 有 Python 的机器上验收示例：

```text
python spikes/hdt-diag-logger/tools/check_capture.py data/BgHelperDiag/<game_id> --hs-logs none
python spikes/hdt-diag-logger/tools/eval_tuanzi_crosscheck.py data/BgHelperDiag/<game_id> data/tuanzi/<当日>.txt
```

对照时看：`bb_board_ok` / `sim_ok` 应为回合全过；`result_sign_vs_median` 偶发失败（如平局 vs 高胜率预测）**单独不算解析错误**。

无 Python 时，至少用记事本看 `meta.json`：`isBattlegroundsMatch=true`、`errors=0`、`probeInitError` 空、`recordCounts` 含 `entities` 与 `hdt_bb`。

---

## 版本变了怎么办

HDT / Bob's Buddy 会更新。`meta.json` 会写下实际版本；**继续用、继续记**。重放与分析按每局 `meta.bobsBuddy.version` 选 DLL，不要假定模拟次数永远是 9996 或 19998。

只有这些情况需要停下来联系（有开发环境后再处理）：

- 插件列表里加载失败，或 HDT 日志里没有 `loaded 0.2.0`
- 每局 `meta.json` 的 `errors` 不是 0，或 `probeInitError` 有字，且你不确定是否还该继续打
- （团子）对战记录与 diag 阵容/五率大面积对不上（不是个别 RNG 战果偏差）

---

## 隐私

记录已做 BattleTag / 玩家名替换，但仍是个人对局数据，只放在本机或你自己的 U 盘 / 网盘。仓库里不放 `records.jsonl[.gz]`、完整 Input JSON、BattleTag。对战记录文本一般不含 BattleTag，可进 `data/tuanzi/` 供对照（若日后含隐私字段再改规则）。
