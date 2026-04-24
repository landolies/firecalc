# San José Fire Department — Tier 2 Retirement Calculator

## Project Brief for Claude Code

### Read this file first. It supersedes any prior conversation or example files.

---

## 1. What this tool is

A single-file, static HTML + JavaScript retirement calculator for San José Fire Department Tier 2 employees (hired on or after January 2, 2015). It projects pension benefits, salary, and years-of-service across configurable "what if" scenarios involving promotion timing and retirement date.

The tool is intended to be:
- **Fully client-side** — one HTML file, no server, no build step for deployment. Runs in any modern browser.
- **Portable** — can be opened locally from disk, emailed as an attachment, or hosted on any static file host. A peer with zero technical setup can use it.
- **Privacy-preserving** — all user inputs live in `localStorage` on the user's own device. No data leaves the browser.
- **Multi-user by design** — no accounts, no hardcoded personal data. Every input (birth date, hire date, rank, step, step progression history, pay grid, rates) is editable.

The user is a current SJFD firefighter (Tier 2) modeling his own retirement decisions and also intends to share the tool with peers in similar situations.

---

## 2. Architecture

Two components:

### 2.1 Python reference implementation (`/engine_py/`)
A pure calculation library with **no UI and no state**. The public interface is a single function:

```python
def compute_retirement_scenario(inputs: ScenarioInputs) -> ScenarioResult
```

Where `ScenarioInputs` captures every user-controllable variable (see §6) and `ScenarioResult` contains the full audit trail: per-year salary timeline, FC calculation details, benefit % derivation, penalty calculation, COLA application, and final pension figures.

This reference implementation exists **only to validate the math**. It is exercised by a pytest test suite (`/engine_py/tests/`) containing hand-worked scenarios (see §11). It is **not** shipped to end users.

### 2.2 Production web tool (`/web/index.html`)
A single HTML file containing inline CSS and JavaScript. The JS implements the same calculation logic as the Python reference and must produce **byte-identical numerical output** for the test scenarios. Persistence is via `localStorage`.

A small test harness (`/web/tests/`) should verify the JS calculation engine against the same test cases as the Python reference. A reasonable approach: generate JSON fixtures from the Python test suite, then have a Node-based test runner (or a browser test page) feed those fixtures to the JS engine and compare.

---

## 3. Authoritative source documents

Two external references are ground truth. They are **not tracked in this repo**; consult them directly from the authoritative sources (SJ Office of Retirement Services for the Fact Sheet; the SJFD salary schedule for the pay table). If anything in this spec appears to contradict them, the source documents win.

### 3.1 SJFD Tier 2 Fact Sheet
The official SJFD Tier 2 pension rules as of 6/22/2025. Covers contribution rates, vesting, benefit formula, early retirement reductions, disability retirement, survivorship, reciprocity, COLA, and post-retirement marriage provisions.

For v0 the calculator only models **service retirement** (both active and deferred vested). Disability retirement, survivorship benefits, and post-retirement marriage provisions are out of scope but should be noted in the UI as "not modeled."

### 3.2 FY 2026/27 bi-weekly pay table
The official SJFD bi-weekly salary table for Fiscal Year 2026/27, including the 3.50% General Wage Increase (GWI). This is the starting pay grid.

**Extract these salaries exactly** (all figures in USD, bi-weekly):

| Rank | Step 1 | Step 2 | Step 3 | Step 4 | Step 5 | Step 6 | Step 7 |
|---|---|---|---|---|---|---|---|
| Firefighter Recruit (2310) | 4148.72 | — | — | — | — | — | — |
| Firefighter (2311) | 4769.02 | 4998.58 | 5239.87 | 5494.83 | 5760.53 | 6036.98 | 6343.70 |
| Fire Engineer (2312) | 5816.21 | 6097.55 | 6391.58 | 6707.11 | 7041.59 | 7384.54 | — |
| Fire Captain (2313) | 6669.01 | 6995.28 | 7335.23 | 7693.73 | 8079.66 | — | — |

Other classifications visible in the photo (Fire Prevention Inspector, Arson Investigator, Battalion Chief) are **out of scope for v0**.

