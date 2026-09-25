# Spike：Bob's Buddy 公开 API 与独立调用（Q-001）

**目的：** 确认 `BobsBuddy.dll` 的 `Input`、`Player`、`Minion`、`SimulationRunner` 等类型是否公开，插件能否在 HDT 之外自己构造输入并调用模拟。

**结论：** 能。核心类型全部公开、可构造；在独立的 net472 x64 进程里调用 `SimulateMultiThreaded`，结果符合预期。详见 [`docs/facts/bobsbuddy-public-api.md`](../../docs/facts/bobsbuddy-public-api.md)。

## 内容

| 目录 | 说明 |
| --- | --- |
| `ApiDump/` | .NET 8 控制台程序，用 `MetadataLoadContext` 导出程序集的公开类型和成员签名，不执行目标代码，不反编译方法体 |
| `MinimalSim/` | net472 x64 控制台程序，构造三个白板场面调用 Bob's Buddy，检查胜 / 平 / 负是否符合预期 |
| `out/` | 导出的签名文本（从闭源 DLL 派生，已被 `.gitignore` 排除，不入库） |

## 复现

```powershell
$dn = "C:\Program Files\dotnet\dotnet.exe"
cd spikes\bobsbuddy-api

# 导出公开 API（第 3 个参数是 HearthDb.dll 所在目录）
& $dn build ApiDump -c Release
.\ApiDump\bin\Release\net8.0\ApiDump.exe "C:\Program Files\HDT\BobsBuddy.dll" out\BobsBuddy.txt "C:\Program Files\HDT"

# 最小模拟（默认引用 C:\Program Files\HDT；-p:BobsBuddyDir=... 可换成别的 BobsBuddy.dll）
& $dn build MinimalSim -c Release -o MinimalSim\bin\run
.\MinimalSim\bin\run\MinimalSim.exe
```

预期输出最后一行是 `ALL CHECKS PASSED`，退出码为 0。

官方最新的 `BobsBuddy.zip` 可以从 `https://libs.hearthsim.net/hdt/BobsBuddy.zip` 下载，解压到临时目录后用 `-p:BobsBuddyDir=<目录>` 编译。
