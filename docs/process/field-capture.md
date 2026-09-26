# 新设备继续采集（无开发环境）

> 在另一台 Windows 电脑上打酒馆战棋、把诊断记录带回来。不需要安装 Git、.NET SDK、Python 或本仓库。
>
> 插件版本：HdtDiagLogger **0.1.0**（2026-09-25 编译，已在官方 HDT 1.58.3 / Bob's Buddy 1.78.1 上跑过 3 局 / 27 场）。

## 结论：插件够不够用

**对「继续打、继续记」够用，不必改插件、不必重编译。**

它已经稳定做到：

- 官方 HDT 能加载；不卡顿；BattleTag 落盘前匿名化。
- 每场战斗记下开战实体快照、HDT 交给模拟器的 Input、模拟 Output、战后快照、整局 Power 行。
- 本批 27/27 场齐全、0 错误。已知数字缺口（对手花费恒为 0、`2717` 不在 TagTransfer 上）是游戏 / HDT 不下发，插件再改也补不出来。

它**不是**正式采集器。下面这些等有开发环境再做，**现在不要为它们停手**：

- 实体快照仍拍在标签 `3533`，HDT 真正做模拟是约 80 行之后的 `2022`（本批数字仍一致）。
- 新对局开头会倒出上一局残留 Input（分析时丢掉即可）。
- 双人 / 畸变 / 战斗中补录样本还很少——这靠多打，不靠改插件。

---

## 出发前：从本机拷走这两样

关 HDT 之后，拷到 U 盘 / 网盘（**只要插件 DLL，不要拷 HDT 或 Bob's Buddy 的任何文件**）：

| 拷什么 | 本机位置 |
| --- | --- |
| `HdtDiagLogger.dll`（约 43 KB，2026-09-25） | `%APPDATA%\HearthstoneDeckTracker\Plugins\HdtDiagLogger.dll` |
| 本说明（可选） | 仓库 `docs/process/field-capture.md` |

可选：同一目录下的 `salt.txt`。带上则两台机器上同一个人会映射成同一个 `player_xxxxxxxx`；不带则新机器自己生成一份盐，分析仍然可用，只是跨机器对不上同一个人。

---

## 新电脑：装官方 HDT + 插件

1. **只装官方 Hearthstone Deck Tracker**（[hsdecktracker.net](https://hsdecktracker.net/)）。不要装「团子版」或其他修改版。装好后先启动一次，让它更新到最新，再关掉。
2. 确认炉石客户端的日志开着：炉石启动器 → 选项 → 崩溃与日志（或游戏内选项）里打开 **Power** 日志。HDT 第一次连上游戏时通常会提示，按提示打开即可。
3. 把 `HdtDiagLogger.dll` 放到：

   `%APPDATA%\HearthstoneDeckTracker\Plugins\`

   也就是 `C:\Users\<你的用户名>\AppData\Roaming\HearthstoneDeckTracker\Plugins\`。没有 `Plugins` 文件夹就新建一个。
4. 若 DLL 是从网盘下来的：右键 → 属性 → 若有「解除锁定」就勾上 → 确定。
5. 启动 HDT → **选项 → 追踪器 → 插件** → 启用 **BG Helper Diagnostic Logger**。
6. 看 HDT 日志（选项里可打开日志目录，或 `%APPDATA%\HearthstoneDeckTracker\Logs\hdt_log.txt`）应有类似一行：

   `[BgHelperDiag] loaded 0.1.0; HDT=…, BobsBuddy=…`

   - 有这行：插件在干活。
   - 若还有 `BobsBuddyInvoker probe unavailable`：仍请继续打。实体快照和 Power 行还在，只是对不上 HDT 当场模拟输入；把该局文件夹带回来即可。
   - 插件列表里根本没有这项：DLL 路径不对，或 HDT 没关干净就覆盖了文件。关 HDT 后重放 DLL，再开。

点插件旁的 **Open records folder** 应打开 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\`。

---

## 怎么打

正常打酒馆战棋即可。**先启用插件，再排队**；中途才打开插件的那一局可能不完整。

每打完一局、回到菜单后，该目录下应多一个文件夹，形如 `20260926_153012_a1b2c3\`，里面至少有：

| 文件 | 说明 |
| --- | --- |
| `meta.json` | 用记事本打开：`errors` 应为 `0`；`probeInitError` 应为 `null` 或空 |
| `records.jsonl` | 大约 10–20 MB / 局 |
| `power.log.gz` | 对局正常结束后才会出现。若中途杀了 HDT，会留下未压缩的 `power.log`，也要保留 |

**优先补样本（遇到就打，不必刻意重开）：** 带任务、对手有奥秘、Malorne、场上有畸变、战斗中有「装填 / 手牌变化」一类效果。双人可以打，插件会记，但不保证覆盖。构造模式不用管，插件不会为它们建目录。

**不要做：** 用修改版 HDT；把 `records.jsonl` / 完整 Input 发到聊天或仓库；为「对手花费对不上」反复重打。

---

## 打完后：把记录带回来

拷走整个目录：

`%APPDATA%\HearthstoneDeckTracker\BgHelperDiag\`

里面应有：`salt.txt` + 若干 `日期_短id\` 对局文件夹。不要只拷其中一个文件。

回到有仓库的那台机器后，把这些对局文件夹放进本机同一个 `BgHelperDiag\`（不要覆盖本机已有的 `salt.txt`，两台机器的盐可以并存于各自带来的目录旁，或把新机器的 `salt.txt` 改名为 `salt-other-pc.txt` 放在旁边）。然后告诉 agent 去验收。

新电脑上没有 Python 也没关系。用记事本看最新一局的 `meta.json` 即可自检：

- `isBattlegroundsMatch` 为 `true`
- `errors` 为 `0`
- `probeInitError` 为空
- `recordCounts` 里能看到 `entities`、`hdt_bb`

---

## 版本变了怎么办

官方 HDT 会自动更新。新电脑上的版本可以比 1.58.3 新，**继续用、继续记**，`meta.json` 会写下实际的 HDT / Bob's Buddy 版本。

只有这两种情况需要停下来联系（有开发环境后再处理）：

- 插件列表里加载失败，或 HDT 日志里没有 `loaded 0.1.0`
- 每局 `meta.json` 的 `errors` 不是 0，或 `probeInitError` 有字，且你不确定是否还该继续打

---

## 隐私

记录已做 BattleTag / 玩家名替换，但仍是个人对局数据，只放在本机或你自己的 U 盘 / 网盘。仓库里不放 `records.jsonl`、完整 Input JSON、BattleTag。
