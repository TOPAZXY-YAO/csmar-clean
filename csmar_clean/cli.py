"""Command-line entry point for csmar-clean."""

import argparse
import sys
from pathlib import Path

import pandas as pd

from csmar_clean.clean import run_clean
from csmar_clean.errors import CleanError, RuleError
from csmar_clean.log import write_clean_log
from csmar_clean.rules import load_rules


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="csmar-clean",
        description="把 CSMAR 原始导出表清洗成可跑回归的分析样本，并生成可粘贴进论文的清洗日志。",
    )
    parser.add_argument("input", help="输入文件（.dta 或 .csv）")
    parser.add_argument("--rules", default=None, help="用户规则 YAML 路径（覆盖默认规则的同名字段）")
    parser.add_argument("--output", default=None, help="输出文件（默认 <input_stem>_clean.<ext>，与输入同格式）")
    parser.add_argument("--log", default=None, help="清洗日志路径（默认 <output_stem>_cleaning_log.md）")
    parser.add_argument("--dry-run", action="store_true", help="只打印将执行的规则和初始行数，不写文件")
    args = parser.parse_args(argv)

    try:
        return _run(args)
    except (CleanError, RuleError) as exc:
        print(f"清洗失败：{exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # CLI boundary: report unexpected errors with exit code 2
        print(f"内部错误：{exc}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    in_path = Path(args.input)
    if not in_path.exists():
        raise CleanError(f"输入文件不存在：{in_path}")
    ext = in_path.suffix.lower()
    if ext == ".dta":
        df = pd.read_stata(in_path, convert_categoricals=False)
    elif ext == ".csv":
        df = pd.read_csv(in_path, encoding="utf-8-sig")
    else:
        raise CleanError(f"只支持 .dta 或 .csv，收到 {ext!r}")

    rules = load_rules(args.rules)

    if args.dry_run:
        _print_plan(in_path, rules, len(df))
        return 0

    out, steps = run_clean(df, rules)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = in_path.with_name(in_path.stem + "_clean" + in_path.suffix)
    if args.log:
        log_path = Path(args.log)
    else:
        log_path = out_path.with_name(out_path.stem + "_cleaning_log.md")

    if out_path.suffix.lower() == ".csv":
        out.to_csv(out_path, index=False, encoding="utf-8-sig")
    else:
        try:
            out.to_stata(out_path, version=118, write_index=False)
        except Exception:
            # v118 is the spec default; older Stata versions may not read it
            out.to_stata(out_path, version=117, write_index=False)

    write_clean_log(str(log_path), str(in_path), rules, steps, len(df), len(out))
    print(f"clean ok: {out_path} | {len(df)} -> {len(out)} rows")
    return 0


def _print_plan(in_path: Path, rules, initial_rows: int) -> None:
    """Dry-run output: planned rules (in execution order) and the initial row count."""
    lo, hi = rules.winsorize_limits
    winsor_cols = rules.winsorize_cols or "自动（数值列减去 winsorize_exclude）"
    print(f"输入文件：{in_path}")
    print(f"初始行数：{initial_rows}")
    print("将按顺序执行以下规则：")
    print(f"  1. 剔除金融业 drop_financial={'开' if rules.drop_financial else '关'}"
          f"（industry_col={rules.industry_col!r}, prefix={rules.financial_prefix!r}）")
    print(f"  2. 剔除 ST drop_st={'开' if rules.drop_st else '关'}"
          f"（st_col={rules.st_col!r}, name_col={rules.name_col!r}）")
    print(f"  3. 剔除 IPO 当年 drop_ipo_year={'开' if rules.drop_ipo_year else '关'}"
          f"（list_date_col={rules.list_date_col!r}）")
    print(f"  4. 缩尾 winsorize：{lo:g}/{hi:g} 分位（变量：{winsor_cols}）")


if __name__ == "__main__":
    raise SystemExit(main())
