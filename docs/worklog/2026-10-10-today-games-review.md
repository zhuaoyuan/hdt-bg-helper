# 2026-10-10 今日对局入库并生成 P3-T5 复盘

## 目标

把今天已结束的诊断对局写入标准层与 BB 1.88.6 战力桶，并为这些局生成赛后静态 HTML。

## 做了什么

1. 扫描 `%APPDATA%\HearthstoneDeckTracker\BgHelperDiag`：今天已结束 **7** 局，全部 HDT 1.58.9 / BB **1.88.6.0** / `ready`。写复盘时另有未结束局 `20261010_191105_addbaf`，未入库。
2. 标准层侧写再合并进 `data/standard/turns.jsonl`（备份 `turns.jsonl.bak_before_20261010`）：
   - 今天 7 局 83 行（`data/standard_20261010` 为上午 6 局；`data/standard_c1e14c` 为傍晚结束的 `c1e14c`）。战果来源 `hdt` / `lb`；无团子配对，`placement=null`。
   - 同版本已结束的 10-07～10-09 共 10 局 114 行（`data/standard_188_prior`）。只把今天 6 局放进参照池时，留一法其他局数 < \(G_\text{min}=6\)，分位会全部是 `insufficient`，所以一并写入。其中 10-07 四局与团子文本配对，严格对照 46/46。
   - 全库约 **73 局 / 853 行**。团子目录已从 `C:\Program Files\HDT\对战记录` 同步；磁盘上只有 10-04、10-05、10-07，没有 10-08～10-10。
3. 战力：`python -m tools.strength percentile --bb-version 1.88.6.0 --turns 1-17` → `data/strength/1.88.6.0/strength.jsonl`。含傍晚局之后：**200** 个己方场面，`missingAfter=0`，level L0 **190** / L1 **3** / insufficient **7**；`nWide=165`。对手分位写入同目录 `strength_opp.jsonl`（今天 81 行；`7953ca` T14、`3b38f9` T13 无对手场面，按幽灵对手未入池）。
4. 阵容：`board_render --side both`（在线肖像）。缺肖像：`3b38f9` 6 张、`0f73cd` 1 张（`TB_BaconUps_*_G`、`BG34_634_Gt_G`、`BG36_360_Gt6_G`），其余 0。
5. 复盘：`python -m tools.review_view --strength data\strength\1.88.6.0\strength.jsonl --boards data\boards --no-opp-strength`（对手分位用已写好的缓存）。

## 发现

- `--game` 导入会整文件覆盖 `turns.jsonl`，增量必须侧写再合并。
- 晚回合局数 < 7 时引擎对整桶打开 turn±1，会补跑跨回合对战（本批先约 1.9 万对，纳入 `c1e14c` 后又补约 2140 对）。缓存命中后第二次分位约 3.5 分钟。
- 今天复盘页多数己方回合是 L0 + `wide`（区间宽度 >20）。`7953ca` T14–T15、`3b38f9` T14 为 `insufficient`。

## 留下的东西

复盘页：

| 局 | 英雄 | 回合 | 页 |
| --- | --- | --- | --- |
| `20261010_091350_7953ca` | 时光之末迦拉克隆 | 15 | `data/review/20261010_091350_7953ca/index.html` |
| `20261010_094407_e747b2` | 钟表先生克劳沃斯 | 11 | `data/review/20261010_094407_e747b2/index.html` |
| `20261010_100449_16e988` | 瓦尔登·晨拥 | 11 | `data/review/20261010_100449_16e988/index.html` |
| `20261010_102621_3b38f9` | 洞穴专家福尔摩斯 | 14 | `data/review/20261010_102621_3b38f9/index.html` |
| `20261010_105504_0f73cd` | 钟表先生克劳沃斯 | 12 | `data/review/20261010_105504_0f73cd/index.html` |
| `20261010_111841_9ca3ca` | 未来的假日诺兹多姆 | 10 | `data/review/20261010_111841_9ca3ca/index.html` |
| `20261010_185240_c1e14c` | 芬利·莫格顿爵士 | 10 | `data/review/20261010_185240_c1e14c/index.html` |

未做：`addbaf`（当时未结束）、1.88.6 同版本 roundtrip、全库 `quality_report` 重写、T5 验收 5 人核。今天各局没有名次（无团子日文件）。
