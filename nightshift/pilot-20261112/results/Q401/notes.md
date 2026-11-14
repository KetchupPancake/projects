# Q401 — Proposition 14 arithmetic check

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
