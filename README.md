# SJFD Tier 2 Retirement Calculator

A retirement planning tool for San José Fire Department Tier 2 employees (hired on or after January 2, 2015).

## For Claude Code: start here

1. **Read `SPEC.md` end-to-end first.** It is the single source of truth for this project and supersedes any other context.
2. **Read the two reference documents** that SPEC.md points to:
   - `Fire_Fact_Sheet_Tier_2.pdf` — official pension rules
   - `PXL_20260204_201446011.jpg` — FY 2026/27 bi-weekly pay table
3. **Ask clarifying questions** before writing any code if anything in the spec is ambiguous or seems to conflict with the reference documents.
4. **Build the Python reference implementation and tests first** (SPEC.md §13 has the implementation order). Do not touch the web UI until the Python engine passes every test case in §11.
5. The `reference-do-not-use/` folder contains older spreadsheets with broken math. Do not copy their logic. They are preserved only to illustrate what the end product should roughly look like visually.

## Project goals

- Portable, single-file, client-side web tool (HTML + JS + localStorage).
- Calculation engine is built and proven correct in Python first, then ported to JS.
- Multi-user friendly: all personal data is user input, nothing hardcoded.
- Designed to be shared with peers as a file they open in any browser.

## What this tool is not

- Not official. Not legal advice. The SJ Office of Retirement Services is the authority. This tool is for planning scenarios only.
- Not a retirement-date calculator down to the day (v0 is whole-year retirement ages only — see SPEC.md §10 for v0 scope boundary).
- Not a disability/survivorship calculator. Service retirement only for v0.
