# Q505 — Cost prediction under verification and retries

Implements spec item 5 (TOP10-TEST-SPECS-DRAFT.md) against card
C-scout-before-you-route. Data: `data/routing/job-usage-log.jsonl`
(shared with Q281).

## Headline

**Cost-under-retries drops ≥20% at some tier: YES**
at tier K=1, source=job_family_quota_5h_pp, p90 drop 50.0% vs unconstrained logged retries.

Outcome is **log status**, not quality. Same mandatory limit as Q281.

## Data profile (computed)

- 13003 records, 2026-10-15T22:06:00-06:00 → 2026-11-09T17:10:59-06:00.
- 11767 rows with status; 523 job
  runs with `start`; 412 with a non-negative
  5h quota delta; **3** with an
  explicit `attempt`/`retried` field (the glm-4.7-flash triple).
- `verified_correct` non-null: 0.
- Positive `cost_usd`: 762 (almost none of
  the status-bearing retry chains).
- Status mix: {"auth": 103, "capacity": 35, "disabled": 1, "empty": 694, "error": 583, "fail": 8, "invalid_output": 22, "ok": 6552, "ratelimit": 2292, "refused": 857, "timeout": 357, "truncated": 263}.

Retries are reconstructed. CHECKS.md said "retries by repeated job
records"; the log does not carry a retry id, so two reconstructions
run in parallel.

## Method

1. **Call-level chains.** Sort status-bearing rows by time. A run is a
   streak of the same `(model, provider, task_type)` with successive
   gaps ≤ 60s, extended only while the previous attempt
   was not `ok` (fail-then-retry; a success ends the run).
   9737 chains, of which
   810 have length ≥2.
   Resource: attempt count (primary) and `latency_s`. Early-stop at
   first `status=ok`.
2. **Job-title families.** Job runs with `start`, grouped by a stem
   that strips version/round/review tokens and keeps gui-plan variants
   distinct. 250 families, 97 with ≥2 attempts.
   Resource: 5h quota delta in percentage points. Negative deltas
   (quota resets) dropped.
3. Replay each run at K=[1, 2, 3, 4, 5, 8, 10] and unconstrained. A budget never
   invents attempts the log did not record.
4. **Predictor in the loop** (spec). First-attempt logistic P(ok |
   model, task_type) on the earliest 70% of chains; on the later 30%,
   compare K=3 replay of every chain against K=3 replay that skips
   chains with predicted P(ok) below 0.3 / 0.5 / 0.7.
5. Variance share: later-slice attempts-used OLS-R² on verifier
   accepted vs on predicted P(ok).

## Call-chain attempt tiers

| tier | n | accepted | outcome_rate | median attempts | p90 | cost/accepted |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 9737 | 6322 | 0.6493 | 1.0 | 1.0 | 1.5402 |
| 2 | 9737 | 6523 | 0.6699 | 1.0 | 1.0 | 1.6169 |
| 3 | 9737 | 6537 | 0.6714 | 1.0 | 1.0 | 1.6552 |
| 4 | 9737 | 6546 | 0.6723 | 1.0 | 1.0 | 1.6803 |
| 5 | 9737 | 6546 | 0.6723 | 1.0 | 1.0 | 1.702 |
| 8 | 9737 | 6551 | 0.6728 | 1.0 | 1.0 | 1.746 |
| 10 | 9737 | 6551 | 0.6728 | 1.0 | 1.0 | 1.7613 |
| unconstrained | 9737 | 6551 | 0.6728 | 1.0 | 1.0 | 1.7961 |

Among chains that actually retried (unconstrained length ≥2):

| tier | n | accepted | outcome_rate | median attempts | p90 | cost/accepted |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 810 | 0 | 0.0 | 1.0 | 1.0 | None |
| 2 | 810 | 201 | 0.2481 | 2.0 | 2.0 | 8.0597 |
| 3 | 810 | 215 | 0.2654 | 2.0 | 3.0 | 8.8047 |
| 4 | 810 | 224 | 0.2765 | 2.0 | 4.0 | 9.25 |
| 5 | 810 | 224 | 0.2765 | 2.0 | 5.0 | 9.8839 |
| 8 | 810 | 229 | 0.2827 | 2.0 | 7.0 | 10.9651 |
| 10 | 810 | 229 | 0.2827 | 2.0 | 7.0 | 11.4017 |
| unconstrained | 810 | 229 | 0.2827 | 2.0 | 7.0 | 12.3974 |

