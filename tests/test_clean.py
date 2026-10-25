"""Tests for the csmar-clean pipeline: the seven spec assertions (section 6.2)."""

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

# allow import both via `unittest discover -s tests` and from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_demo_data import make_demo_data  # noqa: E402

from csmar_clean.clean import run_clean  # noqa: E402
from csmar_clean.errors import CleanError  # noqa: E402
from csmar_clean.log import write_clean_log  # noqa: E402
from csmar_clean.rules import CleanRules, load_rules  # noqa: E402


class TestCleanPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.demo_path = make_demo_data(Path(cls.tmp.name) / "demo_data.dta")
        cls.df = pd.read_stata(cls.demo_path, convert_categoricals=False)
        cls.rules = load_rules(None)
        cls.cleaned, cls.steps = run_clean(cls.df, cls.rules)

    @staticmethod
    def _winsorize_step(steps):
        return next(s for s in steps if s.rule == "winsorize")

    def test_01_default_rules(self):
        rules = load_rules(None)
        self.assertIsInstance(rules, CleanRules)
        self.assertEqual(rules.id_col, "Stkcd")
        self.assertEqual(rules.financial_prefix, "J")

    def test_02_default_clean_and_log_sections(self):
        self.assertTrue(self.steps)
        self.assertLess(len(self.cleaned), len(self.df))
        log_path = Path(self.tmp.name) / "demo_cleaning_log.md"
        write_clean_log(str(log_path), str(self.demo_path), self.rules, self.steps, len(self.df), len(self.cleaned))
        text = log_path.read_text(encoding="utf-8")
        for section in ("剔除金融业", "剔除 ST", "剔除 IPO 当年", "缩尾处理"):
            self.assertIn(section, text)

    def test_03_financial_rows_removed(self):
        ind = self.cleaned["Indcd"].astype(str).str.upper()
        self.assertFalse(ind.str.startswith("J").any())

    def test_04_st_rows_removed(self):
        if "ST" in self.cleaned.columns:
            st = pd.to_numeric(self.cleaned["ST"], errors="coerce")
            self.assertTrue((st == 0).all())

    def test_05_roa_winsorized(self):
        # linear interpolation puts the 99% quantile near the single 999.0
        # outlier (~0.78 * 999 above the second-largest value), so the exact
        # bound is data-dependent; what must hold is high < 999 and that the
        # outlier is actually clipped.
        roa = self._winsorize_step(self.steps).winsorize_info["roa"]
        self.assertLess(roa["high"], 999.0)
        self.assertGreaterEqual(roa["n_clipped_high"], 1)

    def test_06_custom_limits_lower_roa_high(self):
        custom_yaml = Path(__file__).resolve().parents[1] / "examples" / "demo" / "custom_rules.yaml"
        cleaned, steps = run_clean(self.df, load_rules(str(custom_yaml)))
        self.assertLess(len(cleaned), len(self.df))
        high_default = self._winsorize_step(self.steps).winsorize_info["roa"]["high"]
        high_custom = self._winsorize_step(steps).winsorize_info["roa"]["high"]
        self.assertLess(high_custom, high_default)

    def test_07_missing_id_col_raises(self):
        yaml_path = Path(self.tmp.name) / "bad_id.yaml"
        yaml_path.write_text("id_col: not_a_column\n", encoding="utf-8")
        with self.assertRaises(CleanError):
            run_clean(self.df, load_rules(str(yaml_path)))


if __name__ == "__main__":
    unittest.main()
