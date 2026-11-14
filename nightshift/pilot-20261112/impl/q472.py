#!/usr/bin/env python3
"""Q472 - e-means vs tuned Lloyd at small k and n; cost-scaling fits on
synthetic mixtures (Academy, retrieval).

Implements spec item 9 of TOP10-TEST-SPECS-DRAFT.md (small k/n grid,
objective value + wall-time per cell, the k/n region where the advantage
flips) together with the run brief's framing (fit cost ~ n^b exponents
for a k-means-family baseline and an e-means-style solver on an easy
separable family and a hard overlapping family; report whether the gap
widens or narrows with n).

Source card: cards/C-e-means-outperforming-k-means-muse-20261111.md
(arXiv:2611.09501v1, Bessa et al., FAIR). The e-means solver below is
built ONLY from what the card states: per-cluster EMA count N and sum S,
centroid = S/N, step size (1 - decay) cosine-annealed toward a floor,
dead-cluster revival every five batches for clusters whose count falls
below a tenth of the mean count (rebuilt by splitting a donor),
near-zero-weight initialisation, and a last-epoch-mean finalisation.
The card does NOT print the authors' batch-size / decay scaling-law
formulas, so batch size and decay schedule here are stated heuristics
(see ASSUMPTIONS) - this is an e-means-STYLE solver, not the Faiss code.

Usage: q472.py [results_root]   (default ./results)
Writes <results_root>/Q472/{result.json, notes.md, cells.json}.
stdlib + numpy only.
"""
import os
# Single-threaded BLAS so wall times are comparable and reproducible.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json
import math
import sys
import time
from datetime import datetime

import numpy as np

QID = "Q472"
TITLE = "e-means vs tuned Lloyd at small k and n; cost-scaling exponents on synthetic mixtures"
CARD = "cards/C-e-means-outperforming-k-means-muse-20261111.md"
TIME_BUDGET_S = 30 * 60        # self-limit; RUN-PLAN timeout for q472 is 45 min
TOL = 1e-3                     # "reached target" tolerance, applied to BOTH solvers
LLOYD_ITERS = 25               # card: Lloyd's 25-epoch loss is the reference
EM_BUDGETS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]   # e-means epoch budgets
CARD_EPOCH_BAND = (1.4, 2.6)   # card: below Lloyd-25 loss in 1.4-2.6 epochs
CLAIM_BUDGET = 2.5             # largest grid budget inside the card's 2.6 bound


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ----------------------------------------------------------------- core ---

def sqdist(X, x2, C):
    D = x2[:, None] - 2.0 * (X @ C.T) + np.einsum("ij,ij->i", C, C)[None, :]
    np.maximum(D, 0.0, out=D)
    return D


def assign(X, x2, C):
    D = sqdist(X, x2, C)
    a = D.argmin(1)
    return a, D[np.arange(len(X)), a]


def inertia(X, x2, C):
    return float(assign(X, x2, C)[1].sum())


def cluster_sums(X, a, k):
    M = np.zeros((len(X), k))
    M[np.arange(len(X)), a] = 1.0
    return M.sum(0), M.T @ X


def lloyd(X, x2, C0, iters=LLOYD_ITERS):
    """Plain Lloyd. Empty clusters are re-seeded at the worst-served point.
    Returns final centroids, per-iteration loss of C_t (t=1..), cumulative
    algorithm seconds after each iteration (evaluation passes not timed)."""
    C = C0.copy()
    k = len(C)
    losses, ctimes = [], []
    tacc = 0.0
    prev_a = None
    for _ in range(iters):
        t0 = time.perf_counter()
        a, dmin = assign(X, x2, C)
        cnt, S = cluster_sums(X, a, k)
        nz = cnt > 0
        C[nz] = S[nz] / cnt[nz, None]
        for j in np.where(~nz)[0]:
            far = int(dmin.argmax())
            C[j] = X[far]
            dmin[far] = 0.0
        tacc += time.perf_counter() - t0
        ctimes.append(tacc)
        losses.append(inertia(X, x2, C))       # instrumentation, untimed
        if prev_a is not None and np.array_equal(a, prev_a) and nz.all():
            break                               # fixed point: further iters identical
        prev_a = a
    return C, losses, ctimes


