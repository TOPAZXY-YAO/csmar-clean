"""Generate the demo dataset used by tests and the README quick start.

The demo panel deliberately plants observations that each cleaning rule
should catch: two financial firms (Indcd starts with "J"), two ST firms
(flagged both in the ST column and in their names), one firm whose listing
year equals one observed year, and extreme tail values in roa / lev.
"""

from pathlib import Path

import pandas as pd

YEARS = [2015, 2016, 2017, 2018]

# (Stkcd, Stknm, ST, Indcd, Listd)
COMPANIES = [
    ("000001", "华信银行", 0, "J66", "2004-05-10"),  # financial firm
    ("000002", "南海证券", 0, "J67", "2007-09-21"),  # financial firm
    ("000003", "*ST华信", 1, "C39", "2009-03-15"),  # ST via flag and via name
    ("000004", "ST坤源", 1, "C38", "2011-11-02"),  # ST via flag and via name
    ("000005", "恒达电子", 0, "C34", "2016-05-18"),  # listing year == 2016 (IPO year)
    ("000006", "平安机械", 0, "C27", "2003-02-28"),  # roa outlier planted below
    ("000007", "广济咨询", 0, "K70", "2005-08-09"),  # lev outlier planted below
    ("000008", "天成制造", 0, "C30", "2002-04-11"),
    ("000009", "绿源科研", 0, "K71", "2013-06-30"),
    ("000010", "宏图文教", 0, "C35", "2008-12-01"),
]

# (Stkcd, year, column, value): these rows survive the three drop rules,
# so the extreme values must be caught by the winsorize step instead.
OUTLIERS = [
    ("000006", 2017, "roa", 999.0),
    ("000007", 2015, "lev", -3.5),
]


def make_demo_data(output: str | Path | None = None) -> Path:
    """Write the demo Stata file (10 firms x 4 years = 40 rows) and return its path."""
    if output is None:
        output = Path(__file__).resolve().parents[1] / "examples" / "demo" / "demo_data.dta"
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, (stkcd, name, st, indcd, listd) in enumerate(COMPANIES):
        for j, year in enumerate(YEARS):
            rows.append(
                {
                    "Stkcd": stkcd,
                    "year": year,
                    "Stknm": name,
                    "ST": st,
                    "Indcd": indcd,
                    "Listd": listd,
                    "roa": 0.03 + 0.002 * i + 0.001 * j,
                    "lev": 0.35 + 0.01 * i + 0.005 * j,
                    "size": 21.0 + 0.1 * i + 0.05 * j,
                }
            )
    df = pd.DataFrame(rows)
    for stkcd, year, col, value in OUTLIERS:
        df.loc[(df["Stkcd"] == stkcd) & (df["year"] == year), col] = value

    df.to_stata(output, version=118, write_index=False)
    return output


if __name__ == "__main__":
    path = make_demo_data()
    print(f"wrote {path}")
