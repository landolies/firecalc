"""
Social Security tables — AWI, taxable max, COLA, FRA.

Sources (verify before each annual update):
  AWI series:           https://www.ssa.gov/oact/cola/AWIseries.html
  Bend point formula:   https://www.ssa.gov/oact/cola/bendpoints.html
  Taxable max series:   https://www.ssa.gov/oact/cola/cbb.html
  COLA series:          https://www.ssa.gov/oact/cola/colaseries.html
  Annual fact sheet:    https://www.ssa.gov/news/en/cola/factsheets/

Verified through: 2026 fact sheet (published Oct 2025).
Tables are user-overridable from the UI's "Edit SSA tables" modal.

WEP (Windfall Elimination Provision) and GPO (Government Pension Offset)
were repealed by the Social Security Fairness Act, effective for benefits
payable for months after December 2023. This module computes regular PIA
only — no WEP factor table, no WEP guarantee, no GPO offset.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


# ---------------------------------------------------------------------------
# Average Wage Index — used to (a) index past earnings to age-60 dollars and
# (b) derive PIA bend points each year.
# ---------------------------------------------------------------------------
# AWI(year) is the national average wage for that calendar year, published
# by SSA's Office of the Chief Actuary in October of year+1. So AWI(2024)
# was published Oct 2025 and is used for eligibility year 2026 bend points.
#
# 1977 base value ($9,779.44) anchors the bend-point formula and never
# changes. Pre-2011 values are well-documented constants.

AWI_BY_YEAR: dict[int, Decimal] = {
    1951: Decimal("2799.16"), 1952: Decimal("2973.32"), 1953: Decimal("3139.44"),
    1954: Decimal("3155.64"), 1955: Decimal("3301.44"), 1956: Decimal("3532.36"),
    1957: Decimal("3641.72"), 1958: Decimal("3673.80"), 1959: Decimal("3855.80"),
    1960: Decimal("4007.12"), 1961: Decimal("4086.76"), 1962: Decimal("4291.40"),
    1963: Decimal("4396.64"), 1964: Decimal("4576.32"), 1965: Decimal("4658.72"),
    1966: Decimal("4938.36"), 1967: Decimal("5213.44"), 1968: Decimal("5571.76"),
    1969: Decimal("5893.76"), 1970: Decimal("6186.24"), 1971: Decimal("6497.08"),
    1972: Decimal("7133.80"), 1973: Decimal("7580.16"), 1974: Decimal("8030.76"),
    1975: Decimal("8630.92"), 1976: Decimal("9226.48"), 1977: Decimal("9779.44"),
    1978: Decimal("10556.03"), 1979: Decimal("11479.46"), 1980: Decimal("12513.46"),
    1981: Decimal("13773.10"), 1982: Decimal("14531.34"), 1983: Decimal("15239.24"),
    1984: Decimal("16135.07"), 1985: Decimal("16822.51"), 1986: Decimal("17321.82"),
    1987: Decimal("18426.51"), 1988: Decimal("19334.04"), 1989: Decimal("20099.55"),
    1990: Decimal("21027.98"), 1991: Decimal("21811.60"), 1992: Decimal("22935.42"),
    1993: Decimal("23132.67"), 1994: Decimal("23753.53"), 1995: Decimal("24705.66"),
    1996: Decimal("25913.90"), 1997: Decimal("27426.00"), 1998: Decimal("28861.44"),
    1999: Decimal("30469.84"), 2000: Decimal("32154.82"), 2001: Decimal("32921.92"),
    2002: Decimal("33252.09"), 2003: Decimal("34064.95"), 2004: Decimal("35648.55"),
    2005: Decimal("36952.94"), 2006: Decimal("38651.41"), 2007: Decimal("40405.48"),
    2008: Decimal("41334.97"), 2009: Decimal("40711.61"), 2010: Decimal("41673.83"),
    # 2011 onward — values pasted from SSA AWI series
    2011: Decimal("42979.61"), 2012: Decimal("44321.67"), 2013: Decimal("44888.16"),
    2014: Decimal("46481.52"), 2015: Decimal("48098.63"), 2016: Decimal("48642.15"),
    2017: Decimal("50321.89"), 2018: Decimal("52145.80"), 2019: Decimal("54099.99"),
    2020: Decimal("55628.60"), 2021: Decimal("60575.07"), 2022: Decimal("63795.13"),
    2023: Decimal("66621.80"), 2024: Decimal("69846.57"),
}

AWI_1977 = AWI_BY_YEAR[1977]  # bend-point formula anchor

# Forward-projection assumption for years beyond the published AWI series.
# Matches SSA actuary's intermediate "wage growth" assumption and the
# pension calculator's GWI default. Used by `awi_for_year()` below.
DEFAULT_AWI_GROWTH_RATE = Decimal("0.035")


def awi_for_year(
    year: int,
    awi_table: dict[int, Decimal] | None = None,
    growth_rate: Decimal = DEFAULT_AWI_GROWTH_RATE,
) -> Decimal:
    """
    Return AWI for the requested year. If the year is in the published series
    (with optional user overrides), return that value directly. Otherwise
    project forward from the latest available year by compounding at
    `growth_rate` per year.

    The calculator's whole purpose is projecting future retirement, so we
    must extrapolate AWI past the SSA-published frontier — refusing would
    leave every realistic scenario at $0.
    """
    series = awi_table if awi_table is not None else AWI_BY_YEAR
    if year in series:
        return series[year]
    latest_year = max(series.keys())
    if year < latest_year:
        # Asking for a historical pre-1951 year we don't have — return latest
        # as a defensive fallback (shouldn't happen for any realistic input).
        return series[latest_year]
    years_ahead = year - latest_year
    factor = (Decimal(1) + growth_rate) ** years_ahead
    return (series[latest_year] * factor).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# Maximum taxable earnings (annual). Earnings above this don't count toward
# AIME and aren't subject to OASDI tax.
# ---------------------------------------------------------------------------

TAXABLE_MAX_BY_YEAR: dict[int, Decimal] = {
    1937: Decimal("3000"), 1938: Decimal("3000"), 1939: Decimal("3000"),
    1940: Decimal("3000"), 1941: Decimal("3000"), 1942: Decimal("3000"),
    1943: Decimal("3000"), 1944: Decimal("3000"), 1945: Decimal("3000"),
    1946: Decimal("3000"), 1947: Decimal("3000"), 1948: Decimal("3000"),
    1949: Decimal("3000"), 1950: Decimal("3000"),
    1951: Decimal("3600"), 1952: Decimal("3600"), 1953: Decimal("3600"),
    1954: Decimal("3600"),
    1955: Decimal("4200"), 1956: Decimal("4200"), 1957: Decimal("4200"),
    1958: Decimal("4200"),
    1959: Decimal("4800"), 1960: Decimal("4800"), 1961: Decimal("4800"),
    1962: Decimal("4800"), 1963: Decimal("4800"), 1964: Decimal("4800"),
    1965: Decimal("4800"),
    1966: Decimal("6600"), 1967: Decimal("6600"),
    1968: Decimal("7800"), 1969: Decimal("7800"), 1970: Decimal("7800"),
    1971: Decimal("7800"),
    1972: Decimal("9000"),
    1973: Decimal("10800"),
    1974: Decimal("13200"), 1975: Decimal("14100"), 1976: Decimal("15300"),
    1977: Decimal("16500"), 1978: Decimal("17700"), 1979: Decimal("22900"),
    1980: Decimal("25900"), 1981: Decimal("29700"), 1982: Decimal("32400"),
    1983: Decimal("35700"), 1984: Decimal("37800"), 1985: Decimal("39600"),
    1986: Decimal("42000"), 1987: Decimal("43800"), 1988: Decimal("45000"),
    1989: Decimal("48000"), 1990: Decimal("51300"), 1991: Decimal("53400"),
    1992: Decimal("55500"), 1993: Decimal("57600"), 1994: Decimal("60600"),
    1995: Decimal("61200"), 1996: Decimal("62700"), 1997: Decimal("65400"),
    1998: Decimal("68400"), 1999: Decimal("72600"), 2000: Decimal("76200"),
    2001: Decimal("80400"), 2002: Decimal("84900"), 2003: Decimal("87000"),
    2004: Decimal("87900"), 2005: Decimal("90000"), 2006: Decimal("94200"),
    2007: Decimal("97500"), 2008: Decimal("102000"), 2009: Decimal("106800"),
    2010: Decimal("106800"), 2011: Decimal("106800"), 2012: Decimal("110100"),
    2013: Decimal("113700"), 2014: Decimal("117000"), 2015: Decimal("118500"),
    2016: Decimal("118500"), 2017: Decimal("127200"), 2018: Decimal("128400"),
    2019: Decimal("132900"), 2020: Decimal("137700"), 2021: Decimal("142800"),
    2022: Decimal("147000"), 2023: Decimal("160200"), 2024: Decimal("168600"),
    2025: Decimal("176100"), 2026: Decimal("184500"),
}


# ---------------------------------------------------------------------------
# COLA — applied each January to benefits in payment. SS COLA tracks national
# CPI-W, distinct from the SF-Bay CPI-U that drives SJFD's COLA.
# ---------------------------------------------------------------------------

SS_COLA_BY_YEAR: dict[int, Decimal] = {
    2018: Decimal("0.020"), 2019: Decimal("0.028"), 2020: Decimal("0.016"),
    2021: Decimal("0.013"), 2022: Decimal("0.059"), 2023: Decimal("0.087"),
    2024: Decimal("0.032"), 2025: Decimal("0.025"), 2026: Decimal("0.028"),
}

# 10-year average for forward-projection assumption
DEFAULT_SS_COLA_RATE = Decimal("0.025")


# ---------------------------------------------------------------------------
# Full Retirement Age — set by statute. The schedule below covers everyone
# born after 1937. Earlier birth years have FRA = 65, but no SJFD member
# could plausibly be that old and still using this tool.
# ---------------------------------------------------------------------------

def full_retirement_age(birth_year: int) -> tuple[int, int]:
    """
    Returns (years, months) of the FRA for the given birth year.
    Per 42 USC §416(l).
    """
    if birth_year <= 1937: return (65, 0)
    if birth_year == 1938: return (65, 2)
    if birth_year == 1939: return (65, 4)
    if birth_year == 1940: return (65, 6)
    if birth_year == 1941: return (65, 8)
    if birth_year == 1942: return (65, 10)
    if 1943 <= birth_year <= 1954: return (66, 0)
    if birth_year == 1955: return (66, 2)
    if birth_year == 1956: return (66, 4)
    if birth_year == 1957: return (66, 6)
    if birth_year == 1958: return (66, 8)
    if birth_year == 1959: return (66, 10)
    return (67, 0)  # 1960 and later


# ---------------------------------------------------------------------------
# Bend points — derived from AWI rather than tabulated, so the table
# self-extends as users add future AWI values.
# ---------------------------------------------------------------------------

# 1979 base values for the bend-point formula. Per SSA, bend points equal
# these base values scaled by the ratio AWI(year-2) / AWI(1977), rounded to
# the nearest dollar. Eligibility year = year of attaining age 62.
_BP1_BASE = Decimal("180")
_BP2_BASE = Decimal("1085")


def bend_points(eligibility_year: int, awi: dict[int, Decimal] | None = None) -> tuple[Decimal, Decimal]:
    """
    Returns (b1, b2) for the given eligibility year (year of attaining age 62).
    For eligibility years beyond the published AWI series, the underlying
    AWI lookup projects forward via `awi_for_year` so future retirees still
    get usable bend points.
    """
    awi_value = awi_for_year(eligibility_year - 2, awi)
    ratio = awi_value / AWI_1977
    b1 = (_BP1_BASE * ratio).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    b2 = (_BP2_BASE * ratio).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return b1, b2