def kmeanspp_init(X, x2, k, rng):
    n = len(X)
    idx = [int(rng.integers(n))]
    d = sqdist(X, x2, X[idx]).ravel()
    for _ in range(1, k):
        p = d / d.sum() if d.sum() > 0 else None
        j = int(rng.choice(n, p=p))
        idx.append(j)
        d = np.minimum(d, sqdist(X, x2, X[[j]]).ravel())
    return X[idx].copy()


def batch_size(n, k):
    # ASSUMPTION: the authors' batch-size scaling law is not in the card.
    return int(min(n, max(4 * k, round(math.sqrt(n * k)))))


def emeans(X, x2, C0, epochs, batch, rng, alpha0=0.5, init_weight=1e-3,
           revive_every=5, revive_frac=0.1, finalize=True):
    """e-means-style EMA mini-batch k-means, per the card's description."""
    n, d = X.shape
    k = len(C0)
    spe = math.ceil(n / batch)
    T = max(1, int(round(epochs * spe)))
    floor = min(alpha0, 1.0 / spe)     # ASSUMPTION: floor memory ~ one epoch
    C = C0.copy()
    N = np.full(k, init_weight)        # near-zero-weight initialisation
    S = C * init_weight
    fin_cnt = np.zeros(k)
    fin_sum = np.zeros((k, d))
    fin_start = T - min(spe, T)        # last epoch's worth of steps
    revived = 0
    perm = None
    t0 = time.perf_counter()
    for t in range(T):
        j = t % spe
        if j == 0:
            perm = rng.permutation(n)
        idx = perm[j * batch:(j + 1) * batch]
        Xb = X[idx]
        a, _ = assign(Xb, x2[idx], C)
        cnt, sm = cluster_sums(Xb, a, k)
        frac = t / (T - 1) if T > 1 else 1.0
        alpha = floor + 0.5 * (alpha0 - floor) * (1.0 + math.cos(math.pi * frac))
        N = (1.0 - alpha) * N + alpha * cnt
        S = (1.0 - alpha) * S + alpha * sm
        C = S / N[:, None]
        if t >= fin_start:
            fin_cnt += cnt
            fin_sum += sm
        if (t + 1) % revive_every == 0:
            dead = np.where(N < revive_frac * N.mean())[0]
            for dj in dead:
                donor = int(N.argmax())
                if donor == dj:
                    continue
                members = np.where(a == donor)[0]
                pick = members[rng.integers(len(members))] if len(members) else rng.integers(len(Xb))
                delta = 0.01 * (Xb[pick] - C[donor])
                if not np.any(delta):
                    delta = 1e-6 * rng.normal(size=d)
                cd = C[donor].copy()
                C[dj], C[donor] = cd + delta, cd - delta
                N[dj] = N[donor] = N[donor] / 2.0
                S[dj], S[donor] = C[dj] * N[dj], C[donor] * N[donor]
                revived += 1
    if finalize:
        nz = fin_cnt > 0
        Cf = C.copy()
        Cf[nz] = fin_sum[nz] / fin_cnt[nz, None]
    else:
        Cf = C
    secs = time.perf_counter() - t0
    return Cf, C, secs, revived, T


def first_reach(losses, target):
    for i, L in enumerate(losses):
        if L <= target:
            return i
    return None


def ols_loglog(ns, ys):
    """Fit log y = a + b log n; return b, SE(b), a, R^2, points used."""
    x = np.log(np.asarray(ns, float))
    y = np.log(np.asarray(ys, float))
    if len(x) < 3 or len(set(x.tolist())) < 2:
        return None
    A = np.vstack([np.ones_like(x), x]).T
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    res = y - A @ coef
    dof = len(x) - 2
    s2 = float(res @ res) / dof if dof > 0 else float("nan")
    cov = s2 * np.linalg.inv(A.T @ A)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float(res @ res) / ss_tot if ss_tot > 0 else float("nan")
    return {"b": round(float(coef[1]), 4), "se_b": round(float(math.sqrt(cov[1, 1])), 4),
            "log_a": round(float(coef[0]), 4), "r2": round(r2, 4), "points": int(len(x))}


# ----------------------------------------------------------------- data ---

FAMILIES = {
    # easy: well-separated, equal weights; hard: overlapping, unequal weights
    "easy_separable": {"center_sd": 4.0, "dirichlet": None},
    "hard_overlapping": {"center_sd": 0.35, "dirichlet": 2.0},
}
D_DIM = 32
K_TRUE = 16