p90-vs-unconstrained (all chains): NO
(drop 0.0%).
Among chains with unconstrained length ≥2 (the ones that actually
retried): YES at
K=5 (drop 28.57%).
Cost-per-accepted vs K=1 (all chains): NO
(drop -4.98%).

## Job-family 5h quota tiers (families with ≥2 attempts)

| tier | n | accepted | outcome_rate | median 5h pp | p90 | cost/accepted |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 97 | 19 | 0.1959 | 2.0 | 23.0 | 41.4211 |
| 2 | 97 | 19 | 0.1959 | 5.0 | 39.8 | 67.5263 |
| 3 | 97 | 19 | 0.1959 | 5.0 | 43.4 | 81.6842 |
| 4 | 97 | 19 | 0.1959 | 5.0 | 43.4 | 85.3158 |
| 5 | 97 | 19 | 0.1959 | 5.0 | 43.4 | 86.7368 |
| 8 | 97 | 19 | 0.1959 | 5.0 | 46.0 | 89.0 |
| 10 | 97 | 19 | 0.1959 | 5.0 | 46.0 | 90.1053 |
| unconstrained | 97 | 19 | 0.1959 | 5.0 | 46.0 | 90.4737 |

p90-vs-unconstrained: drops≥20%=True at
K=1 (drop 50.0%).
Median-vs-unconstrained: drops≥20%=True
at K=1 (drop 60.0%).

Outcome rate on this table uses `require_status=False`, so "accepted"
here is "some record in the cap has status=ok". Most quota families
have no status at all; the status-only companion table is in
result.json (`job_family_quota_5h_len_ge2_status_only`). Do not read
the quota-table outcome_rate as a quality rate.

## Predictor in the loop (later-slice call chains)

Held-out first-attempt AUC **0.6941**.
Without predictor (K=3): cost/accepted 1.6078
attempts, accepted 1989/2922.
With predictor τ=0.5: cost/accepted 1.352,
started 2255, accepted
1787, net saving
0.2558 attempts/accepted (15.91%).

Variance share of unconstrained attempts-used: verifier outcome R²
**0.0217**, predicted P(ok) R²
**0.0201**. Verifier dominates predicted cost:
**True**.

## What the numbers mean

Two ≥20% drops show up, on different reconstructions:

- Job-family 5h quota, families with ≥2 attempts: capping at K=1
  cuts p90 from 46.0 pp to
  23.0 pp (50.0%) and
  median from 5.0 to
  2.0 (60.0%).
  Logged-ok outcome rate does not move
  (19/97
  at every K) — every family that ever logs `ok` already did so on
  the first attempt, so extra rounds spend quota without converting
  more logged-ok outcomes. That is the headline YES at K=1.
- Call-level fail-retry chains of length ≥2: capping at
  K=5 cuts p90 attempts from
  7.0 to
  5.0
  (28.57%) while outcome rate only
  moves from 0.2827
  to 0.2765. Most chains
  are length 1, so the all-chain p90 stays 1.0 at every tier.

Cost per accepted counts spend on still-failed runs; it rises with K
on both reconstructions (you pour attempts into streaks that never
log `ok`). Retries do not improve cost-per-accepted versus single-shot.

The predictor comparison is the spec's economics question: a cheap
tabular skip of low-P(ok) first attempts, not a prefill scout (the
card's method is not in these logs). Saving is in attempts, not
dollars — status-bearing rows do not carry paid `cost_usd`.

## Limits

- Reconstructed retries, not labelled ones. Call chains extend only
  after a non-ok; soak successes in a burst become separate length-1
  runs. Fail streaks of the same model inside a minute are still
  treated as one run — some of those may be independent trials.
  Stated as an assumption, not hidden.
- Job-family stems can still over- or under-merge. Sample families
  with ≥2 attempts are in result.json for inspection.
- Paid-call rows (`job=hydra paid call`) have `cap_usd` checkpoint
  budgets and dollars, and no status and no retries; they are not in
  the tier tables.
- No quality labels. Accepted means the logger wrote `ok`.
- Card C-scout-before-you-route is not staged under cards/.
