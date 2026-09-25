# Spike：HDT 空插件（Q-005）

**目的：** 确认不装 Visual Studio、只用 .NET SDK 能否编译出引用本机 HDT 的插件，以及需要哪些引用。

**结论：** 能。SDK 风格的 net472 x64 类库以 `Private=false` 引用安装目录中的 `HearthstoneDeckTracker.exe`、`BobsBuddy.dll`、`HearthDb.dll`，外加 WPF 的几个框架程序集，即可编译。产物只有插件自身的 DLL（约 5.6 KB）。详见 [`docs/facts/hdt-baseline.md`](../../docs/facts/hdt-baseline.md) 的"插件构建"一节。

**尚未验证：** 在 HDT 里实际加载。需要所有者配合：

1. 把 `bin\Release\net472\HdtPluginSkeleton.dll` 复制到 `%APPDATA%\HearthstoneDeckTracker\Plugins`；
2. 重启 HDT，在"选项 > 追踪器 > 插件"里启用 "BG Helper Skeleton"；
3. HDT 日志里应出现 `[BgHelperSkeleton] loaded; HDT=…, BobsBuddy=…`，开一局后还应出现 `[BgHelperSkeleton] game start`。

## 编译

```powershell
& "C:\Program Files\dotnet\dotnet.exe" build spikes\hdt-plugin-skeleton\HdtPluginSkeleton -c Release
```

HDT 不在默认位置时加 `-p:HdtDir=<HDT 安装目录>`。
