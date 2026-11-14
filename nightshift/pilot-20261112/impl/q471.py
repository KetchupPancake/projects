#!/usr/bin/env python3
"""Q471 - e-means vs k-means on Academy-adjacent text embeddings: the
independent replication card 162 was filed as awaiting (Academy, retrieval).

Implements spec item 10 of TOP10-TEST-SPECS-DRAFT.md as framed by the run
brief: k-means (Lloyd) vs an e-means-style solver on the staged corpus text
(data/takeaways-full.json, 648 take-aways), embedded with TF-IDF + truncated
SVD written in numpy (no sklearn in the run room; CHECKS.md allows TF-IDF/SVD
when no neural embedder is available - this script uses TF-IDF/SVD and
records that). Small grid k in {4, 8, 12} x two sample sizes; runtime and
quality proxies (inertia; exact silhouette); plus one synthetic set with
known ground truth scored by hand-computed ARI. Closes with the spec's
verdict field.

Source card: cards/C-e-means-outperforming-k-means-muse-20261111.md.
The e-means solver is built only from what the card states (EMA count/sum,
centroid S/N, cosine-annealed step to a floor, dead-cluster revival every 5
batches below 0.1x mean count by donor split, near-zero-weight init,
last-epoch-mean finalisation). The authors' scaling-law FORMULAS are not
printed in the card, so the spec's "fit error of the authors' formulas" is
not computable here; the closest faithful reading used is the card's own
quantitative claim (below Lloyd's 25-epoch loss within 1.4-2.6 epochs) as
the prediction, tested against measurement. Said in assumptions and notes.

Usage: q471.py [results_root]   (default ./results)
Writes <results_root>/Q471/{result.json, notes.md, cells.json}.
stdlib + numpy only.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json
import math
import re
import sys
import time
from collections import Counter
from datetime import datetime

import numpy as np

QID = "Q471"
TITLE = "e-means vs k-means on staged corpus text embeddings (independent replication for card 162)"
CARD = "cards/C-e-means-outperforming-k-means-muse-20261111.md"
CORPUS = "data/takeaways-full.json"
TIME_BUDGET_S = 60 * 60        # self-limit; RUN-PLAN timeout for q471 is 90 min
TOL = 1e-3
LLOYD_ITERS = 25
EM_BUDGETS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
CARD_EPOCH_BAND = (1.4, 2.6)
CLAIM_BUDGET = 2.5
SVD_DIM = 64


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


# ------------------------------------------------------------ embedding ---

STOP = set("""a an the and or but if of to in on at by for with from as is are was were be been being
this that these those it its into than then so such not no can could would should will may might must
do does did done has have had which who whom whose what when where why how all any each more most other
some only own same very just also over under about after before between through during per via while
their there they them we our you your he she his her i me my one two not""".split())


def tokenize(text):
    text = re.sub(r"^\s*T\d+\s*:\s*", "", text)   # drop the leading theme tag ("T6: ...")
    return [w for w in re.findall(r"[a-z][a-z0-9\-]+", text.lower()) if w not in STOP and len(w) > 1]


def tfidf_svd(texts, dim=SVD_DIM, min_df=2, max_df_frac=0.5):
    docs = [tokenize(t) for t in texts]
    df = Counter(w for d in docs for w in set(d))
    nd = len(docs)
    vocab = sorted(w for w, c in df.items() if c >= min_df and c <= max_df_frac * nd)
    vi = {w: i for i, w in enumerate(vocab)}
    A = np.zeros((nd, len(vocab)))
    for r, d in enumerate(docs):
        for w, c in Counter(d).items():
            if w in vi:
                A[r, vi[w]] = 1.0 + math.log(c)            # sublinear tf
    idf = np.log((1.0 + nd) / (1.0 + np.array([df[w] for w in vocab]))) + 1.0
    A *= idf[None, :]
    A /= np.maximum(np.linalg.norm(A, axis=1, keepdims=True), 1e-12)
    U, s, _ = np.linalg.svd(A, full_matrices=False)       # exact SVD, truncated
    dim = min(dim, len(s))
    E = U[:, :dim] * s[:dim]
    explained = float((s[:dim] ** 2).sum() / (s ** 2).sum())
    E /= np.maximum(np.linalg.norm(E, axis=1, keepdims=True), 1e-12)  # cosine geometry
    empty = int((A.sum(1) == 0).sum())
    return E, {"vocab": len(vocab), "docs": nd, "svd_dim": dim,
               "svd_energy_retained": round(explained, 4), "docs_with_no_vocab_terms": empty}


# ------------------------------------------------------- quality proxies ---

def silhouette(X, a):
    """Exact mean silhouette over all points (Euclidean). Singletons score 0."""
    x2 = np.einsum("ij,ij->i", X, X)
    D = np.sqrt(np.maximum(x2[:, None] - 2 * X @ X.T + x2[None, :], 0.0))
    labs = np.unique(a)
    if len(labs) < 2:
        return None
    sums = np.stack([D[:, a == c].sum(1) for c in labs], 1)
    sizes = np.array([(a == c).sum() for c in labs])
    own = np.searchsorted(labs, a)
    n = len(X)
    own_size = sizes[own]
    a_in = sums[np.arange(n), own] / np.maximum(own_size - 1, 1)
    mean_other = sums / sizes[None, :]
    mean_other[np.arange(n), own] = np.inf
    b_out = mean_other.min(1)
    s = (b_out - a_in) / np.maximum(np.maximum(a_in, b_out), 1e-12)
    s[own_size == 1] = 0.0
    return float(s.mean())


def ari(u, v):
    """Adjusted Rand index from the contingency table (Hubert & Arabie)."""
    u = np.unique(u, return_inverse=True)[1]
    v = np.unique(v, return_inverse=True)[1]
    n = len(u)
    M = np.zeros((u.max() + 1, v.max() + 1))
    np.add.at(M, (u, v), 1)
    c2 = lambda x: x * (x - 1) / 2.0
    sij = c2(M).sum()
    sa = c2(M.sum(1)).sum()
    sb = c2(M.sum(0)).sum()
    exp = sa * sb / c2(n)
    mx = 0.5 * (sa + sb)
    return float((sij - exp) / (mx - exp)) if mx != exp else 1.0


# ----------------------------------------------------------------- run ----

def run_cell(X_all, n, k, seed, with_silhouette=True, truth=None):
    rng = np.random.default_rng(seed * 7919 + k * 31 + n)
    rows = np.sort(rng.choice(len(X_all), size=n, replace=False)) if n < len(X_all) else np.arange(len(X_all))
    X = X_all[rows]
    x2 = np.einsum("ij,ij->i", X, X)
    init_idx = rng.choice(n, size=k, replace=False)
    C0 = X[init_idx].copy()

    Cl, l_losses, l_times = lloyd(X, x2, C0)
    L25 = l_losses[-1]
    target = L25 * (1.0 + TOL)
    it = first_reach(l_losses, target)
    t0 = time.perf_counter()
    Cpp0 = kmeanspp_init(X, x2, k, np.random.default_rng(seed + 99))
    pp_init = time.perf_counter() - t0
    Cpp, pp_losses, pp_times = lloyd(X, x2, Cpp0)

    b = batch_size(n, k)
    em, emC = {}, {}
    for E in EM_BUDGETS:
        Cf, Craw, secs, revived, T = emeans(X, x2, C0, E, b, np.random.default_rng(seed * 101 + int(E * 10)))
        em[str(E)] = {"loss": inertia(X, x2, Cf), "loss_raw_ema": inertia(X, x2, Craw),
                      "secs": secs, "revived": revived, "steps": T}
        emC[E] = Cf
    reach = [E for E in EM_BUDGETS if em[str(E)]["loss"] <= target]
    E_t = min(reach) if reach else None
    cell = {
        "n": n, "k": k, "seed": seed, "batch": b,
        "lloyd25_loss": L25, "lloyd_iters_run": len(l_losses),
        "lloyd_iters_to_target": it + 1, "lloyd_secs_to_target": l_times[it],
        "lloyd25_secs": l_times[-1],
        "lloydpp_loss": pp_losses[-1], "lloydpp_secs": pp_init + pp_times[-1],
        "em": em, "em_epochs_to_target": E_t,
        "em_secs_to_target": em[str(E_t)]["secs"] if E_t is not None else None,
        "em_claim_ratio": em[str(CLAIM_BUDGET)]["loss"] / L25,
        "em_claim_beats_lloyd25": em[str(CLAIM_BUDGET)]["loss"] <= L25,
        "em_claim_beats_lloydpp": em[str(CLAIM_BUDGET)]["loss"] <= pp_losses[-1],
        "em_claim_secs": em[str(CLAIM_BUDGET)]["secs"],
    }
    labels = {"lloyd25": assign(X, x2, Cl)[0], "lloydpp": assign(X, x2, Cpp)[0],
              "em1.0": assign(X, x2, emC[1.0])[0], "em2.5": assign(X, x2, emC[CLAIM_BUDGET])[0]}
    if with_silhouette:
        cell["silhouette"] = {m: silhouette(X, a) for m, a in labels.items()}
    if truth is not None:
        cell["ari"] = {m: ari(truth[rows], a) for m, a in labels.items()}
    return cell


def med(xs):
    xs = [x for x in xs if x is not None]
    return float(np.median(xs)) if xs else None


def main():
    started = time.time()
    started_iso = now_iso()
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "results")
    out_dir = os.path.join(root, QID)
    os.makedirs(out_dir, exist_ok=True)
    files = {k: os.path.join(out_dir, k) for k in ("result.json", "notes.md", "cells.json")}

    def write_blocked(reason):
        res = {"qid": QID, "title": TITLE, "status": "blocked", "started": started_iso,
               "finished": now_iso(), "runtime_s": round(time.time() - started, 2),
               "method": "not run", "assumptions": [], "headline": {"reason": reason},
               "records_written": [files["result.json"], files["notes.md"]]}
        json.dump(res, open(files["result.json"], "w"), indent=2)
        open(files["notes.md"], "w").write(f"# {QID} - {TITLE}\n\nStatus: **blocked**\n\n{reason}\n")

    try:
        corpus = json.load(open(CORPUS))
        texts = [r["takeaway"] for r in corpus]
    except Exception as e:
        write_blocked(f"could not read staged corpus {CORPUS}: {e!r}")
        return
    t0 = time.perf_counter()
    E_all, emb_info = tfidf_svd(texts)
    emb_info["embed_secs"] = round(time.perf_counter() - t0, 3)
    emb_info["embedder"] = "TF-IDF (sublinear tf, smoothed idf, l2) + exact truncated SVD (numpy), rows re-normalised"

    N_FULL = len(E_all)
    N_GRID = [N_FULL // 2, N_FULL]
    K_GRID = [4, 8, 12]
    SEEDS = list(range(10))
    SYN = {"n": 2000, "d": 64, "k_true": 8, "center_sd": 0.5, "seeds": list(range(5))}

    # Plan order: one seed of every text cell first, then synthetic, then remaining seeds,
    # so a timebox cut thins seeds rather than dropping whole cells.
    plan = [("text", n, k, s) for s in SEEDS[:3] for n in N_GRID for k in K_GRID]
    plan += [("syn", SYN["n"], SYN["k_true"], s) for s in SYN["seeds"]]
    plan += [("text", n, k, s) for s in SEEDS[3:] for n in N_GRID for k in K_GRID]

    syn_X, syn_y = {}, {}
    text_cells, syn_cells, cut = [], [], []
    status = "done"
    try:
        for i, (kind, n, k, s) in enumerate(plan):
            if time.time() - started > TIME_BUDGET_S:
                cut = plan[i:]
                status = "partial"
                break
            if kind == "text":
                text_cells.append(run_cell(E_all, n, k, s))
            else:
                rng = np.random.default_rng(20_000 + s)
                C = rng.normal(0, SYN["center_sd"], size=(SYN["k_true"], SYN["d"]))
                y = rng.integers(SYN["k_true"], size=SYN["n"])
                X = C[y] + rng.normal(size=(SYN["n"], SYN["d"]))
                syn_cells.append(run_cell(X, SYN["n"], SYN["k_true"], s, with_silhouette=False, truth=y))
            print(f"[{QID}] {kind} n={n} k={k} seed={s} done ({time.time() - started:.0f}s)", flush=True)
    except Exception as e:
        status = "failed" if not (text_cells or syn_cells) else "partial"
        cut = [("error", repr(e))]

    # ------------------------------------------------------- aggregate ---
    grid = []
    for n in N_GRID:
        for k in K_GRID:
            cs = [c for c in text_cells if c["n"] == n and c["k"] == k]
            if not cs:
                continue
            e_t = [c["em_epochs_to_target"] for c in cs]
            sil = lambda m: med([c["silhouette"][m] for c in cs])
            g = {
                "n": n, "k": k, "seeds": len(cs),
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
                "median_lloyd25_secs": med([c["lloyd25_secs"] for c in cs]),
                "median_em_secs_to_target": med([c["em_secs_to_target"] for c in cs]),
                "median_em2.5_secs": med([c["em_claim_secs"] for c in cs]),
                "median_silhouette": {m: sil(m) for m in ("lloyd25", "lloydpp", "em1.0", "em2.5")},
            }
            g["reproduces_card_claim"] = g["median_em2.5_over_lloyd25"] <= 1.0
            grid.append(g)

    syn = None
    if syn_cells:
        syn = {
            "config": SYN, "seeds_run": len(syn_cells),
            "median_ari": {m: med([c["ari"][m] for c in syn_cells]) for m in ("lloyd25", "lloydpp", "em1.0", "em2.5")},
            "median_em2.5_over_lloyd25": med([c["em_claim_ratio"] for c in syn_cells]),
            "em2.5_beats_lloyd25_seeds": sum(c["em_claim_beats_lloyd25"] for c in syn_cells),
            "median_em_epochs_to_target": med([c["em_epochs_to_target"] for c in syn_cells]),
        }

    # ------------------------------------------------------- verdict -----
    # Pre-stated rule (written before the run):
    #  cell reproduces the card's claim  <=> median over seeds of
    #      loss(e-means @ 2.5 epochs) / loss(Lloyd 25 iters, same init) <= 1.0
    #  f = fraction of text cells reproducing.
    #  f >= 2/3 -> "candidate advancement stands"; f <= 1/3 -> "weakens";
    #  otherwise "inconclusive".
    #  Synthetic sanity check: if median ARI(e-means@2.5) < median ARI(Lloyd-25) - 0.05,
    #  a "stands" is downgraded to "inconclusive".
    #  Wall time is reported but does not enter the verdict (CPU numpy at n<=648
    #  is not the card's GPU regime).
    reasons = []
    if not grid:
        verdict = "inconclusive"
        reasons.append("no text cells completed")
    else:
        f = sum(g["reproduces_card_claim"] for g in grid) / len(grid)
        verdict = ("candidate advancement stands" if f >= 2 / 3 else
                   "weakens" if f <= 1 / 3 else "inconclusive")
        reasons.append(f"{sum(g['reproduces_card_claim'] for g in grid)}/{len(grid)} text cells have median "
                       f"e-means@2.5ep loss <= Lloyd-25 loss (f = {f:.2f}; thresholds 2/3 stands, 1/3 weakens)")
        rs = [g["median_em2.5_over_lloyd25"] for g in grid]
        reasons.append(f"magnitude: per-cell median e-means@2.5ep / Lloyd-25 loss ranges {min(rs):.4f}-{max(rs):.4f} "
                       f"(i.e. {100 * (min(rs) - 1):+.2f}% to {100 * (max(rs) - 1):+.2f}%)")
        reasons.append("scope: n <= 648 TF-IDF/SVD text with a heuristic batch/decay schedule (authors' scaling-law "
                       "formulas not in the card); this bears on the small-n, off-family question only, not on the "
                       "card's large-scale GPU claims")
        if syn and verdict == "candidate advancement stands":
            if syn["median_ari"]["em2.5"] < syn["median_ari"]["lloyd25"] - 0.05:
                verdict = "inconclusive"
                reasons.append("downgraded: synthetic ARI of e-means@2.5 is >0.05 below Lloyd-25")
    if status == "partial":
        reasons.append("run was cut by the timebox; verdict is on the completed cells only")

    em_eps = [c["em_epochs_to_target"] for c in text_cells if c["em_epochs_to_target"] is not None]
    headline = {
        "verdict": verdict,
        "verdict_reasons": reasons,
        "text_cells_reproducing_claim": f"{sum(g['reproduces_card_claim'] for g in grid)}/{len(grid)}",
        "median_em2.5_over_lloyd25_by_cell": {f"n={g['n']} k={g['k']}": round(g["median_em2.5_over_lloyd25"], 5) for g in grid},
        "card_prediction_vs_measured": {
            "prediction (card, authors' numbers)": "below Lloyd 25-epoch loss within 1.4-2.6 epochs",
            "text_runs": len(text_cells),
            "text_runs_reaching_target_within_5ep": len(em_eps),
            "text_runs_reaching_target_within_2.5ep": sum(e <= CLAIM_BUDGET for e in em_eps),
            "median_epochs_to_target_where_reached": med(em_eps),
            "text_runs_em2.5_strictly_below_lloyd25": sum(c["em_claim_beats_lloyd25"] for c in text_cells),
            "text_runs_em2.5_below_lloydpp": sum(c["em_claim_beats_lloydpp"] for c in text_cells),
        },
        "median_runtime_s_by_cell": {f"n={g['n']} k={g['k']}": {
            "lloyd_to_target": g["median_lloyd_secs_to_target"], "lloyd25": g["median_lloyd25_secs"],
            "em_to_target": g["median_em_secs_to_target"], "em2.5": g["median_em2.5_secs"]} for g in grid},
        "median_silhouette_by_cell": {f"n={g['n']} k={g['k']}": g["median_silhouette"] for g in grid},
        "synthetic_ari": syn["median_ari"] if syn else None,
        "embedding": emb_info,
        "spec_points_not_implementable": [
            "Fit error of the authors' scaling-law formulas on text embeddings vs their reported image-embedding fit: "
            "neither the formulas nor the reported fit errors are printed in the card, so this cannot be computed "
            "without inventing them. Replaced by the card's stated 1.4-2.6 epoch claim as the prediction.",
        ],
    }

    finished_iso = now_iso()
    runtime = round(time.time() - started, 2)
    assumptions = [
        f"Corpus: the {N_FULL} take-away strings in {CORPUS} (leading theme tag like 'T6:' stripped). The staged question set is not used - the brief names the take-aways file.",
        f"Embedding: TF-IDF (tokens [a-z][a-z0-9-]+, small stop list, min_df=2, max_df=50%, sublinear tf, smoothed idf, l2) then exact SVD truncated to {SVD_DIM} dims, rows re-normalised to unit length. A neural embedder was not attempted (no model downloads in the run room; numpy only).",
        f"Sample sizes: n = {N_GRID[0]} (random subset per seed, drawn from the full embedded corpus) and n = {N_GRID[1]} (full). TF-IDF/SVD is fitted once on all {N_FULL} texts.",
        "e-means-style solver per the card's listed components; batch size b = min(n, max(4k, round(sqrt(n*k)))) and the step-size schedule (cosine 0.5 -> 1/(batches per epoch)) are this script's heuristics because the card does not print the authors' scaling-law formulas. Donor-split detail of revival is not in the card (split along 1% of the offset to a donor batch point).",
        f"Baseline: Lloyd {LLOYD_ITERS} iterations (or fixed point) from the same random init as e-means; k-means++ Lloyd as a stronger loss reference. Target-reached tolerance {TOL} for both solvers; the card-claim check is strict (<=) at 2.5 epochs, the largest budget grid point within the card's 2.6.",
        "Quality proxies: inertia (sum of squared Euclidean distances on unit-normalised embeddings) and exact silhouette over all points (n <= 648 makes the full computation cheap, so no sampling). ARI is computed from the contingency table on a synthetic mixture with known labels.",
        f"Synthetic ground-truth set: n={SYN['n']}, d={SYN['d']}, {SYN['k_true']} Gaussian components, centres N(0, {SYN['center_sd']}^2), unit noise, uniform labels; k = k_true.",
        "Runtime = single-thread numpy wall time of algorithm steps only (evaluation passes untimed). At these n, timings are microseconds-to-milliseconds and overhead-dominated; they are reported, not used in the verdict.",
        "Verdict rule was fixed in code before the run (see verdict_reasons).",
    ]
    method = (
        f"Embedded {N_FULL} staged take-aways with numpy TF-IDF + truncated SVD ({SVD_DIM} dims, unit rows). "
        f"Grid k in {K_GRID} x n in {N_GRID} x {len(SEEDS)} seeds: plain Lloyd (25 iters) and an e-means-style EMA "
        f"mini-batch solver from the same random init, e-means at epoch budgets {EM_BUDGETS}, plus k-means++ Lloyd. "
        "Per run: inertia, wall time, epochs/iterations to Lloyd-25 loss, exact silhouette. One synthetic Gaussian "
        "mixture with known labels (5 seeds) scored by hand-computed ARI. Verdict by a pre-stated rule on the "
        "fraction of text cells where e-means at 2.5 epochs matches or beats Lloyd-25 loss."
    )
    result = {
        "qid": QID, "title": TITLE, "status": status,
        "started": started_iso, "finished": finished_iso, "runtime_s": runtime,
        "method": method, "assumptions": assumptions, "headline": headline,
        "verdict": verdict,
        "grid_summary": grid, "synthetic_summary": syn,
        "cut_from_plan": [list(map(str, c)) for c in cut],
        "source_card": CARD, "spec": "TOP10-TEST-SPECS-DRAFT.md item 10 (Q471)",
        "records_written": [files["result.json"], files["notes.md"], files["cells.json"]],
    }
    with open(files["cells.json"], "w") as fh:
        json.dump({"text": text_cells, "synthetic": syn_cells}, fh, indent=1)
    with open(files["result.json"], "w") as fh:
        json.dump(result, fh, indent=2)

    fmt = lambda x, p=4: "-" if x is None else (f"{x:.{p}g}" if isinstance(x, float) else str(x))
    L = [f"# {QID} - {TITLE}", "",
         f"Status: **{status}** | runtime {runtime}s | {started_iso} -> {finished_iso}",
         f"Spec: TOP10-TEST-SPECS-DRAFT.md item 10, as framed by the run brief. Card: `{CARD}`.", "",
         f"## Verdict: **{verdict}**", ""]
    L += [f"- {r}" for r in reasons]
    L += ["", "## Method", "", method, "",
          f"Embedding: vocab {emb_info['vocab']} terms, SVD energy retained {emb_info['svd_energy_retained']}, "
          f"{emb_info['docs_with_no_vocab_terms']} docs with no vocabulary terms, embed time {emb_info['embed_secs']}s.", "",
          "## Assumptions", ""]
    L += [f"- {a}" for a in assumptions]
    L += ["", "## Results - text grid (medians over seeds)", "",
          "| n | k | seeds | em2.5/L25 loss | em2.5 beats L25 | em2.5 beats L++ | em epochs->target | Lloyd iters->target | Lloyd s->target | em s->target | sil L25 | sil L++ | sil em2.5 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for g in grid:
        s_ = g["median_silhouette"]
        L.append(f"| {g['n']} | {g['k']} | {g['seeds']} | {fmt(g['median_em2.5_over_lloyd25'], 5)} | "
                 f"{g['em2.5_beats_lloyd25_seeds']}/{g['seeds']} | {g['em2.5_beats_lloydpp_seeds']}/{g['seeds']} | "
                 f"{fmt(g['median_em_epochs_to_target'])} (unreached {g['em_target_unreached_seeds']}) | "
                 f"{fmt(g['median_lloyd_iters_to_target'])} | {fmt(g['median_lloyd_secs_to_target'], 3)} | "
                 f"{fmt(g['median_em_secs_to_target'], 3)} | {fmt(s_['lloyd25'], 3)} | {fmt(s_['lloydpp'], 3)} | {fmt(s_['em2.5'], 3)} |")
    cp = headline["card_prediction_vs_measured"]
    L += ["", "## Card prediction vs measured", "",
          "- Card (authors' numbers): below Lloyd's 25-epoch loss within 1.4-2.6 epochs.",
          f"- Measured on text: {cp['text_runs_reaching_target_within_5ep']}/{cp['text_runs']} runs reached Lloyd-25 loss (within {TOL}) by 5 epochs, "
          f"{cp['text_runs_reaching_target_within_2.5ep']} by 2.5 epochs; median epochs where reached = {cp['median_epochs_to_target_where_reached']}.",
          f"- Strictly below Lloyd-25 at 2.5 epochs in {cp['text_runs_em2.5_strictly_below_lloyd25']}/{cp['text_runs']} runs; "
          f"below k-means++ Lloyd in {cp['text_runs_em2.5_below_lloydpp']}/{cp['text_runs']}.", ""]
    if syn:
        L += ["## Synthetic ground truth (ARI)", "",
              f"Config {SYN}; {syn['seeds_run']} seeds. Median ARI: " +
              ", ".join(f"{m} = {fmt(v)}" for m, v in syn["median_ari"].items()) +
              f". Median em2.5/L25 loss = {fmt(syn['median_em2.5_over_lloyd25'], 5)}; "
              f"e-means@2.5 strictly below Lloyd-25 in {syn['em2.5_beats_lloyd25_seeds']}/{syn['seeds_run']} seeds.", ""]
    L += ["## What the numbers mean", "",
          "- em2.5/L25 < 1 means the e-means-style solver, given 2.5 passes, found lower inertia than 25 Lloyd passes "
          "from the same start - the card's central claim, in its own units (epochs, not GPU seconds).",
          "- Silhouette and ARI check that lower inertia is not bought with worse partitions.",
          ] + ([f"- All text-grid median silhouettes are below 0.1 (max {max(v for g in grid for v in g['median_silhouette'].values() if v is not None):.3f}): "
                "the take-away embeddings have weak cluster structure, so the solvers are choosing among many "
                "near-equivalent partitions and sub-1% inertia gaps carry little practical meaning."]
               if grid and max(v for g in grid for v in g["median_silhouette"].values() if v is not None) < 0.1 else []) + [
          "- Wall times at n <= 648 are tiny and dominated by Python overhead; they are not evidence about the card's 10-45x GPU speedups either way.",
          "", "## Limits", "",
          "- Not the authors' implementation or formulas: an e-means-style solver from the card's description with fixed "
          "heuristics. A shortfall can come from the missing tuning rule (the card's own T14 caveat), not from e-means as published.",
          "- n <= 648 sparse-text embeddings in 64 dims: this is a small-scale off-family check, not 'Academy scale' in the "
          "card's sense of a large index build; the spec's scaling-formula fit error is not computable (formulas not in card).",
          "- TF-IDF/SVD, not a neural embedder; the geometry of neural text embeddings may differ.",
          ]
    if cut:
        L += [f"- TIMEBOX/ERROR CUT: {len(cut)} planned runs not done: {cut[:5]}{' ...' if len(cut) > 5 else ''}"]
    with open(files["notes.md"], "w") as fh:
        fh.write("\n".join(L) + "\n")
    print(json.dumps({k: headline[k] for k in ("verdict", "verdict_reasons", "text_cells_reproducing_claim",
                                               "median_em2.5_over_lloyd25_by_cell", "card_prediction_vs_measured",
                                               "synthetic_ari", "embedding")}, indent=1))


if __name__ == "__main__":
    main()