def make_mixture(family, n, seed):
    spec = FAMILIES[family]
    rng = np.random.default_rng(10_000 + seed)
    centers = rng.normal(0.0, spec["center_sd"], size=(K_TRUE, D_DIM))
    w = (rng.dirichlet([spec["dirichlet"]] * K_TRUE) if spec["dirichlet"]
         else np.full(K_TRUE, 1.0 / K_TRUE))
    lab = rng.choice(K_TRUE, size=n, p=w)
    X = centers[lab] + rng.normal(size=(n, D_DIM))
    return X, lab


# ----------------------------------------------------------------- run ----

def run_cell(family, n, k, seed):
    X, _ = make_mixture(family, n, seed)
    x2 = np.einsum("ij,ij->i", X, X)
    rng = np.random.default_rng(seed * 7919 + k * 31 + n)
    init_idx = rng.choice(n, size=k, replace=False)
    C0 = X[init_idx].copy()          # matched init: Lloyd and e-means share it

    _, l_losses, l_times = lloyd(X, x2, C0)
    L25 = l_losses[-1]
    target = L25 * (1.0 + TOL)
    it = first_reach(l_losses, target)
    lloyd_iters_to_target = it + 1
    lloyd_time_to_target = l_times[it]

    t0 = time.perf_counter()
    Cpp0 = kmeanspp_init(X, x2, k, np.random.default_rng(seed + 99))
    pp_init_s = time.perf_counter() - t0
    _, pp_losses, pp_times = lloyd(X, x2, Cpp0)

    b = batch_size(n, k)
    em = {}
    for E in EM_BUDGETS:
        Cf, Craw, secs, revived, T = emeans(X, x2, C0, E, b, np.random.default_rng(seed * 101 + int(E * 10)))
        em[E] = {"loss": inertia(X, x2, Cf), "loss_raw_ema": inertia(X, x2, Craw),
                 "secs": secs, "revived": revived, "steps": T}
    reach = [E for E in EM_BUDGETS if em[E]["loss"] <= target]
    E_t = min(reach) if reach else None
    return {
        "family": family, "n": n, "k": k, "seed": seed, "batch": b,
        "lloyd25_loss": L25, "lloyd_iters_run": len(l_losses),
        "lloyd_iters_to_target": lloyd_iters_to_target,
        "lloyd_secs_to_target": lloyd_time_to_target,
        "lloyd_secs_full": l_times[-1],
        "lloyd_dist_evals_to_target": lloyd_iters_to_target * n * k,
        "lloydpp_loss": pp_losses[-1], "lloydpp_secs": pp_init_s + pp_times[-1],
        "em": {str(E): v for E, v in em.items()},
        "em_epochs_to_target": E_t,
        "em_secs_to_target": em[E_t]["secs"] if E_t is not None else None,
        "em_dist_evals_to_target": (E_t * n * k) if E_t is not None else None,
        "em_claim_ratio": em[CLAIM_BUDGET]["loss"] / L25,
        "em_claim_beats_lloyd25": em[CLAIM_BUDGET]["loss"] <= L25,
        "em_claim_beats_lloydpp": em[CLAIM_BUDGET]["loss"] <= pp_losses[-1],
        "em_claim_secs": em[CLAIM_BUDGET]["secs"],
    }


