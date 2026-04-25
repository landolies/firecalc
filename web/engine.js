/*
 * FireCalc engine — JavaScript port of engine_py/.
 * Requires decimal.js loaded beforehand (exposes global `Decimal`).
 * Produces byte-identical output to the Python reference for all fixtures
 * in fixtures/scenarios.json (SPEC §2.2).
 *
 * Structure mirrors Python:
 *   A. Dates          (replaces Python `datetime.date`)
 *   B. Models         (plain-object shapes; no classes)
 *   C. Pay timeline   (engine_py/pay_timeline.py)
 *   D. Pension        (engine_py/pension.py)
 *   E. Engine         (engine_py/engine.py)
 *   F. Defaults       (engine_py/defaults.py)
 *   G. Serialization  (engine_py/_serialize.py)
 *   H. Namespace export
 */
(function (global) {
  "use strict";

  const D = global.Decimal;
  if (!D) throw new Error("engine.js requires decimal.js to be loaded first");

  // Match Python Decimal's default sufficient precision; ROUND_HALF_UP is our rounding mode.
  D.set({ precision: 40, rounding: D.ROUND_HALF_UP });

  const TWO_PLACES = new D("0.01");
  const FOUR_PLACES = new D("0.0001");
  const ZERO = new D("0");
  const TWELVE = new D("12");

  // round2/round4 tag the returned Decimal with its displayed precision so
  // toJsonable can reproduce Python's trailing-zero-preserving str(Decimal).
  function round2(d) {
    const r = d.toDecimalPlaces(2, D.ROUND_HALF_UP);
    r._dp = 2;
    return r;
  }
  function round4(d) {
    const r = d.toDecimalPlaces(4, D.ROUND_HALF_UP);
    r._dp = 4;
    return r;
  }

  function decStr(d) {
    return d._dp !== undefined ? d.toFixed(d._dp) : d.toString();
  }

  // Parse a Decimal from a string and tag with the string's visible precision
  // so "0.020" round-trips as "0.020" (not "0.02").
  function decFromStr(s) {
    const d = new D(s);
    const dotIdx = s.indexOf(".");
    if (dotIdx >= 0) d._dp = s.length - dotIdx - 1;
    return d;
  }

  // ---------- A. Dates --------------------------------------------------

  function parseIsoDate(s) {
    const [y, m, d] = s.split("-").map(Number);
    return { year: y, month: m, day: d };
  }

  function isoDate(d) {
    const mm = String(d.month).padStart(2, "0");
    const dd = String(d.day).padStart(2, "0");
    return `${d.year}-${mm}-${dd}`;
  }

  function isLeap(y) { return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0; }
  const _DAYS_IN_MONTH = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  function daysInMonth(y, m) {
    if (m === 2 && isLeap(y)) return 29;
    return _DAYS_IN_MONTH[m];
  }

  // Proleptic Gregorian ordinal (days since year 1 Jan 1), matching Python datetime.
  function toOrdinal(d) {
    const y = d.year - 1;
    let days = y * 365 + Math.floor(y / 4) - Math.floor(y / 100) + Math.floor(y / 400);
    for (let m = 1; m < d.month; m++) days += daysInMonth(d.year, m);
    return days + d.day;
  }

  function daysBetween(a, b) { return toOrdinal(b) - toOrdinal(a); }

  function compareDates(a, b) {
    if (a.year !== b.year) return a.year < b.year ? -1 : 1;
    if (a.month !== b.month) return a.month < b.month ? -1 : 1;
    if (a.day !== b.day) return a.day < b.day ? -1 : 1;
    return 0;
  }

  function addYears(d, n) {
    const y = d.year + n;
    // Feb 29 clamp → Feb 28 (matches Python _add_years fallback).
    if (d.month === 2 && d.day === 29 && !isLeap(y)) {
      return { year: y, month: 2, day: 28 };
    }
    return { year: y, month: d.month, day: d.day };
  }

  function mdLess(a, b) {
    if (a.month !== b.month) return a.month < b.month;
    return a.day < b.day;
  }

  // ---------- B. Models -------------------------------------------------

  // PayGrid.rates is a Map keyed by "rank|step" string; values are Decimal.
  // Matches the flattened key format from engine_py/_serialize.py::_key.
  function payGridGet(pg, rank, step) {
    return pg.rates.get(`${rank}|${step}`) || null;
  }

  function payGridMaxStep(pg, rank) {
    let mx = -Infinity;
    for (const key of pg.rates.keys()) {
      const [r, s] = key.split("|");
      if (r === rank) {
        const n = parseInt(s, 10);
        if (n > mx) mx = n;
      }
    }
    if (mx === -Infinity) throw new Error(`Unknown rank: ${JSON.stringify(rank)}`);
    return mx;
  }

  // ---------- C. Pay timeline (engine_py/pay_timeline.py) --------------

  function gwiExponent(gridEffective, target, gwiMonth, gwiDay) {
    function fy(d) {
      const cutoff = { year: d.year, month: gwiMonth, day: gwiDay };
      return compareDates(d, cutoff) >= 0 ? d.year : d.year - 1;
    }
    return fy(target) - fy(gridEffective);
  }

  function adjustedBiweekly(base, gridEffective, target, gwiRate, gwiMonth, gwiDay) {
    const n = gwiExponent(gridEffective, target, gwiMonth, gwiDay);
    if (n === 0) return round2(base);
    // Match Python: factor = Decimal(str((1 + float(gwi_rate)) ** abs(n)))
    const floatRate = Number(gwiRate.toString());
    const factor = new D(String(Math.pow(1 + floatRate, Math.abs(n))));
    return round2(n > 0 ? base.times(factor) : base.div(factor));
  }

  function nextGwiAfter(d, gwiMonth, gwiDay) {
    const candidate = { year: d.year, month: gwiMonth, day: gwiDay };
    if (compareDates(candidate, d) > 0) return candidate;
    return { year: d.year + 1, month: gwiMonth, day: gwiDay };
  }

  function landingStep(newRank, preBw, payGrid, gridEff, promoDate, gwiRate, gwiMonth, gwiDay) {
    const threshold = preBw.times(new D("1.05"));
    const max = payGridMaxStep(payGrid, newRank);
    for (let step = 1; step <= max; step++) {
      const base = payGridGet(payGrid, newRank, step);
      if (base === null) continue;
      const adj = adjustedBiweekly(base, gridEff, promoDate, gwiRate, gwiMonth, gwiDay);
      if (adj.gte(threshold)) return { step, ok: true };
    }
    return { step: max, ok: false };
  }

  function yearsBetween(earlier, later) {
    let years = later.year - earlier.year;
    if (mdLess(later, earlier)) years -= 1;
    return Math.max(0, years);
  }

  const RANK_ORDER = [
    "Firefighter Recruit", "Firefighter", "Fire Engineer",
    "Fire Prevention Inspector", "Arson Investigator",
    "Fire Captain", "Battalion Chief",
  ];
  const LINEAR_LADDER = [
    "Firefighter Recruit", "Firefighter", "Fire Engineer",
    "Fire Captain", "Battalion Chief",
  ];
  const SPECIALTY_RANKS = new Set(["Fire Prevention Inspector", "Arson Investigator"]);

  function rankBeforePromotion(newRank) {
    if (SPECIALTY_RANKS.has(newRank)) return "Firefighter";
    const idx = LINEAR_LADDER.indexOf(newRank);
    if (idx <= 1) return "Firefighter";
    return LINEAR_LADDER[idx - 1];
  }

  function buildSalaryTimeline(inputs, endDate, warnings) {
    if (compareDates(endDate, inputs.hire_date) <= 0) return [];

    const [gm, gd] = inputs.gwi_effective_month_day;
    const gridEff = inputs.pay_grid_effective_date;

    const promotions = inputs.promotions
      .filter((p) => compareDates(p.effective_date, endDate) < 0)
      .slice()
      .sort((a, b) => compareDates(a.effective_date, b.effective_date));

    for (const p of promotions) {
      if (compareDates(p.effective_date, inputs.hire_date) <= 0) {
        throw new Error(`Promotion date ${isoDate(p.effective_date)} must be after hire date ${isoDate(inputs.hire_date)}`);
      }
    }

    let initialRank = inputs.current_rank;
    if (promotions.length > 0) {
      initialRank = rankBeforePromotion(promotions[0].new_rank);
    }

    let initialStep, stepClock0;
    if (promotions.length === 0 || initialRank === inputs.current_rank) {
      stepClock0 = addYears(inputs.current_step_arrival_date, -(inputs.current_step - 1));
      initialStep = 1 + yearsBetween(stepClock0, inputs.hire_date);
      initialStep = Math.max(1, Math.min(initialStep, payGridMaxStep(inputs.pay_grid, initialRank)));
    } else {
      initialStep = 1;
      stepClock0 = inputs.hire_date;
    }

    let rank = initialRank;
    let step = initialStep;
    let stepClock = stepClock0;
    const promoQueue = promotions.slice();

    let cursor = inputs.hire_date;
    let eventLabel = "hired";
    const periods = [];

    const MAX_ITERATIONS = 10000;
    let iter = 0;
    while (compareDates(cursor, endDate) < 0) {
      iter++;
      if (iter > MAX_ITERATIONS) {
        throw new Error(`buildSalaryTimeline exceeded ${MAX_ITERATIONS} iterations at ${isoDate(cursor)}`);
      }

      const candidates = [];

      const nextGwi = nextGwiAfter(cursor, gm, gd);
      if (compareDates(nextGwi, endDate) < 0) candidates.push([nextGwi, "gwi"]);

      const maxSt = payGridMaxStep(inputs.pay_grid, rank);
      if (step < maxSt) {
        const nextStepDate = addYears(stepClock, step);
        if (compareDates(nextStepDate, endDate) < 0) candidates.push([nextStepDate, "step_increase"]);
      }

      if (promoQueue.length > 0) {
        candidates.push([promoQueue[0].effective_date, "promotion"]);
      }

      if (candidates.length === 0) break;

      // min by date
      let nextEventDate = candidates[0][0];
      for (const [d] of candidates) if (compareDates(d, nextEventDate) < 0) nextEventDate = d;

      if (compareDates(nextEventDate, cursor) <= 0) {
        throw new Error(`timeline not advancing: cursor=${isoDate(cursor)}, next=${isoDate(nextEventDate)}`);
      }

      const baseRate = payGridGet(inputs.pay_grid, rank, step);
      if (baseRate === null) throw new Error(`No pay defined for (${rank}, step ${step})`);
      const bw = adjustedBiweekly(baseRate, gridEff, cursor, inputs.gwi_rate, gm, gd);
      periods.push({
        start: cursor,
        end: nextEventDate,
        rank,
        step,
        biweekly: bw,
        annual: round2(bw.times(26)),
        event: eventLabel,
      });

      const firing = new Set(candidates.filter(([d]) => compareDates(d, nextEventDate) === 0).map(([, l]) => l));

      if (firing.has("promotion")) {
        const preBw = adjustedBiweekly(payGridGet(inputs.pay_grid, rank, step), gridEff, nextEventDate, inputs.gwi_rate, gm, gd);
        const p = promoQueue.shift();
        rank = p.new_rank;
        const landed = landingStep(rank, preBw, inputs.pay_grid, gridEff, nextEventDate, inputs.gwi_rate, gm, gd);
        step = landed.step;
        if (!landed.ok && warnings) {
          warnings.push(
            `Promotion to ${rank} on ${isoDate(nextEventDate)} violates the 5%-landing rule: ` +
            `no step in ${rank} pays at least 5% above the pre-promotion bi-weekly of $${preBw.toFixed(2)}. ` +
            `The timeline lands at the top step of ${rank}, but the promotion is not allowed under plan rules.`
          );
        }
        stepClock = addYears(nextEventDate, -(step - 1));
        eventLabel = "promotion";
      } else {
        const hasStep = firing.has("step_increase");
        const hasGwi = firing.has("gwi");
        if (hasStep && hasGwi) { step++; eventLabel = "gwi+step"; }
        else if (hasStep) { step++; eventLabel = "step_increase"; }
        else { eventLabel = "gwi"; }
      }

      cursor = nextEventDate;
    }

    if (compareDates(cursor, endDate) < 0) {
      const baseRate = payGridGet(inputs.pay_grid, rank, step);
      if (baseRate === null) throw new Error(`No pay defined for (${rank}, step ${step})`);
      const bw = adjustedBiweekly(baseRate, gridEff, cursor, inputs.gwi_rate, gm, gd);
      periods.push({
        start: cursor,
        end: endDate,
        rank,
        step,
        biweekly: bw,
        annual: round2(bw.times(26)),
        event: eventLabel,
      });
    }

    return periods;
  }

  // ---------- D. Pension (engine_py/pension.py) -------------------------

  function computeYos(start, end) {
    let whole = end.year - start.year;
    if (mdLess(end, start)) whole -= 1;
    const lastAnniv = addYears(start, whole);
    const nextAnniv = addYears(start, whole + 1);
    const period = daysBetween(lastAnniv, nextAnniv);
    const elapsed = daysBetween(lastAnniv, end);
    return round4(new D(whole).plus(new D(elapsed).div(new D(period))));
  }

  function dateOverlapDays(a1, a2, b1, b2) {
    const lo = compareDates(a1, b1) > 0 ? a1 : b1;
    const hi = compareDates(a2, b2) < 0 ? a2 : b2;
    return Math.max(0, daysBetween(lo, hi));
  }

  function buildYearlyEarnings(timeline, serviceStart, serviceEnd) {
    const out = [];
    let k = 0;
    while (true) {
      const winStart = addYears(serviceStart, k);
      let winEnd = addYears(serviceStart, k + 1);
      if (compareDates(winStart, serviceEnd) >= 0) break;
      if (compareDates(winEnd, serviceEnd) > 0) winEnd = serviceEnd;
      const winDays = daysBetween(winStart, winEnd);
      if (winDays <= 0) break;

      let weightedSum = ZERO;
      for (const seg of timeline) {
        const overlap = dateOverlapDays(seg.start, seg.end, winStart, winEnd);
        if (overlap > 0) weightedSum = weightedSum.plus(seg.annual.times(overlap));
      }

      const annualBase = weightedSum.div(new D(winDays));
      out.push({
        year_start: winStart,
        year_end: winEnd,
        annual_base: round2(annualBase),
      });
      k++;
    }
    return out;
  }

  function computeFc3yrAvg(yearly) {
    const n = yearly.length;
    if (n === 0) {
      return { method: "3yr_avg", annual_fc: ZERO, yearly_earnings: [], note: "No earnings data" };
    }
    const window = Math.min(3, n);
    let bestSum = ZERO;
    let bestStart = 0;
    for (let i = 0; i <= n - window; i++) {
      let s = ZERO;
      for (let j = i; j < i + window; j++) s = s.plus(yearly[j].annual_base);
      if (s.gt(bestSum)) { bestSum = s; bestStart = i; }
    }
    const bestYears = yearly.slice(bestStart, bestStart + window);
    return {
      method: "3yr_avg",
      annual_fc: round2(bestSum.div(new D(window))),
      yearly_earnings: bestYears,
      note: `Average of highest ${window} consecutive YOS windows`,
    };
  }

  function computeFcFinal(timeline, serviceEnd) {
    if (timeline.length === 0) {
      return { method: "final", annual_fc: ZERO, yearly_earnings: [], note: "No earnings data" };
    }
    const last = timeline[timeline.length - 1];
    const fc = round2(last.annual);
    return {
      method: "final",
      annual_fc: fc,
      yearly_earnings: [],
      note: `Annualized final pay: ${decStr(last.biweekly)} × 26 = ${decStr(fc)}`,
    };
  }

  function computeBenefitPct(yos) {
    const TIER1_MAX = new D("20");
    const TIER2_MAX = new D("25");
    const TIER1_RATE = new D("0.024");
    const TIER2_RATE = new D("0.030");
    const TIER3_RATE = new D("0.034");
    const CAP = new D("0.80");

    const t1 = D.min(yos, TIER1_MAX);
    const t2 = D.max(ZERO, D.min(yos, TIER2_MAX).minus(TIER1_MAX));
    const t3 = D.max(ZERO, yos.minus(TIER2_MAX));

    const raw = t1.times(TIER1_RATE).plus(t2.times(TIER2_RATE)).plus(t3.times(TIER3_RATE));
    const capped = raw.gte(CAP);
    const final = D.min(raw, CAP);

    return {
      yos,
      tier1_years: round4(t1),
      tier1_pct: round4(t1.times(TIER1_RATE)),
      tier2_years: round4(t2),
      tier2_pct: round4(t2.times(TIER2_RATE)),
      tier3_years: round4(t3),
      tier3_pct: round4(t3.times(TIER3_RATE)),
      raw_pct: round4(raw),
      capped,
      final_pct: round4(final),
    };
  }

  function yosAtCap() { return new D("30"); }

  function computeEarlyReduction(retirementAge) {
    const years = Math.max(0, 57 - retirementAge);
    const reductionPct = round4(new D(years).times(new D("0.07")));
    const factor = round4(new D("1").minus(reductionPct));
    return {
      retirement_age: retirementAge,
      years_before_57: years,
      reduction_pct: reductionPct,
      factor: round4(D.max(ZERO, factor)),
    };
  }

  function projectCola(basePension, colaRate, retirementDate, colaMonth, colaDay, projectToAge, birthDate) {
    const rows = [];

    const candidate = { year: retirementDate.year, month: colaMonth, day: colaDay };
    let nextColaDate = compareDates(candidate, retirementDate) > 0
      ? candidate
      : { year: candidate.year + 1, month: colaMonth, day: colaDay };

    function fullMonths(start, end) {
      let m = (end.year - start.year) * 12 + (end.month - start.month);
      if (end.day < start.day) m -= 1;
      return Math.max(0, m);
    }

    const firstColaMonths = fullMonths(retirementDate, nextColaDate);
    let nextColaFactor = new D(1).plus(colaRate.times(new D(firstColaMonths)).div(TWELVE));
    const fullColaFactor = new D(1).plus(colaRate);

    let age = retirementDate.year - birthDate.year;
    if (mdLess(retirementDate, birthDate)) age -= 1;

    let currentPension = basePension;
    let year = retirementDate.year;
    while (age <= projectToAge) {
      const nextYearStart = { year: year + 1, month: 1, day: 1 };
      while (compareDates(nextColaDate, nextYearStart) < 0) {
        currentPension = round2(currentPension.times(nextColaFactor));
        nextColaDate = { year: nextColaDate.year + 1, month: colaMonth, day: colaDay };
        nextColaFactor = fullColaFactor;
      }
      rows.push({
        age,
        year,
        annual_pension: round2(currentPension),
        monthly_pension: round2(currentPension.div(TWELVE)),
      });
      year++;
      age++;
    }
    return rows;
  }

  // ---------- E. Engine (engine_py/engine.py) ---------------------------

  const MIN_RETIREMENT_AGE = 50;
  const MIN_VESTING_YOS = new D("5");
  const COLA_PROJECT_TO_AGE = 95;

  function birthday(birthDate, age) { return addYears(birthDate, age); }

  function computeRetirementScenario(inputs) {
    const warnings = [];

    const retirementDate = birthday(inputs.birth_date, inputs.retirement_age);

    let serviceEnd, pensionStart, effectiveRetirementAge;
    if (inputs.retirement_type === "deferred_vested") {
      if (!inputs.separation_date || !inputs.pension_start_date) {
        throw new Error("separation_date and pension_start_date required for deferred_vested");
      }
      serviceEnd = inputs.separation_date;
      pensionStart = inputs.pension_start_date;
      let psAge = pensionStart.year - inputs.birth_date.year;
      if (mdLess(pensionStart, inputs.birth_date)) psAge -= 1;
      effectiveRetirementAge = psAge;
    } else {
      serviceEnd = retirementDate;
      pensionStart = retirementDate;
      effectiveRetirementAge = inputs.retirement_age;
    }

    if (effectiveRetirementAge < MIN_RETIREMENT_AGE) {
      warnings.push(`Retirement age ${effectiveRetirementAge} is below the minimum age of ${MIN_RETIREMENT_AGE}.`);
    }

    const timeline = buildSalaryTimeline(inputs, serviceEnd, warnings);
    const finalPeriod = timeline.length > 0 ? timeline[timeline.length - 1] : null;
    const finalRank = finalPeriod ? finalPeriod.rank : inputs.current_rank;
    const finalStep = finalPeriod ? finalPeriod.step : inputs.current_step;

    const yos = computeYos(inputs.hire_date, serviceEnd);
    if (yos.lt(MIN_VESTING_YOS)) {
      const noun = inputs.retirement_type === "deferred_vested" ? "separation" : "retirement";
      warnings.push(`Not vested: ${decStr(yos)} YOS at ${noun} (minimum 5 required).`);
    }

    const yearly = buildYearlyEarnings(timeline, inputs.hire_date, serviceEnd);
    const fc3yr = computeFc3yrAvg(yearly);
    const fcFinal = computeFcFinal(timeline, serviceEnd);

    const benefitDetail = computeBenefitPct(yos);

    const capYos = yosAtCap();
    const capReached = yos.gte(capYos);
    const capDate = capReached ? addYears(inputs.hire_date, 30) : null;

    const earlyReduction = computeEarlyReduction(effectiveRetirementAge);

    function pension(fc) {
      if (warnings.length > 0) return ZERO;
      return fc.times(benefitDetail.final_pct).times(earlyReduction.factor);
    }

    let annual3yr = pension(fc3yr.annual_fc);
    let monthly3yr = annual3yr.div(TWELVE);
    let annualFinal = pension(fcFinal.annual_fc);
    let monthlyFinal = annualFinal.div(TWELVE);

    annual3yr = round2(annual3yr);
    monthly3yr = round2(monthly3yr);
    annualFinal = round2(annualFinal);
    monthlyFinal = round2(monthlyFinal);

    const [cm, cd] = inputs.cola_effective_month_day;
    let colaRows3yr = [];
    let colaRowsFinal = [];
    if (inputs.show_cola && warnings.length === 0) {
      colaRows3yr = projectCola(annual3yr, inputs.cola_rate, pensionStart, cm, cd, COLA_PROJECT_TO_AGE, inputs.birth_date);
      colaRowsFinal = projectCola(annualFinal, inputs.cola_rate, pensionStart, cm, cd, COLA_PROJECT_TO_AGE, inputs.birth_date);
    }

    return {
      inputs,
      retirement_date: retirementDate,
      separation_date: inputs.separation_date || null,
      yos_at_retirement: yos,
      final_rank: finalRank,
      final_step: finalStep,
      cap_reached: capReached,
      cap_date: capDate,
      fc_3yr: fc3yr,
      fc_final: fcFinal,
      benefit_pct_detail: benefitDetail,
      early_reduction: earlyReduction,
      annual_pension_3yr: annual3yr,
      monthly_pension_3yr: monthly3yr,
      annual_pension_final: annualFinal,
      monthly_pension_final: monthlyFinal,
      cola_rows_3yr: colaRows3yr,
      cola_rows_final: colaRowsFinal,
      salary_timeline: timeline,
      warnings,
    };
  }

  // ---------- F. Defaults (engine_py/defaults.py) ----------------------

  const FIREFIGHTER_RECRUIT = "Firefighter Recruit";
  const FIREFIGHTER = "Firefighter";
  const FIRE_ENGINEER = "Fire Engineer";
  const FIRE_PREVENTION_INSPECTOR = "Fire Prevention Inspector";
  const ARSON_INVESTIGATOR = "Arson Investigator";
  const FIRE_CAPTAIN = "Fire Captain";
  const BATTALION_CHIEF = "Battalion Chief";

  const _RATES = [
    [FIREFIGHTER_RECRUIT, 1, "4148.72"],
    [FIREFIGHTER, 1, "4769.02"], [FIREFIGHTER, 2, "4998.58"], [FIREFIGHTER, 3, "5239.87"],
    [FIREFIGHTER, 4, "5494.83"], [FIREFIGHTER, 5, "5760.53"], [FIREFIGHTER, 6, "6036.98"],
    [FIREFIGHTER, 7, "6343.70"],
    [FIRE_ENGINEER, 1, "5816.21"], [FIRE_ENGINEER, 2, "6097.55"], [FIRE_ENGINEER, 3, "6391.58"],
    [FIRE_ENGINEER, 4, "6707.11"], [FIRE_ENGINEER, 5, "7041.59"],
    [FIRE_PREVENTION_INSPECTOR, 1, "6097.55"], [FIRE_PREVENTION_INSPECTOR, 2, "6391.58"],
    [FIRE_PREVENTION_INSPECTOR, 3, "6707.11"], [FIRE_PREVENTION_INSPECTOR, 4, "7033.38"],
    [FIRE_PREVENTION_INSPECTOR, 5, "7384.54"],
    [ARSON_INVESTIGATOR, 1, "6360.32"], [ARSON_INVESTIGATOR, 2, "6669.01"],
    [ARSON_INVESTIGATOR, 3, "6995.28"], [ARSON_INVESTIGATOR, 4, "7335.23"],
    [ARSON_INVESTIGATOR, 5, "7702.60"],
    [FIRE_CAPTAIN, 1, "6669.01"], [FIRE_CAPTAIN, 2, "6995.28"], [FIRE_CAPTAIN, 3, "7335.23"],
    [FIRE_CAPTAIN, 4, "7693.73"], [FIRE_CAPTAIN, 5, "8079.66"],
    [BATTALION_CHIEF, 1, "8304.27"], [BATTALION_CHIEF, 2, "8713.57"],
    [BATTALION_CHIEF, 3, "9138.51"], [BATTALION_CHIEF, 4, "9590.79"],
    [BATTALION_CHIEF, 5, "10071.00"],
  ];

  function buildDefaultPayGrid() {
    const rates = new Map();
    for (const [r, s, v] of _RATES) rates.set(`${r}|${s}`, new D(v));
    return { rates };
  }

  const FY2627_PAY_GRID = buildDefaultPayGrid();
  const FY2627_EFFECTIVE_DATE = { year: 2026, month: 7, day: 1 };
  const DEFAULT_GWI_RATE = new D("0.035");
  const DEFAULT_COLA_RATE = new D("0.020");

  // ---------- G. Serialization (engine_py/_serialize.py) ----------------

  function toJsonable(obj) {
    if (obj === null || obj === undefined) return obj;
    if (obj instanceof D) {
      return obj._dp !== undefined ? obj.toFixed(obj._dp) : obj.toString();
    }
    if (typeof obj === "object" && "year" in obj && "month" in obj && "day" in obj && Object.keys(obj).length === 3) {
      return isoDate(obj);
    }
    if (obj instanceof Map) {
      const out = {};
      const keys = Array.from(obj.keys()).sort();
      for (const k of keys) out[String(k)] = toJsonable(obj.get(k));
      return out;
    }
    if (Array.isArray(obj)) return obj.map(toJsonable);
    if (typeof obj === "object") {
      const out = {};
      for (const k of Object.keys(obj)) out[k] = toJsonable(obj[k]);
      return out;
    }
    return obj;
  }

  // Rehydrate fixture JSON (strings/arrays) back into {Decimal, date, Map} shapes
  // for feeding into computeRetirementScenario.
  function hydrateInputs(raw) {
    const pgRates = new Map();
    for (const k of Object.keys(raw.pay_grid.rates)) {
      pgRates.set(k, decFromStr(raw.pay_grid.rates[k]));
    }
    return {
      birth_date: parseIsoDate(raw.birth_date),
      hire_date: parseIsoDate(raw.hire_date),
      current_rank: raw.current_rank,
      current_step: raw.current_step,
      current_step_arrival_date: parseIsoDate(raw.current_step_arrival_date),
      pay_grid: { rates: pgRates },
      pay_grid_effective_date: parseIsoDate(raw.pay_grid_effective_date),
      gwi_rate: decFromStr(raw.gwi_rate),
      cola_rate: decFromStr(raw.cola_rate),
      gwi_effective_month_day: raw.gwi_effective_month_day,
      cola_effective_month_day: raw.cola_effective_month_day,
      retirement_age: raw.retirement_age,
      promotions: (raw.promotions || []).map((p) => ({
        new_rank: p.new_rank,
        effective_date: parseIsoDate(p.effective_date),
      })),
      retirement_type: raw.retirement_type,
      separation_date: raw.separation_date ? parseIsoDate(raw.separation_date) : null,
      pension_start_date: raw.pension_start_date ? parseIsoDate(raw.pension_start_date) : null,
      show_cola: raw.show_cola,
      as_of_date: parseIsoDate(raw.as_of_date),
    };
  }

  // ---------- H. Namespace export --------------------------------------

  global.firecalc = {
    // Core
    computeRetirementScenario,
    // Building blocks
    buildSalaryTimeline, buildYearlyEarnings,
    computeYos, computeFc3yrAvg, computeFcFinal,
    computeBenefitPct, computeEarlyReduction, projectCola, yosAtCap,
    adjustedBiweekly, landingStep,
    // Dates
    parseIsoDate, isoDate, addYears, compareDates, daysBetween,
    // Models
    payGridGet, payGridMaxStep, buildDefaultPayGrid,
    // Defaults
    FY2627_PAY_GRID, FY2627_EFFECTIVE_DATE, DEFAULT_GWI_RATE, DEFAULT_COLA_RATE,
    // Serialization
    toJsonable, hydrateInputs,
    // Constants for UI
    RANK_ORDER,
  };
})(typeof window !== "undefined" ? window : globalThis);
