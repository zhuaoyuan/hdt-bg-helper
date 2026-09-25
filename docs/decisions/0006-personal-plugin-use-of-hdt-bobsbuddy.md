# ADR-0006：个人非商业插件可调用本机 HDT / Bob's Buddy 公开 API

- **状态：** accepted（所有者 2026-09-25 对话确认）
- **日期：** 2026-09-25
- **相关：** Q-003、ADR-0002、`facts/licensing.md`

## 背景

- HDT 和 `BobsBuddy.dll` 都是保留全部权利的专有软件。HearthSim 服务条款授予个人非商业使用许可，同时禁止修改、制作衍生作品和再分发（`facts/licensing.md`）。
- 条款没有专门写插件调用 DLL。官方 wiki 教第三方写插件并引用 HDT 程序集；HDT 在代码里只屏蔽了 Reconnector 一类被认定为不公平优势的插件。
- 官方明确不支持"会自己玩酒馆战棋的 agent"（issue #4063）。本项目的目标是提升所有者本人的决策与复盘，不是代打。
- Q-001 已确认：插件或独立进程可以调用 `BobsBuddy.dll` 的公开 API，不需要反编译方法体。

## 决定

1. 本项目只在本机、个人、非商业地使用所有者已安装的 HDT 自带 DLL。这与 TERMS 第 28 行的 "personal, non-commercial use" 相容。
2. 插件或独立进程引用并调用 `BobsBuddy.dll` 的公开 API，属于合理用途，不按 TERMS 第 30 行的 "exploit … any portion of the Service" 处理。
3. 实时对局中显示本回合战力分位，与 HDT 自己显示 Bob's Buddy 胜率属于同一类信息，不按 issue #4509 的"不公平优势"处理。
4. 仓库可以公开，但不得包含 HDT / Bob's Buddy 的二进制文件或反编译代码（`.gitignore` 已排除 `dll` / `exe`；从闭源 DLL 派生的 API 导出放在 `spikes/**/out/`，不入库）。

执行约束：

- 不把 `BobsBuddy.dll`、`HearthstoneDeckTracker.exe` 或其他 HDT 自带程序集随本项目分发。
- 不为调用模拟器去反编译方法体或把反编译结果写入仓库。公开签名反射（如 `spikes/bobsbuddy-api/ApiDump`）可以继续用。
- 不自动操作游戏、不写代打 agent。这是范围红线，也是与 issue #4063 官方表态的分界。

## 考虑过的方案

| 方案 | 为什么没选 / 为什么选 |
| --- | --- |
| 不用 Bob's Buddy，改开源或自研模拟器 | 避开专有软件，但机制覆盖和版本跟进差，且 Q-001 已证明调用可行 |
| 先书面征得 HearthSim 许可再动手 | 更稳妥，但条款对插件没有明确禁止，社区插件普遍引用 HDT，会拖延 P1/P2 |
| **按个人非商业、不入库、不分发的方式调用公开 API** | 选中：与官方插件机制和本项目目标一致，所有者接受剩余风险 |

## 后果

- 正面：ADR-0002 的许可阻塞解除；P2 可以按公开 API 调用模拟器。
- 代价：HearthSim 仍可能事后改变态度或屏蔽插件；仓库公开后若有人二次分发 DLL，不在本决定覆盖范围内。
- 需要跟进：分发插件安装包时仍然只带本项目自己的 DLL；采集记录模拟器版本（Q-011）。

## 推翻条件

- HearthSim 或暴雪明确禁止第三方调用 `BobsBuddy.dll`，或在 HDT 中屏蔽此类插件；
- 本项目转为商业用途，或需要随安装包分发 HDT / Bob's Buddy 二进制文件。