These values are the **defaults** shown in the UI and must be editable by the user (so a new contract's numbers can be typed in without changing code).

---

## 4. Calculation rules

### 4.1 Pension benefit formula (service retirement)

Benefit percentage based on Years of Service (YOS):
- Years 1–20: 2.4% per year
- Years 21–25: 3.0% per year
- Years 26+: 3.4% per year
- Hard cap: **80% of Final Compensation**

The 80% cap is reached at exactly **30.0 YOS**: (20 × 2.4%) + (5 × 3.0%) + (5 × 3.4%) = 48% + 15% + 17% = 80%.

Working beyond 30 YOS yields **no additional pension benefit** — salary only. The UI must clearly flag the date the cap is reached and communicate this.

### 4.2 Final Compensation (FC)

Per the Fact Sheet: "the average annual base pay plus any premium pays authorized by ordinance for the highest 3 consecutive Years of Service."

For v0, **premium pays are not modeled** — only base pay is used. The UI must display a note: "Premium pays (EMT/paramedic, specialty assignments, etc.) are not included in this calculation. A future version will support them."

The calculator must compute FC **two ways** and display both:

- **FC_3yr_avg**: The true trailing 3-year average of annual base salary over the final 3 YOS before retirement.
- **FC_final**: The annualized salary in the final year only (bi-weekly × 26).

Both pension figures are shown side-by-side. The 3-year average is the more accurate figure per the Fact Sheet; the final-year figure is the simpler optimistic approximation.

### 4.3 Early retirement reduction (active service retirement)

If retiring at age 50–56 with at least 5 YOS: pension is reduced by **7% per year** between the retirement age and age 57, prorated to the closest month.

For v0 (whole-year retirement ages), the prorating simplifies to: `reduction = (57 − retirement_age) × 0.07`, clamped at 0 for age ≥ 57.

Minimum retirement age under this plan is **50**. Below 50 the tool should not produce a scenario and instead show a warning.

### 4.4 Deferred vested retirement

A separate path: the user separates from City service before retirement (with at least 5 YOS) but leaves their contributions in the plan, then begins drawing pension later. Same 7%/year reduction structure applies.

**Key modeling difference**: FC is **frozen at the date of separation**. No GWI or COLA growth applies between separation and the pension start date.

The UI provides a toggle: "Retirement type: Active service / Deferred vested". When deferred vested is selected, the user specifies both a **separation date** and a **pension start date** (age 50 or later).

### 4.5 Cost-of-Living Adjustment (COLA)

Per the Fact Sheet: applied annually on February 1, capped at 2.0%, based on CPI-U for San Jose-San Francisco-Oakland (Dec-to-Dec). The user noted that this region has historically exceeded 2% most years, so the full 2.0% is a realistic modeling assumption.

COLA is a **user-editable parameter** (default 2.0%, range 0–2.0%).

The UI provides a **COLA display toggle**:
- **"Today's dollars"**: Pension shown at retirement value, no COLA applied. Simpler to compare scenarios.
- **"With COLA"**: Pension projected forward compounding at the COLA rate annually from retirement date.

The toggle must include an inline explainer: *"COLA (Cost-of-Living Adjustment) increases your pension each year after retirement to offset inflation. Toggle this to see your pension in today's purchasing power versus its projected future dollar amount."*

The first COLA after retirement is prorated by months retired prior to February 1 (partial months excluded). For v0 simplicity using whole-year retirement, use retirement-date month to determine the first-year proration.

### 4.6 General Wage Increase (GWI)

User-editable parameter (default 3.5%, based on the user's stated 34-year historical average).

Applied **annually on July 1** to the **entire salary grid**. Every step at every rank scales by (1 + GWI) each July 1. This means a Firefighter Step 7 in FY 2027/28 earns 3.5% more than a Firefighter Step 7 did in FY 2026/27.

The user also wants a "guaranteed vs. projected" comparison: the ability to see scenarios with GWI = 0% (no future raises guaranteed) alongside GWI = 3.5% (projected). This is achieved by the user changing the GWI input and comparing — no special UI needed beyond making the input prominent and easy to toggle between 0% and 3.5%.

### 4.7 Step increases

- Step increases occur on the **anniversary of the last rank change** (hire date for original rank, promotion date for any promoted rank).
- They advance one step per year until the top step of the current rank is reached.
- Tier 2 user must have 1 YOS at each step before advancing (i.e., hire 3/24/2019 → Step 2 on 3/24/2020 → Step 3 on 3/24/2021 → ... → Step 7 on 3/24/2025).
- Current step and the date of arrival at current step are **user-configurable** — not hardcoded. The tool must handle users who arrived at their current step out of the normal cadence (e.g., lateral hires).

### 4.8 Promotions

When the user specifies a promotion at a given date:
- **Landing step auto-computed**: the lowest step in the new rank whose bi-weekly pay is at least **5% higher** than the pre-promotion bi-weekly pay. Per SJFD promotion rules, promotions must result in at least a 5% pay increase.
- After promotion, annual step increases resume on the **anniversary of the promotion date** until the top step of the new rank.
- Promotion from Firefighter directly to Captain (skipping Engineer) is allowed. The landing-step rule applies identically.
- No minimum time-in-rank prerequisite is enforced in v0.

### 4.9 Annualization

Bi-weekly pay × 26 = annual pay. Flagged in the UI as "Note: actual years contain ~26.09 biweekly pay periods; this tool uses the standard 26 × approximation for pension calculation, consistent with common practice."

### 4.10 Forced retirement

Age 70 is the mandatory retirement age. Scenario tables should extend through age 70 but may show "past 80% cap, no pension gain" for every year beyond cap reach.

### 4.11 Vesting

Minimum 5 YOS required to receive any pension benefit. Scenarios with less than 5 YOS at retirement should not produce a pension figure and should show a "not vested" warning.

---

## 5. User inputs and defaults

All inputs are editable and persisted to localStorage. The UI is organized into logical groups.

### 5.1 Personal information
- Birth date (date input)
- Hire date (date input)
- Current rank (dropdown: Firefighter / Fire Engineer / Fire Captain)
- Current step (integer input, 1 to rank's max step)
- Date arrived at current step (date input; defaults to current-step arrival computed from hire date + normal progression, but user-editable)

### 5.2 Pay grid
A table showing current bi-weekly pay for every rank × step combination. Pre-populated with FY 2026/27 values from §3.2. Every cell is editable.

### 5.3 Rate assumptions
- GWI rate (percent, default 3.5%)
- COLA rate (percent, default 2.0%, max 2.0%)

### 5.4 Scenario configuration
The user defines one or more "what if" scenarios. Each scenario specifies:
- Retirement age (integer, 50–70)
- Optional promotion events: a list of `{rank: "Engineer"|"Captain", date: YYYY-MM-DD}` entries
- Retirement type (Active service / Deferred vested)
- If deferred vested: separation date + pension start date

The "no promotion" baseline scenario is always present and shows the path if the user stays at current rank until retirement.

### 5.5 Display toggles
- COLA: "Today's dollars" / "With COLA" (see §4.5)
- Current timestamp for YOS calculation (defaults to today, overridable for testing)

---

## 6. `ScenarioInputs` schema (Python reference)

```python
@dataclass
class PayGrid:
    # Bi-weekly pay by rank and step. Missing (rank, step) pairs mean that step
    # doesn't exist for that rank (e.g., Captain has no Step 6 or 7).
    rates: dict[tuple[str, int], Decimal]  # e.g., ("Firefighter", 7) -> Decimal("6343.70")

@dataclass
class PromotionEvent:
    new_rank: str               # "Fire Engineer" or "Fire Captain"
    effective_date: date

@dataclass
class ScenarioInputs:
    # Personal
    birth_date: date
    hire_date: date
    current_rank: str
    current_step: int
    current_step_arrival_date: date
    
    # Pay grid
    pay_grid: PayGrid
    pay_grid_effective_date: date      # When the pay grid values are current as-of. GWI grows grid from this date forward (and shrinks it backward for historical salaries).
    
    # Rates
    gwi_rate: Decimal                   # e.g., Decimal("0.035")
    cola_rate: Decimal                  # e.g., Decimal("0.020")
    gwi_effective_month_day: tuple[int, int]  # (7, 1) for July 1
    cola_effective_month_day: tuple[int, int] # (2, 1) for February 1
    
    # Scenario
    retirement_age: int
    promotions: list[PromotionEvent]
    retirement_type: str                # "active" or "deferred_vested"
    separation_date: Optional[date]     # required if deferred_vested
    pension_start_date: Optional[date]  # required if deferred_vested
    
    # Display
    show_cola: bool                     # if True, project pension forward with COLA
    as_of_date: date                    # for YOS calculation; defaults to today
```

### `ScenarioResult` must include:
- Derived retirement date (from retirement_age + birth_date)
- Years of service at retirement (precise, not rounded)
- Final rank and step at retirement
- FC_3yr_avg and FC_final (both annual)
- Benefit percentage (with tier-by-tier breakdown)
- 80% cap flag + date cap was reached (if applicable)
- Early retirement reduction percent (with derivation)
- Annual and monthly pension at retirement (both FC methods, both with/without COLA projections for each year from retirement to age ~95)
- Full salary timeline: list of `{date_range, rank, step, biweekly, annual}` entries covering from hire to retirement/separation
- The 3 specific consecutive years used for FC_3yr_avg
- Warnings list (e.g., "Not vested", "Retirement below minimum age 50")

---

## 7. Scenario grid / output

The primary output is a **scenario array table**, one row per scenario. Columns (at minimum):

| Retirement Age | Retirement Date | Promotion Path | Final Rank/Step | YOS | FC (3yr avg) | FC (final year) | Benefit % | Cap Reached? | Early Penalty | Annual Pension (3yr FC) | Monthly Pension (3yr FC) | Annual Pension (final-yr FC) | Monthly Pension (final-yr FC) |

Each row is clickable and opens an **audit drawer**.

The user's original motivation: promotions are optional career decisions. The grid makes it easy to answer "if I promote to Engineer at age 42 and retire at 55 vs. stay Firefighter and retire at 55, what's the difference?" — that should be visually obvious.

A reasonable default population: for each "what if" promotion configuration the user enters, generate rows for retirement ages 50, 52, 55, 57, 60, 65, 70. The user can add/remove retirement ages.

### 7.1 Audit drawer contents

Full derivation for one selected scenario:
- Personal inputs summary
- Salary timeline: table of every pay change from hire to retirement with date, event ("hired", "step increase", "GWI", "promotion"), rank, step, biweekly, annual
- FC calculation: the 3 consecutive YOS with highest aggregate base pay, annual salary for each of those 3 years, and the average
- Benefit % derivation: "20 × 2.4% = 48.0%, plus 5 × 3.0% = 15.0%, plus 2.3 × 3.4% = 7.82%, total 70.82%"
- 80% cap application (if it applied)
- Early retirement calculation (if applied): "Retiring at age 54, which is 3 years before age 57. Reduction = 3 × 7% = 21%. Pension × (1 − 0.21) = $X"
- COLA projection table (if toggle is on): year-by-year pension from retirement to age 95
- Annual pension (both FC methods) and monthly
- Warnings

### 7.2 Exports

- **PDF export**: one scenario's audit drawer content formatted for printing, or the full grid summary. Printable via browser print-to-PDF is acceptable for v0; a dedicated "Print view" CSS stylesheet should be included so the output is presentable.
- **CSV export**: the scenario grid as a downloadable CSV. Plain text download via `Blob` + `a[download]` — no library needed.

---

## 8. UI layout suggestion

Top: sticky header with user summary (name/initials optional, current rank/step, today's YOS, current annual pay).

Left column (or collapsible sidebar): all inputs (personal, pay grid, rates, scenario builder).

Main area: scenario grid. Row click opens audit drawer as a right-side slide-out or full-width section below the grid.

Export buttons prominent: "Export scenarios as CSV", "Export this scenario as PDF", "Print this view".

Design tokens and patterns: see `/mnt/skills/public/frontend-design/SKILL.md` when you start the web component. The tool should feel professional (this is financial planning, not a toy), readable, and trustworthy — not flashy.

---

## 9. Persistence

All inputs persist to `localStorage` under a single JSON blob with a versioned schema key (e.g., `sjfd_retirement_calculator_v1`). Include a version number so future schema migrations are possible. On load, if stored data's schema version is older than the current one, run a migration (or fall back to defaults and warn).

Provide a "Reset to defaults" button that clears localStorage and reloads with FY 2026/27 pay grid defaults.

---

## 10. v0 scope boundary (DO NOT BUILD in v0)

Explicitly out of scope for this initial build. Note each in the UI as "coming soon" or "future version" where relevant:

- Premium pays in FC calculation
- Disability retirement
- Survivorship benefits
- Post-retirement marriage provisions
- Battalion Chief, Fire Prevention Inspector, Arson Investigator ranks
- VEBA account tracking
- CalPERS reciprocity
- Per-year GWI overrides (single flat rate only in v0)
- Sub-annual retirement dates (whole ages only in v0)
- "Punch in any date" for retirement (whole ages only; future version adds date picker)
- Multi-user accounts (single-user-per-device via localStorage only)
- Server-side anything

---

## 11. Test cases (required before UI work)

The Python reference implementation must pass the following test cases before any web UI work begins. Add more as the implementation reveals edge cases.

### 11.1 Known-good trivial cases

- **Vested minimum**: hire 1/1/2020, retire at age 57 on 1/1/2025 (exactly 5 YOS). Benefit % = 5 × 2.4% = 12.0%. No cap, no early penalty. Verify correct FC.
- **80% cap exactly**: 30 YOS retirement at age 57+. Benefit % = 80.0% exactly. Any additional years don't change pension.
- **Below minimum age**: retire at 49. Returns a warning and no pension figure.
- **Below vesting**: retire at 57 with 4 YOS. Returns "not vested" warning, no pension.

### 11.2 Early retirement

- Retire at 54, YOS 20, FC $160,000, no promotions.
  - Benefit % = 20 × 2.4% = 48%
  - Base pension = $76,800
  - Early reduction = 3 × 7% = 21%
  - Final pension = $76,800 × 0.79 = $60,672
- Retire at 50, YOS 20. Reduction = 49%. Verify floor behavior.

### 11.3 Tier transitions

- Retire with exactly 20.0 YOS: all 20 years at 2.4%. Benefit % = 48.0%.
- Retire with exactly 25.0 YOS: 48% + 15% = 63.0%.
- Retire with exactly 30.0 YOS: 80.0% (cap reached precisely).
- Retire with 35.0 YOS: still 80.0% (capped).
- Retire with 22.5 YOS: 48% + (2.5 × 3.0%) = 55.5%.
- Retire with 27.8 YOS: 48% + 15% + (2.8 × 3.4%) = 72.52%.

### 11.4 Promotions

- Firefighter Step 7 (bi-weekly 6343.70) promoted to Fire Engineer on a specified date. Landing step must be the lowest Engineer step whose bi-weekly ≥ 6343.70 × 1.05 = 6660.89. That's Engineer Step 4 (6707.11). Verify.
- Firefighter Step 7 promoted directly to Fire Captain. Landing step ≥ 6660.89. That's Captain Step 3 (7335.23). Wait — let me re-check: Captain Step 1 is 6669.01 which is ≥ 6660.89. So landing is Captain Step 1. Verify the auto-compute finds the **lowest** qualifying step.
- Post-promotion step increases: promoted at date D, next step increase on D+1year, continues annually until top of new rank.

### 11.5 FC methods diverge

- Retire at age 57 after a promotion at age 54. FC_3yr_avg reflects a mix of pre- and post-promotion salary. FC_final uses only the final year's (post-promotion) salary. The two should differ meaningfully.

### 11.6 GWI growth

- With GWI = 0%, Firefighter Step 7 earns $164,936.20 annually forever.
- With GWI = 3.5%, Firefighter Step 7 in the next fiscal year (post-July 1) earns $164,936.20 × 1.035 = $170,708.97. Verify grid scaling.
- With GWI = 3.5%, in 10 fiscal years the same step/rank earns $164,936.20 × (1.035^10) = $232,693.43. Verify compounding.

### 11.7 COLA projection

- Retire at 57 with $80,000 annual pension, COLA = 2.0%.
  - Year 1 (retirement year): $80,000
  - Year 2: $81,600
  - Year 10: $80,000 × 1.02^9 = $95,605.87
  - Toggled off: $80,000 every year.

### 11.8 Deferred vested

- Separate at age 48 with 15 YOS, FC_final at separation = $150,000. Start pension at age 57.
  - FC is frozen at separation ($150,000).
  - Benefit % = 15 × 2.4% = 36%.
  - Base pension = $54,000.
  - No early reduction (starts at 57).
  - Verify FC does NOT grow with GWI during the wait.

### 11.9 Reference case: the spec author

- Birth date 10/1/1986, hire date 3/24/2019, currently Firefighter Step 7 (arrived 3/24/2025).
- No promotions, retire at age 57 (10/1/2043).
- YOS = 24.52 (from 3/24/2019 to 10/1/2043 = 24 years, 6 months, 8 days).
- Benefit % = 20 × 2.4% + 4.52 × 3.0% = 48% + 13.56% = 61.56%.
- With GWI = 3.5%, compute FC_3yr_avg and FC_final. Verify both.
- Monthly pension (3yr FC method) should be the primary number.

---

## 12. File layout

```
/
├── SPEC.md                              ← this file
├── README.md                            ← quick-start for Claude Code
├── index.html                           ← root redirect → web/index.html (for GitHub Pages)
│
├── engine_py/                           ← Python reference implementation
│   ├── __init__.py
│   ├── models.py                        ← dataclasses (ScenarioInputs, ScenarioResult, PayGrid, PromotionEvent)
│   ├── engine.py                        ← compute_retirement_scenario()
│   ├── pay_timeline.py                  ← salary progression (step + GWI + promotions)
│   ├── pension.py                       ← FC, benefit %, cap, early penalty, COLA
│   ├── defaults.py                      ← FY 2026/27 pay grid constants
│   └── tests/
│       ├── test_vesting.py
│       ├── test_early_retirement.py
│       ├── test_tier_transitions.py
│       ├── test_promotions.py
│       ├── test_fc_methods.py
│       ├── test_gwi.py
│       ├── test_cola.py
│       ├── test_deferred_vested.py
│       └── test_reference_case.py
│
├── fixtures/                            ← JSON test fixtures generated from Python tests
│   └── scenarios.json
│
└── web/
    ├── engine.js                        ← JS port of engine_py (used by index.html)
    ├── vendor/decimal.min.js            ← Decimal arithmetic library
    ├── index.html                       ← the user-facing calculator (CSS + JS inline in body)
    └── tests/
        └── run_tests.html               ← browser test page that loads fixtures and runs JS engine
```

---

## 13. Implementation order

1. Read this spec end-to-end. Read the PDF. Read the pay table image. Ask clarifying questions before writing any code if anything is ambiguous.
2. Draft `models.py` with the data classes from §6.
3. Draft `defaults.py` with the FY 2026/27 pay grid from §3.2.
4. Implement `pay_timeline.py`: given inputs, produce the full salary-by-date timeline from hire through retirement (or separation, for deferred vested). This is the trickiest piece — step increases, GWI on July 1, promotions, landing-step auto-compute.
5. Implement `pension.py`: FC computation (both methods), benefit % with tier logic, 80% cap, early penalty, COLA projection.
6. Wire it all together in `engine.py` behind the `compute_retirement_scenario` function.
7. Write all tests in §11. Run. Fix. Repeat until green.
8. Generate JSON fixtures for the web engine.
9. Build `web/index.html`: inputs, scenario grid, audit drawer, exports, localStorage persistence.
10. Port the calculation logic to JavaScript within `index.html`.
11. Verify JS engine matches Python engine on all fixtures.
12. Polish UI per `/mnt/skills/public/frontend-design/SKILL.md` principles.

---

## 14. Decisions already made (do not re-litigate)

These were settled during the planning phase. Changing them requires a new discussion; for v0, treat them as given:

- Whole-year retirement ages only; monthly/arbitrary dates are future work.
- Birthday is the retirement date convention (retire "at 55" means on 55th birthday).
- Bi-weekly × 26 is the annualizer; flagged as approximation.
- Deferred vested: FC frozen at separation, no indexing.
- COLA default 2.0%, editable, capped at 2.0%.
- GWI default 3.5%, editable. Single flat rate in v0; per-year override is future work.
- Promotion auto-computes landing step using ≥5% rule; FF → Captain directly is allowed.
- No time-in-rank prerequisite for promotions in v0.
- Minimum retirement age 50, minimum 5 YOS for vesting.
- Output format is a scenario grid with clickable audit drawer.
- PDF export via browser print-to-PDF with a print stylesheet; CSV export via Blob download.
- Single-file static HTML, client-side only, localStorage for persistence.

---

## 15. Known approximations and caveats (user-facing disclaimers)

These should appear in the UI as a collapsible "Methodology & caveats" section:

1. Uses biweekly × 26 = annual. Actual years have ~26.09 periods.
2. Premium pays not included in FC (v0).
3. Early retirement prorating done in whole years (v0); Fact Sheet specifies prorating to closest month.
4. Historical pay assumed to follow same grid × GWI deflation; users who experienced actual different raises may have slightly different FC_3yr_avg.
5. COLA assumed to hit the 2% cap each year (historically realistic for this region but not guaranteed).
6. GWI is an assumption, not guaranteed by contract.
7. CalPERS reciprocity not modeled.
8. Disability and survivorship scenarios not modeled.
9. This tool is for planning purposes only. Actual pension is calculated by the SJ Office of Retirement Services per Municipal Code; governing law prevails in any conflict. Contact ORS at (408) 794-1000 or sjretirement.com for official figures.

---

## End of spec.
