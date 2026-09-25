# HDT 与 Bob's Buddy 的许可和使用条款

> 这份文档回答：HDT 和 `BobsBuddy.dll` 以什么条款提供、官方对插件和 Bob's Buddy 二次使用有过什么表态（Q-003）。这里只列原文事实。所有者对风险的接受见 [ADR-0006](../decisions/0006-personal-plugin-use-of-hdt-bobsbuddy.md)。

```text
基线：HDT v1.58.3 / 509bb0b9；HearthSim/legal TERMS.md 最后提交 ba1c4dee（2022-10-20）
最后核实：2026-09-25
```

## 许可证文本

- HDT 仓库 `README.md` 第 61–63 行："Copyright © HearthSim. All Rights Reserved."。
- 仓库根目录没有 LICENSE 文件。GitHub API `repos/HearthSim/Hearthstone-Deck-Tracker` 返回的 `license` 为空，`/license` 端点返回 404。
- `licenses/` 目录只有第三方组件的许可证（如 `HearthDb.md` 为 MIT；`Hearthstone.md` 声明炉石图像版权归暴雪）。里面没有 Bob's Buddy 的许可证。
- `BobsBuddy.dll` 的程序集属性：`AssemblyCompany = HearthSim`，`AssemblyCopyright = "Copyright © HearthSim 2023"`（见 `bobsbuddy-public-api.md`）。`BobsBuddy.zip` 里只有两个 DLL，没有许可证文件。
- 本机 HDT 安装目录（`C:\Program Files\HDT`）两层以内没有 license / eula / notice 类文件。

**结论（已核实）：HDT 和 Bob's Buddy 都没有开源许可证，是保留全部权利的专有软件。**

## HearthSim 服务条款（`HearthSim/legal` 仓库 `TERMS.md`）

条款明确覆盖 Hearthstone Deck Tracker（第 14 行）。相关原文：

- 第 28 行：授予"limited, revocable, non-exclusive, non-transferable, non-sublicensable license to use and access the Service, solely for your personal, non-commercial use"。
- 第 30 行：不得"copy, adapt, modify, prepare derivative works based upon, distribute, license, sell, … or otherwise exploit the Service or any portion of the Service, except as expressly permitted in these Terms"。
- 第 70 行：不得"modify, copy, distribute, … or otherwise exploit the Service without our express prior written permission"。
- 条款里没有提到插件、反编译或逆向工程。

## 官方对插件的态度

- 官方 wiki "Creating Plugins"（2024-02-17 版）给出了插件开发步骤（引用 `Hearthstone Deck Tracker.exe`、实现 `IPlugin`），"Available Plugins" 页列出了社区插件（2026-07-06 仍在更新）。
- HSReplay 帮助中心 "How do I use plugins for Hearthstone Deck Tracker?"：HearthSim 不支持第三方插件，使用风险自负。
- HDT 会拒绝加载特定插件：`PluginManager.cs:179–187` 按名称拒绝 Reconnector 类插件，`208–223` 拒绝导入 `iphlpapi` / `lovepapi` 的程序集，注释是"Blizzard has kindly asked us to stop supporting reconnector plugins"。
- [issue #4509](https://github.com/HearthSim/Hearthstone-Deck-Tracker/issues/4509) 中维护者表示，Reconnector 插件被屏蔽是因为提供了不公平优势，而且 Blizzard 要求移除。讨论里还有人指出，使用旧版本是允许的，但修改或再分发（包括衍生作品）不允许。

## 官方对 Bob's Buddy 二次使用的表态

[issue #4063](https://github.com/HearthSim/Hearthstone-Deck-Tracker/issues/4063)（2020-05-05，HearthSim 成员 beheh 回复）：

> The Bob's Buddy simulator code is built outside of the deck tracker repository and is private at this time. … we can't condone or support such development [agents that semi-intelligently play Battlegrounds] in the HearthSim community because the resulting tooling is prone to being misused by bad actors …

- 表态针对的是"会自己玩酒馆战棋的 agent"。
- 没有找到官方对"插件调用 `BobsBuddy.dll` 做个人复盘分析"的明确许可或禁止。

## 所有者判断（2026-09-25）

以下不是法律意见，是所有者对上列事实的接受范围，已写入 [ADR-0006](../decisions/0006-personal-plugin-use-of-hdt-bobsbuddy.md)：

1. 本机、个人、非商业使用 HDT 自带 DLL，且不分发 `BobsBuddy.dll` 或 HDT 二进制文件，与 TERMS 第 28 行相容。
2. 插件引用并调用 `BobsBuddy.dll` 的公开 API，属于合理用途。
3. 实时显示战力分位属于合理用途，与 HDT 显示 Bob's Buddy 胜率同类，不按 issue #4509 的"不公平优势"处理。
4. 仓库可以公开，但不能包含 HDT / Bob's Buddy 的二进制文件或反编译代码。
