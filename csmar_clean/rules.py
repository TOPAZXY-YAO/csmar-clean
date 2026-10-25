"""Load and validate cleaning rules from YAML files."""

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from csmar_clean.errors import RuleError

DEFAULT_RULES_PATH = Path(__file__).parent / "default_rules.yaml"


@dataclass
class CleanRules:
    id_col: str = "Stkcd"
    year_col: str = "year"
    st_col: str | None = "ST"
    name_col: str | None = "Stknm"
    industry_col: str | None = "Indcd"
    list_date_col: str | None = "Listd"
    drop_financial: bool = True
    financial_prefix: str = "J"
    drop_st: bool = True
    drop_ipo_year: bool = True
    winsorize_cols: list[str] = field(default_factory=list)
    winsorize_limits: tuple[float, float] = (0.01, 0.99)
    winsorize_exclude: list[str] = field(default_factory=list)


def load_rules(path: str | None) -> CleanRules:
    """Load the built-in default rules; if *path* is given, overlay the user
    YAML on top of them.

    User keys overwrite default keys one-for-one, and keys absent from the
    user YAML keep their default values. A user-provided ``winsorize_cols``
    list therefore replaces the default list instead of being appended to.
    """
    merged = _read_yaml(DEFAULT_RULES_PATH)
    if path is not None:
        merged.update(_read_yaml(Path(path)))

    known = {f.name for f in fields(CleanRules)}
    kwargs = {k: v for k, v in merged.items() if k in known}
    if isinstance(kwargs.get("winsorize_limits"), list):
        kwargs["winsorize_limits"] = tuple(kwargs["winsorize_limits"])

    rules = CleanRules(**kwargs)
    _validate(rules)
    return rules


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file into a dict, raising RuleError on any I/O or parse issue."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except OSError as exc:
        raise RuleError(f"无法读取规则文件：{path}（{exc}）") from exc
    except yaml.YAMLError as exc:
        raise RuleError(f"规则文件不是合法 YAML：{path}（{exc}）") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise RuleError(f"规则文件顶层必须是键值映射：{path}")
    return data


def _validate(rules: CleanRules) -> None:
    """Enforce the invariants the cleaning pipeline relies on."""
    for name in ("id_col", "year_col"):
        value = getattr(rules, name)
        if not isinstance(value, str) or not value:
            raise RuleError(f"规则字段 {name} 必须是非空字符串")

    prefix = rules.financial_prefix
    if not isinstance(prefix, str) or not prefix:
        raise RuleError("规则字段 financial_prefix 不能为空")

    limits = rules.winsorize_limits
    try:
        lo, hi = float(limits[0]), float(limits[1])
    except (TypeError, ValueError, IndexError, KeyError) as exc:
        raise RuleError(
            f"规则字段 winsorize_limits 必须是两个数值（如 [0.01, 0.99]），当前为 {limits!r}"
        ) from exc
    if not (0.0 <= lo < hi <= 1.0):
        raise RuleError(
            f"规则字段 winsorize_limits 必须满足 0 <= 下限 < 上限 <= 1，当前为 [{lo}, {hi}]"
        )