def main():
    started = time.time()
    started_iso = now_iso()
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "results")
    out_dir = os.path.join(root, QID)
    os.makedirs(out_dir, exist_ok=True)
    files = {k: os.path.join(out_dir, k) for k in ("result.json", "notes.md", "cells.json")}

    N_GRID = [500, 2000, 8000, 32000, 128000]
    K_GRID = [4, 8, 16, 32]
    SEEDS = [0, 1, 2]
    # Order: all small cells first, so a timebox cut drops the largest n.
    plan = [(f, n, k, s) for n in N_GRID for k in K_GRID for f in FAMILIES for s in SEEDS]
    cells, cut = [], []
    status = "done"
    try:
        for i, (f, n, k, s) in enumerate(plan):
            if time.time() - started > TIME_BUDGET_S:
                cut = plan[i:]
                status = "partial"
                break
            cells.append(run_cell(f, n, k, s))
            print(f"[{QID}] {f} n={n} k={k} seed={s} done ({time.time() - started:.0f}s)", flush=True)
    except Exception as e:  # record, never silent
        status = "failed" if not cells else "partial"
        cut = [("error", repr(e))]

    # ------------------------------------------------------- aggregate ---
    def med(xs):
        xs = [x for x in xs if x is not None]
        return float(np.median(xs)) if xs else None

    grid = []
    for f in FAMILIES:
        for n in N_GRID:
            for k in K_GRID:
                cs = [c for c in cells if c["family"] == f and c["n"] == n and c["k"] == k]
                if not cs:
                    continue
                e_t = [c["em_epochs_to_target"] for c in cs]
                grid.append({
                    "family": f, "n": n, "k": k, "seeds": len(cs),
                    "median_lloyd25_loss": med([c["lloyd25_loss"] for c in cs]),
                    "median_lloydpp_loss": med([c["lloydpp_loss"] for c in cs]),
                    "median_em2.5_loss": med([c["em"][str(CLAIM_BUDGET)]["loss"] for c in cs]),
                    "median_em2.5_over_lloyd25": med([c["em_claim_ratio"] for c in cs]),
                    "em2.5_beats_lloyd25_seeds": sum(c["em_claim_beats_lloyd25"] for c in cs),
                    "em2.5_beats_lloydpp_seeds": sum(c["em_claim_beats_lloydpp"] for c in cs),
                    "median_em_epochs_to_target": med(e_t),
                    "em_target_unreached_seeds": sum(x is None for x in e_t),
                    "median_lloyd_iters_to_target": med([c["lloyd_iters_to_target"] for c in cs]),
                    "median_lloyd_secs_to_target": med([c["lloyd_secs_to_target"] for c in cs]),
                    "median_em_secs_to_target": med([c["em_secs_to_target"] for c in cs]),
                    "median_em2.5_secs": med([c["em_claim_secs"] for c in cs]),
                    "median_lloyd25_secs": med([c["lloyd_secs_full"] for c in cs]),
                })

    # Loss advantage: e-means at 2.5 epochs beats Lloyd-25 in a majority of seeds.
    # Speed advantage: e-means time-to-target < tuned (early-stopped) Lloyd time-to-target.
    for g in grid:
        g["loss_advantage_em"] = g["em2.5_beats_lloyd25_seeds"] * 2 > g["seeds"]
        lt, et = g["median_lloyd_secs_to_target"], g["median_em_secs_to_target"]
        g["speed_advantage_em"] = (et is not None and lt is not None and et < lt
                                   and g["em_target_unreached_seeds"] * 2 < g["seeds"])

    # Scaling fits: cost-to-target vs n per family, per k and pooled over k.
    scaling = {}
    for f in FAMILIES:
        fam = {}
        for kk in K_GRID + ["pooled"]:
            cs = [c for c in cells if c["family"] == f and (kk == "pooled" or c["k"] == kk)]
            if not cs:
                continue
            reached = [c for c in cs if c["em_epochs_to_target"] is not None]
            # pooled fit includes k as a covariate implicitly by normalising per-k cost by k
            def norm(c, key):
                return c[key] / (c["k"] if kk == "pooled" else 1)
            fam[str(kk)] = {
                "lloyd_wall_s": ols_loglog([c["n"] for c in cs], [max(norm(c, "lloyd_secs_to_target"), 1e-7) for c in cs]),
                "emeans_wall_s": ols_loglog([c["n"] for c in reached], [max(norm(c, "em_secs_to_target"), 1e-7) for c in reached]),
                "lloyd_dist_evals": ols_loglog([c["n"] for c in cs], [norm(c, "lloyd_dist_evals_to_target") for c in cs]),
                "emeans_dist_evals": ols_loglog([c["n"] for c in reached], [norm(c, "em_dist_evals_to_target") for c in reached]),
                "emeans_cells_target_unreached": len(cs) - len(reached),
                "cells": len(cs),
            }
        scaling[f] = fam

    def gap_trend(fit_l, fit_e):
        if not fit_l or not fit_e:
            return "not fittable"
        diff = fit_l["b"] - fit_e["b"]          # >0: Lloyd cost grows faster -> gap widens
        se = math.sqrt(fit_l["se_b"] ** 2 + fit_e["se_b"] ** 2)
        if abs(diff) < 2 * se:
            return f"no clear trend (b_lloyd - b_emeans = {diff:+.3f}, 2SE = {2 * se:.3f})"
        return ("widens in e-means' favour" if diff > 0 else "narrows / moves toward Lloyd") + \
            f" (b_lloyd - b_emeans = {diff:+.3f}, 2SE = {2 * se:.3f})"

    headline = {}
    for f in FAMILIES:
        p = scaling.get(f, {}).get("pooled")
        if not p:
            continue
        headline[f] = {
            "b_lloyd_wall": p["lloyd_wall_s"]["b"] if p["lloyd_wall_s"] else None,
            "b_emeans_wall": p["emeans_wall_s"]["b"] if p["emeans_wall_s"] else None,
            "gap_trend_wall": gap_trend(p["lloyd_wall_s"], p["emeans_wall_s"]),
            "b_lloyd_dist_evals": p["lloyd_dist_evals"]["b"] if p["lloyd_dist_evals"] else None,
            "b_emeans_dist_evals": p["emeans_dist_evals"]["b"] if p["emeans_dist_evals"] else None,
            "gap_trend_dist_evals": gap_trend(p["lloyd_dist_evals"], p["emeans_dist_evals"]),
            "emeans_cells_target_unreached": p["emeans_cells_target_unreached"],
            "cells": p["cells"],
        }
    flips = {
        "loss_advantage_cells (e-means@2.5ep beats Lloyd-25)":
            [f"{g['family']} n={g['n']} k={g['k']}" for g in grid if g["loss_advantage_em"]],
        "loss_disadvantage_cells":
            [f"{g['family']} n={g['n']} k={g['k']}" for g in grid if not g["loss_advantage_em"]],
        "speed_advantage_cells (e-means time-to-target < early-stopped Lloyd)":
            [f"{g['family']} n={g['n']} k={g['k']}" for g in grid if g["speed_advantage_em"]],
    }
    em_eps = [c["em_epochs_to_target"] for c in cells if c["em_epochs_to_target"] is not None]
    headline["card_band_check"] = {
        "card_claim": "e-means below Lloyd 25-epoch loss in 1.4-2.6 epochs (card, authors' numbers)",
        "cells_total": len(cells),
        "cells_em_reached_target_within_5ep": len(em_eps),
        "cells_em_reached_target_within_2.5ep": sum(e <= CLAIM_BUDGET for e in em_eps),
        "median_em_epochs_to_target_where_reached": med(em_eps),
        "cells_em2.5_beats_lloyd25": sum(c["em_claim_beats_lloyd25"] for c in cells),
        "cells_em2.5_beats_lloydpp": sum(c["em_claim_beats_lloydpp"] for c in cells),
    }
    headline["flip_region"] = {k: v for k, v in flips.items()}
    # Compact form of the spec's question: per family and n, how many of the
    # k values show the e-means loss advantage, and the median time ratio.
    compact = {}
    for f in FAMILIES:
        for n in N_GRID:
            gs = [g for g in grid if g["family"] == f and g["n"] == n]
            if not gs:
                continue
            ratios = [g["median_lloyd_secs_to_target"] / g["median_em_secs_to_target"]
                      for g in gs if g["median_em_secs_to_target"]]
            compact[f"{f} n={n}"] = {
                "k_with_loss_advantage": f"{sum(g['loss_advantage_em'] for g in gs)}/{len(gs)}",
                "median_em2.5_over_lloyd25": med([g["median_em2.5_over_lloyd25"] for g in gs]),
                "median_time_to_target_lloyd_over_em": round(med(ratios), 3) if ratios else None,
            }
    headline["flip_summary_by_n"] = compact

    finished_iso = now_iso()
    runtime = round(time.time() - started, 2)
    assumptions = [
        "The card does not print the authors' batch-size/decay scaling-law formulas. Batch size b = min(n, max(4k, round(sqrt(n*k)))) and an EMA step size cosine-annealed from 0.5 to a floor of 1/(batches per epoch) are this script's heuristics, fixed for every cell (no per-cell tuning).",
        "e-means components implemented exactly as the card lists them: EMA count N and sum S per cluster, centroid S/N; cosine-annealed step size to a floor; revival every 5 batches for clusters with N < 0.1*mean(N), by splitting the largest-count donor along 1% of the offset to one of its batch points (split detail not in card); init weight 1e-3 so early batches dominate; finalisation = mean of the points assigned during the last epoch of steps.",
        "Each e-means epoch budget (0.5..5 epochs) is a separate run with its schedule set for that budget; 'epochs to target' is the smallest budget in that grid whose final loss reaches the target, so it is resolved only to the grid.",
        f"Target = loss of plain Lloyd after {LLOYD_ITERS} iterations (or its fixed point if it converges earlier) from the SAME random init e-means uses. 'Reached' = loss <= target*(1+{TOL}) for both solvers; the card-claim check uses strict loss <= target at 2.5 epochs (the largest grid budget within the card's 2.6).",
        "'Tuned Lloyd' = Lloyd with early stopping at the first iteration within the tolerance of its own 25-iteration loss, empty clusters re-seeded at the worst-served point; a k-means++-seeded Lloyd (25 iters) is reported as a stronger loss reference. Restarts are matched by seeds (3 per cell, same init for Lloyd and e-means).",
        "Cost = single-threaded numpy wall time of the algorithm steps only (loss evaluations for instrumentation are not timed), and point-centroid distance evaluations (iterations*n*k for Lloyd, epochs*n*k for e-means). Wall-time on CPU numpy at these sizes includes per-batch Python overhead and says nothing about the card's GPU 10-45x figures.",
        "Pooled exponents divide cost by k and fit log(cost/k) on log n across all k; per-k fits are in result.json.",
        f"Synthetic families: d={D_DIM}, {K_TRUE} true Gaussian components, unit noise; easy = centres N(0, 4^2), equal weights; hard = centres N(0, 0.35^2), Dirichlet(2) weights. Cluster count k is swept independently of the true 16.",
        "Brief and spec differ in framing (brief: n-scaling exponents on synthetic families; spec: small k/n grid and flip region). Both are computed from one grid; the corpus text embedding set the CHECKS note mentions is used in Q471, not here.",
    ]
    method = (
        "Synthetic Gaussian-mixture grid (easy separable / hard overlapping families; n in "
        f"{N_GRID}; k in {K_GRID}; 3 seeds). Per cell, plain Lloyd and an e-means-style EMA mini-batch "
        "solver start from the same random init; Lloyd's 25-iteration loss is the target. e-means is run "
        f"at epoch budgets {EM_BUDGETS}; a k-means++ Lloyd gives a stronger loss reference. Per cell: losses, "
        "wall time, epochs/iterations to target, distance evaluations. Cost-to-target is fitted as cost ~ n^b "
        "(OLS on log-log) per family and solver, for wall time and distance evaluations; the gap trend is the "
        "sign of b_lloyd - b_emeans judged against 2 standard errors. The flip region lists the k/n cells where "
        "e-means at 2.5 epochs does or does not beat Lloyd-25 and where it is faster to target."
    )
    result = {
        "qid": QID, "title": TITLE, "status": status,
        "started": started_iso, "finished": finished_iso, "runtime_s": runtime,
        "method": method, "assumptions": assumptions, "headline": headline,
        "scaling_fits": scaling, "grid_summary": grid,
        "cut_from_plan": [list(map(str, c)) for c in cut],
        "source_card": CARD, "spec": "TOP10-TEST-SPECS-DRAFT.md item 9 (Q472)",
        "records_written": [files["result.json"], files["notes.md"], files["cells.json"]],
    }
    with open(files["cells.json"], "w") as fh:
        json.dump(cells, fh, indent=1)
    with open(files["result.json"], "w") as fh:
        json.dump(result, fh, indent=2)

    # ---------------------------------------------------------- notes ----
    fmt = lambda x, p=4: "-" if x is None else (f"{x:.{p}g}" if isinstance(x, float) else str(x))
    L = [f"# {QID} - {TITLE}", "",
         f"Status: **{status}** | runtime {runtime}s | {started_iso} -> {finished_iso}",
         f"Spec: TOP10-TEST-SPECS-DRAFT.md item 9; run brief (scaling-exponent framing). Card: `{CARD}`.", "",
         "## Method", "", method, "",
         "## Assumptions (the card does not fully specify the method)", ""]
    L += [f"- {a}" for a in assumptions]
    L += ["", "## Headline", ""]
    for f in FAMILIES:
        h = headline.get(f)
        if not h:
            continue
        L += [f"**{f}** ({h['cells']} cells, e-means target unreached in {h['emeans_cells_target_unreached']}):",
              f"- wall time to target: b_lloyd = {h['b_lloyd_wall']}, b_emeans = {h['b_emeans_wall']} -> gap {h['gap_trend_wall']}",
              f"- distance evals to target: b_lloyd = {h['b_lloyd_dist_evals']}, b_emeans = {h['b_emeans_dist_evals']} -> gap {h['gap_trend_dist_evals']}", ""]
    cb = headline["card_band_check"]
    L += ["**Card band check** (card claims e-means below Lloyd-25 loss in 1.4-2.6 epochs):",
          f"- e-means reached target (within tol) by 5 epochs in {cb['cells_em_reached_target_within_5ep']}/{cb['cells_total']} runs; by 2.5 epochs in {cb['cells_em_reached_target_within_2.5ep']}; median epochs where reached = {cb['median_em_epochs_to_target_where_reached']}",
          f"- e-means@2.5ep strictly below Lloyd-25 in {cb['cells_em2.5_beats_lloyd25']}/{cb['cells_total']} runs; below k-means++ Lloyd in {cb['cells_em2.5_beats_lloydpp']}", "",
          "**Flip summary by n** (k values where e-means@2.5ep beats Lloyd-25 in a seed majority; "
          "median em/L25 loss ratio; median Lloyd/e-means time-to-target, >1 = e-means faster):", ""]
    for key, v in headline["flip_summary_by_n"].items():
        L.append(f"- {key}: loss advantage at {v['k_with_loss_advantage']} k values; "
                 f"em/L25 = {fmt(v['median_em2.5_over_lloyd25'])}; time ratio = {v['median_time_to_target_lloyd_over_em']}")
    L += ["",
          "## Per-cell grid (medians over seeds)", "",
          "| family | n | k | em2.5/L25 | em2.5 beats L25 (seeds) | em epochs->target | Lloyd iters->target | Lloyd s->target | em s->target |",
          "|---|---|---|---|---|---|---|---|---|"]
    for g in grid:
        L.append(f"| {g['family']} | {g['n']} | {g['k']} | {fmt(g['median_em2.5_over_lloyd25'])} | "
                 f"{g['em2.5_beats_lloyd25_seeds']}/{g['seeds']} | {fmt(g['median_em_epochs_to_target'])} "
                 f"(unreached {g['em_target_unreached_seeds']}) | {fmt(g['median_lloyd_iters_to_target'])} | "
                 f"{fmt(g['median_lloyd_secs_to_target'], 3)} | {fmt(g['median_em_secs_to_target'], 3)} |")
    L += ["", "## What the numbers mean", "",
          "- b is the exponent in cost ~ n^b. Distance-evaluation exponents are hardware-free: b ~ 1 means a "
          "constant number of passes; b > 1 means passes-to-target grow with n. If b_lloyd > b_emeans by more than "
          "2 SE, e-means' relative advantage grows with n (the card's 'large-scale phenomenon' reading); if less, it shrinks.",
          "- Epochs/iterations to target are matched-init comparisons against Lloyd's OWN 25-iteration loss; "
          "Lloyd stopping early at that loss is the 'well-tuned Lloyd' the spec asks about.",
          "- Wall time here is single-thread CPU numpy; e-means pays Python per-batch overhead, which dominates at small n.",
          "", "## Limits", "",
          "- Not the authors' code and not their scaling-law formulas (not in the card); results test an e-means-style "
          "solver built from the card's description with fixed heuristics, so a negative result may reflect the "
          "missing tuning rule rather than e-means itself - exactly the card's own T14 caveat.",
          "- Synthetic Gaussian data, d=32, n <= 128k: far from the card's 10B-point / 16M-cluster regime.",
          "- Epochs-to-target is resolved only to the budget grid; 3 seeds per cell.",
          ]
    if cut:
        L += [f"- TIMEBOX/ERROR CUT: {len(cut)} planned cells not run: {cut[:5]}{' ...' if len(cut) > 5 else ''}"]
    with open(files["notes.md"], "w") as fh:
        fh.write("\n".join(L) + "\n")
    print(json.dumps(headline, indent=1))


if __name__ == "__main__":
    main()
