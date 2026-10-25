"""Write the Markdown cleaning log (Chinese, paper-ready)."""

from datetime import datetime, timezone

from csmar_clean.clean import CleanStep
from csmar_clean.rules import CleanRules

_RULE_LABELS = {
    "drop_financial": "剔除金融业",
    "drop_st": "剔除 ST",
    "drop_ipo_year": "剔除 IPO 当年",
}


def _pct(q: float) -> str:
    """Format a quantile like 0.01 / 0.025 as '1%' / '2.5%'."""
    return f"{q * 100:g}%"


def write_clean_log(
    path: str,
    source_path: str,
    rules: CleanRules,
    steps: list[CleanStep],
    initial_rows: int,
    final_rows: int,
) -> None:
    """Write the full cleaning trace of one run to *path* as Markdown."""
    lines: list[str] = []
    lines.append("# CSMAR 数据清洗日志")
    lines.append("")
    lines.append(f"- 源文件：`{source_path}`")
    lines.append(f"- 生成时间：{datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append(f"- 初始观测数：{initial_rows}")
    lines.append(f"- 最终观测数：{final_rows}")
    removed_pct = (initial_rows - final_rows) / initial_rows * 100 if initial_rows else 0.0
    lines.append(f"- 累计剔除比例：{removed_pct:.2f}%")
    lines.append("")

    lines.append("## 样本筛选步骤")
    lines.append("")
    lines.append("| 步骤 | 规则 | 剔除前行数 | 剔除后行数 | 剔除行数 | 剔除比例 | 说明 |")
    lines.append("|---|---|---|---|---|---|---|")
    n = 0
    for step in steps:
        if step.rule not in _RULE_LABELS:
            continue
        n += 1
        pct = step.rows_removed / step.rows_before * 100 if step.rows_before else 0.0
        lines.append(
            f"| {n} | {_RULE_LABELS[step.rule]} | {step.rows_before} | {step.rows_after} "
            f"| {step.rows_removed} | {pct:.2f}% | {step.detail} |"
        )
    lines.append("")

    lines.append("## 缩尾处理")
    lines.append("")
    lo, hi = rules.winsorize_limits
    winsor_step = next((s for s in steps if s.rule == "winsorize"), None)
    info: dict = (winsor_step.winsorize_info or {}) if winsor_step else {}
    lines.append(f"- 缩尾分位点：{_pct(lo)} / {_pct(hi)}")
    lines.append(f"- 处理变量数：{len(info)}")
    lines.append("")
    lines.append(f"| 变量 | 下界（{_pct(lo)}） | 上界（{_pct(hi)}） | 下侧截断数 | 上侧截断数 |")
    lines.append("|---|---|---|---|---|")
    for col, d in info.items():
        lines.append(
            f"| {col} | {d['low']:.6g} | {d['high']:.6g} | {d['n_clipped_low']} | {d['n_clipped_high']} |"
        )
    lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
