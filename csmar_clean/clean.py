"""Run the fixed-order cleaning pipeline on a DataFrame."""

from dataclasses import dataclass

import pandas as pd

from csmar_clean.errors import CleanError
from csmar_clean.rules import CleanRules

# Hard-coded fallback column tried when rules.list_date_col is absent,
# matching the common CSMAR export variant.
_FALLBACK_LIST_DATE_COL = "ListDt"


@dataclass
class CleanStep:
    rule: str
    rows_before: int
    rows_after: int
    rows_removed: int
    detail: str
    winsorize_info: dict | None = None


def run_clean(df: pd.DataFrame, rules: CleanRules) -> tuple[pd.DataFrame, list[CleanStep]]:
    """Apply the four rules in the standard paper order:
    drop_financial -> drop_st -> drop_ipo_year -> winsorize.
    """
    for key, col_name in (("id_col", rules.id_col), ("year_col", rules.year_col)):
        if col_name not in df.columns:
            raise CleanError(f"输入数据缺少必需列 {col_name!r}（可在规则 YAML 中用 {key} 覆盖列名）")

    out = df.copy()
    steps: list[CleanStep] = []
    out, step = _drop_financial(out, rules)
    steps.append(step)
    out, step = _drop_st(out, rules)
    steps.append(step)
    out, step = _drop_ipo_year(out, rules)
    steps.append(step)
    out, step = _winsorize(out, rules)
    steps.append(step)
    return out, steps


def _make_step(
    rule: str,
    before: int,
    after: int,
    detail: str,
    winsorize_info: dict | None = None,
) -> CleanStep:
    return CleanStep(
        rule=rule,
        rows_before=before,
        rows_after=after,
        rows_removed=before - after,
        detail=detail,
        winsorize_info=winsorize_info,
    )


def _drop_financial(df: pd.DataFrame, rules: CleanRules) -> tuple[pd.DataFrame, CleanStep]:
    """Keep rows whose industry code does not start with the financial prefix."""
    before = len(df)
    if not rules.drop_financial:
        return df, _make_step("drop_financial", before, before, "未执行：drop_financial 已设为 false")
    col = rules.industry_col
    if col is None or col not in df.columns:
        return df, _make_step("drop_financial", before, before, "未执行：未找到行业列，跳过金融业剔除")
    is_financial = df[col].astype(str).str.upper().str.startswith(rules.financial_prefix.upper())
    out = df[~is_financial]
    return out, _make_step("drop_financial", before, len(out), f"{col} 以 {rules.financial_prefix} 开头的金融业观测")


def _drop_st(df: pd.DataFrame, rules: CleanRules) -> tuple[pd.DataFrame, CleanStep]:
    """Drop ST rows via the ST flag column, or via the security name as fallback."""
    before = len(df)
    if not rules.drop_st:
        return df, _make_step("drop_st", before, before, "未执行：drop_st 已设为 false")
    if rules.st_col is not None and rules.st_col in df.columns:
        s = df[rules.st_col]
        text = s.astype(str).str.strip().str.lower()
        # non-null and non-placeholder values only
        has_value = s.notna() & ~text.isin(["", "nan", "none", "<na>", "false"])
        numeric = pd.to_numeric(text, errors="coerce")
        # 0 / "0" means not ST; 1, "1", "ST", True-like strings mean ST
        is_st = has_value & ~(numeric == 0)
        out = df[~is_st]
        return out, _make_step("drop_st", before, len(out), f"{rules.st_col} 字段标记为非 0 的观测")
    if rules.name_col is not None and rules.name_col in df.columns:
        is_st = df[rules.name_col].astype(str).str.contains("ST", na=False, case=False)
        out = df[~is_st]
        return out, _make_step("drop_st", before, len(out), f"{rules.name_col} 证券简称含 ST 的观测")
    return df, _make_step("drop_st", before, before, "未执行：未找到 ST 标记列和证券简称列，跳过 ST 剔除")


def _drop_ipo_year(df: pd.DataFrame, rules: CleanRules) -> tuple[pd.DataFrame, CleanStep]:
    """Drop rows whose observation year equals the listing year."""
    before = len(df)
    if not rules.drop_ipo_year:
        return df, _make_step("drop_ipo_year", before, before, "未执行：drop_ipo_year 已设为 false")
    col = rules.list_date_col
    if col is not None and col in df.columns:
        date_col = col
    elif _FALLBACK_LIST_DATE_COL in df.columns and col != _FALLBACK_LIST_DATE_COL:
        date_col = _FALLBACK_LIST_DATE_COL
    else:
        return df, _make_step("drop_ipo_year", before, before, "未执行：未找到上市日期列，跳过 IPO 当年剔除")

    s = df[date_col]
    if pd.api.types.is_datetime64_any_dtype(s):
        list_year = s.dt.year
    else:
        list_year = pd.to_numeric(s.astype(str).str.slice(0, 4), errors="coerce")
    obs_year = pd.to_numeric(df[rules.year_col], errors="coerce")
    is_ipo_year = obs_year == list_year
    out = df[~is_ipo_year]
    return out, _make_step("drop_ipo_year", before, len(out), f"观测年份等于上市年份（{date_col}）的 IPO 当年观测")


def _winsorize(df: pd.DataFrame, rules: CleanRules) -> tuple[pd.DataFrame, CleanStep]:
    """Clip every candidate numeric column to its [lo, hi] quantiles."""
    before = len(df)
    lo, hi = rules.winsorize_limits
    if rules.winsorize_cols:
        candidates = list(rules.winsorize_cols)
    else:
        exclude = set(rules.winsorize_exclude) | {rules.id_col, rules.year_col}
        candidates = [c for c in df.select_dtypes(include="number").columns if c not in exclude]

    info: dict = {}
    for col in candidates:
        if col not in df.columns:
            raise CleanError(f"winsorize：指定的缩尾列 {col!r} 不在数据中（步骤开始前行数 {before}）")
        series = df[col]
        if not pd.api.types.is_numeric_dtype(series):
            raise CleanError(f"winsorize：缩尾列 {col!r} 不是数值列（步骤开始前行数 {before}）")
        low = series.quantile(lo)
        high = series.quantile(hi)
        n_clipped_low = int((series < low).sum())
        n_clipped_high = int((series > high).sum())
        df[col] = series.clip(lower=low, upper=high)
        info[col] = {
            "low": float(low),
            "high": float(high),
            "n_clipped_low": n_clipped_low,
            "n_clipped_high": n_clipped_high,
        }
    detail = f"对 {len(candidates)} 个数值列在 {lo:g}/{hi:g} 分位缩尾（不改变行数）"
    return df, _make_step("winsorize", before, before, detail, winsorize_info=info)
