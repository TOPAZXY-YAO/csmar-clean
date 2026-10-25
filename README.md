# csmar-clean

一条命令 + 默认 YAML，把 CSMAR 原始导出表清洗成可跑回归的分析样本，并生成可粘贴进论文的清洗日志。

## 快速开始

```bash
pip install -e .
python3 tests/make_demo_data.py            # 生成示例数据 examples/demo/demo_data.dta
csmar-clean examples/demo/demo_data.dta    # 清洗
```

（Windows 下把 `python3` 换成 `python`。）

跑完打开 `examples/demo/demo_data_clean_cleaning_log.md`——一份可直接粘进论文"样本筛选"小节的中文 Markdown 日志：

```markdown
| 步骤 | 规则 | 剔除前行数 | 剔除后行数 | 剔除行数 | 剔除比例 | 说明 |
|---|---|---|---|---|---|---|
| 1 | 剔除金融业 | 40 | 32 | 8 | 20.00% | Indcd 以 J 开头的金融业观测 |
| 2 | 剔除 ST | 32 | 24 | 8 | 25.00% | ST 字段标记为非 0 的观测 |
| 3 | 剔除 IPO 当年 | 24 | 23 | 1 | 4.17% | 观测年份等于上市年份（Listd）的 IPO 当年观测 |
```

先看看规则将怎么执行、不写任何文件：

```bash
csmar-clean examples/demo/demo_data.dta --dry-run
```

## 默认执行的 4 条规则（顺序固定）

顺序与中文实证论文的标准样本筛选流程一致：

| 顺序 | 规则 | 默认判定方式 |
|---|---|---|
| 1 | 剔除金融业 | `Indcd` 以 `J` 开头（证监会门类 J 金融业） |
| 2 | 剔除 ST | `ST` 字段非 0 视为 ST（兼容 `1`、`"1"`、`"ST"`）；若数据没有 `ST` 列，退化为 `Stknm` 含 "ST" 的模糊匹配 |
| 3 | 剔除 IPO 当年 | 观测年份 == 上市年份（`Listd`，缺列时自动尝试 `ListDt`） |
| 4 | 缩尾 | 数值列在 1% / 99% 分位缩尾（自动排除 `Stkcd`、`year` 等非分析列） |

每一步执行前后的行数、剔除比例、缩尾分位点与两侧截断数，全部写入清洗日志。某条规则因缺列或被关闭而未执行时，日志对应行会标注"未执行：<原因>"。

## 用 YAML 覆盖默认规则

工具不猜列名：所有列名与开关都来自 YAML。把 `--rules your.yaml` 交给 CLI，其中的字段覆盖默认值，没写的沿用默认：

```yaml
# my_rules.yaml：换成你数据里的列名
id_col: Stkcd
year_col: year
st_col: ST              # 设为 null 则改用证券简称模糊匹配
name_col: Stknm
industry_col: Indcd
list_date_col: Listd
drop_financial: true
financial_prefix: J
drop_st: true
drop_ipo_year: true
winsorize_limits: [0.01, 0.99]
winsorize_exclude: [Stkcd, year]
winsorize_cols: []      # 留空 = 自动选数值列；写了列表就完全按列表执行（整体替换）
```

```bash
csmar-clean raw.dta --rules my_rules.yaml --output clean.dta --log log.md
```

完整示例见 `examples/demo/custom_rules.yaml`（5%/95% 分位、只缩 `roa`/`lev`）：

```bash
csmar-clean examples/demo/demo_data.dta --rules examples/demo/custom_rules.yaml
```

## YAML 字段说明

| 字段 | 默认值 | 说明 |
|---|---|---|
| `id_col` | `Stkcd` | 股票代码列（**必需**，数据中必须有此列） |
| `year_col` | `year` | 年份列（**必需**，数据中必须有此列） |
| `st_col` | `ST` | ST 标记列，非 0 / 非 "0" 视为 ST；设为 `null` 走 `name_col` 模糊匹配 |
| `name_col` | `Stknm` | 证券简称列，`st_col` 为 `null` 或不在数据中时生效 |
| `industry_col` | `Indcd` | 行业代码列，以 `financial_prefix` 开头的观测被剔除 |
| `list_date_col` | `Listd` | 上市日期列；不在数据中时自动尝试 `ListDt` |
| `drop_financial` | `true` | 是否剔除金融业 |
| `financial_prefix` | `J` | 金融业行业代码前缀（非空） |
| `drop_st` | `true` | 是否剔除 ST |
| `drop_ipo_year` | `true` | 是否剔除 IPO 当年观测 |
| `winsorize_cols` | `[]` | 缩尾变量；留空自动选所有数值列，非空则**整体替换**自动选择 |
| `winsorize_limits` | `[0.01, 0.99]` | 缩尾下/上分位点（0–1 之间递增） |
| `winsorize_exclude` | `[Stkcd, year]` | 自动选列时排除的列；`id_col`/`year_col` 始终被排除 |

## 为什么不用手写脚本

每个用 CSMAR 数据的人都写过那段"剔金融、剔 ST、剔 IPO、缩尾"的 Stata/Python 脚本。csmar-clean 把它变成一条命令，差别在四点：

- **留痕**：手写脚本的剔除行数靠手工 `count`（或干脆不记）；这里每一步的前后行数、比例、缩尾阈值与截断数自动进日志，直接可粘进论文。
- **可复现**：一条命令 + 一份 YAML 重跑即得同一份样本与日志，阈值不再散落在脚本各处。
- **字段名可覆盖**：换一版导出表不用改代码，改 YAML 即可。
- **默认即惯例**：规则与顺序按中文实证论文的标准样本筛选流程预置，开箱即用。

## 边界声明（v0.1 刻意不做）

- **不猜列名**：所有列名显式来自 YAML；
- **不碰回归**：只做清洗与筛选，不做合并、不做变量构造、不跑模型；
- **不做行业代码映射**（CSRC 2012/2001 版互转）、**不做公司 ID 变更追踪**；
- 只支持 `.dta` / `.csv` 输入输出。

## 路线图

- 公司 ID 变更追踪
- CSRC 行业代码映射（2012 vs 2001）
- 面板平衡度检查
- 与 panelstitch / tracecheck 的衔接：上游先拼接面板、下游可溯源每行来龙去脉

## License

MIT
