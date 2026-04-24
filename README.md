# SJFD Tier 2 Retirement Calculator

A retirement planning tool for San José Fire Department Tier 2 employees (hired on or after January 2, 2015).

## For Claude Code: start here

1. **Read `SPEC.md` end-to-end first.** It is the single source of truth for this project and supersedes any other context.
2. **Authoritative source documents** are not tracked in this repo. SPEC.md references two external documents that must be treated as ground truth: the SJFD Tier 2 Fact Sheet (official pension rules, available from SJ Office of Retirement Services) and the FY 2026/27 bi-weekly pay table (the numbers themselves are embedded in `engine_py/defaults.py`).
3. **Ask clarifying questions** before writing any code if anything in the spec is ambiguous.
4. **Build the Python reference implementation and tests first** (SPEC.md §13 has the implementation order). Do not touch the web UI until the Python engine passes every test case in §11.

## Project goals

- Portable, single-file, client-side web tool (HTML + JS + localStorage).
- Calculation engine is built and proven correct in Python first, then ported to JS.
- Multi-user friendly: all personal data is user input, nothing hardcoded.
- Designed to be shared with peers as a file they open in any browser.

## What this tool is not

- Not official. Not legal advice. The SJ Office of Retirement Services is the authority. This tool is for planning scenarios only.
- Not a retirement-date calculator down to the day (v0 is whole-year retirement ages only — see SPEC.md §10 for v0 scope boundary).
- Not a disability/survivorship calculator. Service retirement only for v0.
