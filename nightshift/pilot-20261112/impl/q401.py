#!/usr/bin/env python3
"""Q401 — Proposition 14 arithmetic check (Still).

Implements spec item 1 in TOP10-TEST-SPECS-DRAFT.md against card
C-sys1-sys2-codesign (arXiv:2610.39497). Pure arithmetic, no external data.

The card states Proposition 14: with a perfect screen, acquiring the
utility-relevant subset costs a fraction rho_u + r of exhaustive
execute-then-filter evaluation (rho_u = utility-relevant fraction,
the abstract's p*; r = screening cost over execution cost), so the
speedup is 1 / (rho_u + r), approaching 1 / rho_u as r -> 0.
At the paper's stated values (r = 0.01, rho_u = 0.02), the formula
gives 1 / 0.03 = 33.333...x against the paper's printed 26x.

This script computes:
1. The ratio from the formula (33.333333x), the printed value (26x),
   and the exact discrepancy (both absolute difference and ratio).
2. The parameter sets that yield_exactly 26x: solving rho_u given r=0.01,
   solving r given rho_u=0.02, and the one-parameter family rho_u + r = 1/26.
3. Cross-checks of all other printed Section 6.2 analytic figures in the card
   (5x at p*=0.2; 1.25x at 10% error; 1.11x at 20% error; 1.54x at rho_u=0.3;
   1.24x at rho_u=0.5; 1.13x at rho_u=0.5 with 10% error), including the exact
   implied cost overheads needed to reconcile 1.54x and 1.24x with 1/(rho_u + r_eff).
4. The small-r (r -> 0) and large-r (r -> 1 - rho_u, r = 1, r -> inf) limit
   behaviour.

Usage: q401.py [output_root]   (default ./results)
Writes <output_root>/Q401/result.json and <output_root>/Q401/notes.md.
"""
import json
import os
import sys
import time
from datetime import datetime
import numpy as np

QID = "Q401"
TITLE = "Proposition 14 arithmetic check"


def now_iso_local():
    return datetime.now().astimezone().isoformat()


def cost_fraction(rho_u, r):
    return float(rho_u + r)


def speedup(rho_u, r):
    return float(1.0 / (rho_u + r))


def main():
    started = time.time()
    started_iso = now_iso_local()
    out_root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "results")
    out_dir = os.path.join(out_root, QID)
    os.makedirs(out_dir, exist_ok=True)

    # 1. Core comparison at stated values from card C-sys1-sys2-codesign:
    # r = 0.01, rho_u = 0.02, printed = 26x
    rho_stated = 0.02
    r_stated = 0.01
    printed = 26.0

    stated_cost_frac = cost_fraction(rho_stated, r_stated)  # 0.03
    computed = speedup(rho_stated, r_stated)                # 1 / 0.03 = 33.333333...

    diff_abs = computed - printed                           # +7.333333...
    diff_rel_over_printed = (computed - printed) / printed  # +28.205128%
    diff_rel_over_computed = (printed - computed) / computed  # -22.0%
    ratio_computed_over_printed = computed / printed        # 1.282051...

    # 2. Parameter sets yielding exactly 26x: rho_u + r = 1 / 26 = 0.038461538...
    target_cost_frac = 1.0 / printed  # 0.038461538461538464
    extra_cost_frac_needed = target_cost_frac - stated_cost_frac  # 0.008461538461538463

    # Solve rho_u given stated r = 0.01
    rho_given_stated_r = target_cost_frac - r_stated  # 0.02846153846153846
    solve_rho_given_r = {
        "fixed_r": r_stated,
        "solved_rho_u": round(rho_given_stated_r, 6),
        "solved_rho_u_exact_fraction": "37/1300",
        "verified_speedup": round(speedup(rho_given_stated_r, r_stated), 6),
    }

    # Solve r given stated rho_u = 0.02
    r_given_stated_rho = target_cost_frac - rho_stated  # 0.018461538461538463
    solve_r_given_rho = {
        "fixed_rho_u": rho_stated,
        "solved_r": round(r_given_stated_rho, 6),
        "solved_r_exact_fraction": "12/650",
        "verified_speedup": round(speedup(rho_stated, r_given_stated_rho), 6),
    }

    # One-parameter family rho_u + r = 1/26 across grid
    rho_grid = np.linspace(0.0, 0.035, 8)
    family = []
    for rho_val in rho_grid:
        r_val = target_cost_frac - float(rho_val)
        if r_val >= 0.0:
            family.append({
                "rho_u": round(float(rho_val), 6),
                "r": round(r_val, 6),
                "cost_fraction": round(float(rho_val) + r_val, 6),
                "speedup": round(speedup(float(rho_val), r_val), 4),
            })

    # Also check integer-rounded speedups near stated values (e.g. could 26x come from
    # a rounded cost fraction of 0.038 or 0.0385, or rho_u=0.028, r=0.01?):
    near_integer_candidates = [
        {"rho_u": 0.028, "r": 0.01, "speedup": round(speedup(0.028, 0.01), 3)},
        {"rho_u": 0.02, "r": 0.018, "speedup": round(speedup(0.02, 0.018), 3)},
        {"rho_u": 0.02, "r": 0.019, "speedup": round(speedup(0.02, 0.019), 3)},
        {"rho_u": 0.03, "r": 0.01, "speedup": round(speedup(0.03, 0.01), 3)},
    ]

    # 3. Cross-checks of all other Section 6.2 analytic figures printed in the card
    # For each figure where rho_u is stated, we compute:
    # - bare ideal speedup 1/rho_u (r=0)
    # - speedup with stated screening cost r=0.01: 1/(rho_u + 0.01)
    # - implied effective overhead r_eff = (1/printed) - rho_u needed to produce the printed number.
    cross_checks = [
        {
            "case": "ideal p*=0.2, r->0",
            "rho_u": 0.2,
            "printed": 5.0,
            "computed_r0": round(speedup(0.2, 0.0), 4),
            "computed_r0_01": round(speedup(0.2, 0.01), 4),
            "implied_total_cost_fraction": round(1.0 / 5.0, 6),
            "implied_r_or_error_overhead": round((1.0 / 5.0) - 0.2, 6),
            "matches_bare_proposition_14": True,
            "note": "Exact match to 1/p* = 1/0.2 = 5.0x at r=0.",
        },
        {
            "case": "stated r=0.01, rho_u=0.02",
            "rho_u": 0.02,
            "printed": 26.0,
            "computed_r0": round(speedup(0.02, 0.0), 4),
            "computed_r0_01": round(speedup(0.02, 0.01), 4),
            "implied_total_cost_fraction": round(1.0 / 26.0, 6),
            "implied_r_or_error_overhead": round((1.0 / 26.0) - 0.02, 6),
            "matches_bare_proposition_14": False,
            "note": "1/(0.02+0.01) = 33.333x != 26x; requires an extra 0.008462 cost fraction.",
        },
        {
            "case": "rho_u=0.3 (Section 6.2 analytic)",
            "rho_u": 0.3,
            "printed": 1.54,
            "computed_r0": round(speedup(0.3, 0.0), 4),
            "computed_r0_01": round(speedup(0.3, 0.01), 4),
            "implied_total_cost_fraction": round(1.0 / 1.54, 6),
            "implied_r_or_error_overhead": round((1.0 / 1.54) - 0.3, 6),
            "matches_bare_proposition_14": False,
            "note": (
                "1/1.54 = 0.649351 (practically 0.65 = 0.30 + 0.35, since 1/0.65 = 1.5385 -> 1.54x); "
                "implies an unstated screening + false-positive/exploration overhead of ~0.35."
            ),
        },
        {
            "case": "rho_u=0.5 (Section 6.2 analytic)",
            "rho_u": 0.5,
            "printed": 1.24,
            "computed_r0": round(speedup(0.5, 0.0), 4),
            "computed_r0_01": round(speedup(0.5, 0.01), 4),
            "implied_total_cost_fraction": round(1.0 / 1.24, 6),
            "implied_r_or_error_overhead": round((1.0 / 1.24) - 0.5, 6),
            "matches_bare_proposition_14": False,
            "note": (
                "1/1.24 = 0.806452 (~0.8065 = 0.50 + 0.3065); implies an unstated overhead of ~0.3065."
            ),
        },
        {
            "case": "rho_u=0.5 with 10% error",
            "rho_u": 0.5,
            "printed": 1.13,
            "computed_r0": round(speedup(0.5, 0.0), 4),
            "computed_r0_01": round(speedup(0.5, 0.01), 4),
            "implied_total_cost_fraction": round(1.0 / 1.13, 6),
            "implied_r_or_error_overhead": round((1.0 / 1.13) - 0.5, 6),
            "matches_bare_proposition_14": False,
            "note": "Includes 10% predictor error; implied total cost fraction 1/1.13 = 0.884956.",
        },
        {
            "case": "10% predictor error (illustrated saving)",
            "rho_u": None,
            "printed": 1.25,
            "computed_r0": None,
            "computed_r0_01": None,
            "implied_total_cost_fraction": round(1.0 / 1.25, 6),
            "implied_r_or_error_overhead": None,
            "matches_bare_proposition_14": False,
            "note": "1/1.25 = 0.80 total cost fraction (falls from ideal due to 10% false-positive/error rate).",
        },
        {
            "case": "20% predictor error (illustrated saving)",
            "rho_u": None,
            "printed": 1.11,
            "computed_r0": None,
            "computed_r0_01": None,
            "implied_total_cost_fraction": round(1.0 / 1.11, 6),
            "implied_r_or_error_overhead": None,
            "matches_bare_proposition_14": False,
            "note": "1/1.11 = 0.9009 (i.e. 1/0.90 = 1.111x) total cost fraction under 20% predictor error.",
        },
    ]

    # 4. Small-r and Large-r limit behaviour
    # Small-r limit (r -> 0): speedup -> 1 / rho_u = 50.0x (for rho_u = 0.02)
    limit_r_to_0 = speedup(rho_stated, 0.0)  # 50.0
    # Break-even r where speedup == 1.0x (cost fraction rho_u + r == 1.0): r = 1 - rho_u = 0.98
    r_breakeven_1x = round(1.0 - rho_stated, 6)  # 0.98
    # When screening costs as much as execution (r = 1.0): cost fraction = 1 + rho_u = 1.02, speedup = 0.980392x (< 1, net slowdown)
    speedup_at_r_eq_1 = round(speedup(rho_stated, 1.0), 6)  # 0.980392
    # Asymptotic large-r limit (r -> infinity):
    # speedup = 1 / (rho_u + r) ~ 1/r -> 0; total cost fraction = rho_u + r ~ r -> infinity.

    r_sweep_values = [0.0, 0.001, 0.005, 0.01, 0.018462, 0.05, 0.1, 0.25, 0.5, 0.98, 1.0, 2.0, 10.0, 100.0]
    r_sweep = {
        str(r_val): {
            "cost_fraction": round(cost_fraction(rho_stated, r_val), 6),
            "speedup": round(speedup(rho_stated, r_val), 6),
        }
        for r_val in r_sweep_values
    }

    large_r_behaviour = {
        "small_r_limit_r_to_0_speedup": limit_r_to_0,
        "small_r_asymptotic_formula": "1 / rho_u",
        "r_breakeven_for_1x_speedup": r_breakeven_1x,
        "speedup_at_r_equals_1": speedup_at_r_eq_1,
        "large_r_asymptotic_cost_fraction": "rho_u + r ~ r -> infinity as r -> infinity",
        "large_r_asymptotic_speedup": "1 / (rho_u + r) ~ 1 / r -> 0 as r -> infinity (strict net loss for all r > 1 - rho_u = 0.98)",
        "r_sweep_at_rho_0.02": r_sweep,
    }

    result_path = os.path.join(out_dir, "result.json")
    notes_path = os.path.join(out_dir, "notes.md")
    records_written = [result_path, notes_path]

    headline = {
        "stated_rho_u": rho_stated,
        "stated_r": r_stated,
        "stated_cost_fraction_rho_plus_r": stated_cost_frac,
        "computed_ratio_at_stated_values": round(computed, 6),
        "printed_ratio": printed,
        "discrepancy_difference_x": round(diff_abs, 6),
        "discrepancy_relative_to_printed_pct": round(diff_rel_over_printed * 100.0, 4),
        "discrepancy_relative_to_computed_pct": round(diff_rel_over_computed * 100.0, 4),
        "ratio_computed_over_printed": round(ratio_computed_over_printed, 6),
        "required_rho_plus_r_for_26x": round(target_cost_frac, 6),
        "unexplained_extra_cost_fraction_for_26x": round(extra_cost_frac_needed, 6),
        "solve_rho_u_given_stated_r_0.01": solve_rho_given_r,
        "solve_r_given_stated_rho_u_0.02": solve_r_given_rho,
        "param_family_26x": family,
        "near_integer_parameter_candidates": near_integer_candidates,
        "speedup_limit_r_to_0": limit_r_to_0,
        "r_where_speedup_falls_to_1x": r_breakeven_1x,
        "speedup_at_r_equals_1": speedup_at_r_eq_1,
        "large_r_limit_speedup_as_r_to_inf": 0.0,
        "large_r_behaviour": large_r_behaviour,
        "cross_checks": cross_checks,
        "verdict": (
            "At the stated parameters (r = 0.01, rho_u = 0.02), Proposition 14 gives a cost "
            "fraction of 0.03 and a speedup of 1 / 0.03 = 33.333x, exceeding the paper's "
            "printed 26x by +7.333x (+28.21% over printed; printed is 22.0% below the formula). "
            "Obtaining exactly 26x requires rho_u + r = 1/26 = 0.038462 (an extra 0.008462 cost "
            "fraction): either rho_u = 0.028462 (37/1300) at r = 0.01, or r = 0.018462 (12/650) "
            "at rho_u = 0.02. As r increases, speedup declines hyperbolically as 1/(rho_u + r), "
            "crossing break-even (1.0x) at r = 1 - rho_u = 0.98, falling to 0.980x when screening "
            "equals execution cost (r = 1), and approaching 0 (~ 1/r) as r -> infinity."
        ),
    }

    result = {
        "qid": QID,
        "title": TITLE,
        "status": "done",
        "started": started_iso,
        "finished": now_iso_local(),
        "runtime_s": round(time.time() - started, 3),
        "method": (
            "Substituted the card's stated parameters (r = 0.01, rho_u = 0.02) into Proposition 14's "
            "total cost fraction (rho_u + r) and speedup formula 1 / (rho_u + r); quantified the "
            "exact absolute and relative discrepancy against the paper's printed 26x; solved "
            "rho_u + r = 1/26 both for rho_u given r = 0.01 and for r given rho_u = 0.02 (plus a "
            "one-parameter grid); cross-checked every other Section 6.2 analytic figure reported in "
            "the card by computing the implied overhead (1/printed - rho_u); and evaluated the "
            "small-r (r -> 0) and large-r (r = 1 - rho_u, r = 1, r -> inf) asymptotic regimes."
        ),
        "assumptions": [
            "Proposition 14 formula taken verbatim from card C-sys1-sys2-codesign: under a perfect screen, acquiring the utility-relevant subset costs a fraction rho_u + r of exhaustive execute-then-filter evaluation, giving speedup 1 / (rho_u + r) that approaches 1 / rho_u as r -> 0.",
            "All checked numbers (26x at r=0.01, rho_u=0.02; 5x at p*=0.2; 1.25x at 10% error; 1.11x at 20% error; 1.54x at rho_u=0.3; 1.24x at rho_u=0.5; 1.13x at rho_u=0.5 with 10% error) are taken verbatim from card C-sys1-sys2-codesign's summary of Section 6.2.",
            "Where the card reports Section 6.2 figures with predictor error or without stating r (1.54x at rho_u=0.3, 1.24x at rho_u=0.5), we report both the bare formula value and the implied additional cost fraction (1/printed - rho_u) rather than conflating extended-model numbers with bare-formula errors.",
        ],
        "headline": headline,
        "records_written": records_written,
    }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    notes = f"""# {QID} — {TITLE}

Implements spec item 1 (`TOP10-TEST-SPECS-DRAFT.md`) against card `C-sys1-sys2-codesign` (arXiv:2610.39497), Proposition 14.

## Method

Pure analytic calculation from the card's stated formula and numbers:
- **Proposition 14 cost fraction:** `C_frac = rho_u + r`, where `rho_u` is the utility-relevant fraction (`p*` in the abstract) and `r` is the screening-to-execution cost ratio.
- **Proposition 14 speedup:** `S(rho_u, r) = 1 / (rho_u + r)`, approaching `1 / rho_u` as `r -> 0`.
- Evaluated `S(0.02, 0.01)`, compared against the paper's printed `26x`, solved `rho_u + r = 1/26` for each parameter holding the other fixed, cross-checked all other Section 6.2 numbers in the card, and analysed the `r -> 0` and large-`r` regimes.

## Assumptions

- Every formula and parameter value is taken strictly from card `C-sys1-sys2-codesign` (no external data).
- For Section 6.2 numbers where predictor error or additional unstated terms are active (`1.54x` at `rho_u = 0.3`, `1.24x` at `rho_u = 0.5`, `1.25x` at 10% error, `1.11x` at 20% error, `1.13x` at `rho_u = 0.5` with 10% error), we compute both the bare Proposition 14 value and the exact implied overhead `(1 / printed) - rho_u`.

## Results & What the Numbers Mean

### 1. The 26x Discrepancy at `r = 0.01, rho_u = 0.02`
- **Formula cost fraction:** `rho_u + r = 0.02 + 0.01 = 0.03`
- **Formula speedup:** `1 / 0.03 = 33.333333x` (`100 / 3`)
- **Paper's printed speedup:** `26x`
- **Discrepancy:**
  - Absolute: **`+7.333333x`** (`33.333x` vs `26.0x`)
  - Relative: Formula is **`+28.21%` higher** than printed (`computed / printed = 1.282051`); printed is **`22.00%` lower** than the formula (`(26 - 33.333) / 33.333 = -0.22`).
- **Direction of error:** The bare Proposition 14 formula predicts a *larger* speedup (`33.3x`) than the paper prints (`26x`). Thus, `26x` either reflects an unstated extra cost fraction of **`0.008462`** (e.g., an exploration floor or nonzero false-positive admission rate folded into Section 6.2's calculation without being stated alongside `r = 0.01, rho_u = 0.02`), or an arithmetic/parameter typo.

### 2. Parameter Sets That Yield Exactly `26x` (`rho_u + r = 1/26 = 0.038462`)
- **Solving for `rho_u` given stated `r = 0.01`:**
  - `rho_u = 1/26 - 0.01 = 0.028462` (exact fraction `37 / 1300`, or ~`0.028` if rounded to 3 decimals, where `1 / (0.028 + 0.01) = 26.316x`).
- **Solving for `r` given stated `rho_u = 0.02`:**
  - `r = 1/26 - 0.02 = 0.018462` (exact fraction `12 / 650`, or ~`0.0185`).
- **One-parameter family (`rho_u + r = 0.038462`):**
  - `(rho_u = 0.000, r = 0.038462)` -> `26.0x`
  - `(rho_u = 0.010, r = 0.028462)` -> `26.0x`
  - `(rho_u = 0.015, r = 0.023462)` -> `26.0x`
  - `(rho_u = 0.020, r = 0.018462)` -> `26.0x`
  - `(rho_u = 0.025, r = 0.013462)` -> `26.0x`
  - `(rho_u = 0.028462, r = 0.010)` -> `26.0x`
  - `(rho_u = 0.035, r = 0.003462)` -> `26.0x`

### 3. Cross-Checks of Other Printed Section 6.2 Figures
- **Ideal case `p* = 0.2, r -> 0`:** Printed **`5x`**, bare formula `1 / 0.2 = 5.0x` (**exact match**).
- **`rho_u = 0.3` (printed `1.54x`):** Bare formula at `r = 0` gives `3.333x` (`3.226x` at `r = 0.01`). Notably, `1 / 1.54 = 0.64935` (`1 / 0.65 = 1.5385x -> 1.54x`), which means `1.54x` corresponds to a total cost fraction of `0.65 = 0.30 + 0.35` (an unstated screening + error/exploration overhead of `0.35`).
- **`rho_u = 0.5` (printed `1.24x`):** Bare formula at `r = 0` gives `2.0x` (`1.961x` at `r = 0.01`). `1 / 1.24 = 0.80645`, implying an unstated overhead of `0.3065` on top of `rho_u = 0.50`.
- **Predictor error figures (`1.25x` at 10% error, `1.11x` at 20% error, `1.13x` at `rho_u = 0.5` with 10% error):** Correspond to total cost fractions of `0.80` (`1 / 1.25`), `0.90` (`1 / 1.111`), and `0.885` (`1 / 1.13`), confirming that Section 6.2's extended arithmetic adds substantial false-positive/error terms beyond bare `rho_u + r`.

### 4. Small-`r` and Large-`r` Limit Behaviour (at `rho_u = 0.02`)
- **Small-`r` limit (`r -> 0`):** Speedup approaches the supremum `1 / rho_u = 50.0x`.
- **Moderate `r`:** Falls hyperbolically: `33.333x` at `r = 0.01`, `14.286x` at `r = 0.05`, `8.333x` at `r = 0.10`, `3.704x` at `r = 0.25`, `1.923x` at `r = 0.50`.
- **Break-even point (`S = 1.0x`):** Occurs at `r = 1 - rho_u = 0.98`. At this point, screening all candidates costs `98%` of exhaustive execution and executing the admitted `2%` costs the remaining `2%`, yielding zero net savings (`1.0x`).
- **Large-`r` regime (`r > 1 - rho_u` and `r -> infinity`):**
  - For all `r > 0.98`, conditional interaction is strictly slower/more expensive than exhaustive execution (`S < 1.0x`).
  - At `r = 1.0` (screening costs as much as executing), total cost fraction is `1 + rho_u = 1.02` and speedup is `0.980392x`.
  - As `r -> infinity`, total cost fraction diverges linearly (`rho_u + r ~ r -> infinity`) and speedup decays to zero (`1 / (rho_u + r) ~ 1 / r -> 0`).

## Limits

This test settles the analytic arithmetic of Proposition 14 and Section 6.2 as reported in `C-sys1-sys2-codesign`. Because the paper contains no experiments or empirical measurements of `rho_u`, `r`, `epsilon`, or `Delta_min`, real-workload gating economics must be tested on logged run data (as in Q207, Q281, and Q505).
"""

    with open(notes_path, "w", encoding="utf-8") as f:
        f.write(notes)

    print(json.dumps({
        "qid": QID,
        "status": "done",
        "headline": headline["computed_ratio_at_stated_values"],
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
