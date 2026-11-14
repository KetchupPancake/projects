#!/usr/bin/env python3
"""Q281 — Pre-run prediction value on Hydra run records (Hydra, routing).

Implements spec item 4 in TOP10-TEST-SPECS-DRAFT.md against card
C-meta-models-model-learning, reduced as CHECKS.md requires.

Tabular experiment on data/routing/job-usage-log.jsonl: outcome ~
f(cost so far, calls so far, model, task_type). Outcome is the logged
status field (ok vs anything else). The logs carry status and cost
and no quality labels — verified_correct / verified_by are present
on thousands of rows and are null on every one of them.

Usage: q281.py [output_root]   (default ./results)
Writes <output_root>/Q281/result.json and notes.md.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np

QID = "Q281"
TITLE = "Pre-run prediction value on Hydra run records"
LOG_PATH = os.path.join("data", "routing", "job-usage-log.jsonl")
TRAIN_FRAC = 0.70
MIN_MODEL_N = 30
L2 = 1e-2


def now_iso():
    return datetime.now().astimezone().isoformat()


def parse_ts(s):
    if not s:
        return None
    s = str(s).strip()
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})([+-].+)$", s)
    if m:
        s = m.group(1) + ":00" + m.group(2)
    elif re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$", s):
        s = s + ":00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def rec_time(rec):
    return parse_ts(rec.get("ts") or rec.get("start") or rec.get("end"))


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def load_log(path):
    recs = []
    with open(path) as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec["_i"] = i
            recs.append(rec)
    return recs


def profile_log(recs):
    n = len(recs)
    keys = Counter()
    nullish = Counter()
    for r in recs:
        for k, v in r.items():
            if k.startswith("_"):
                continue
            keys[k] += 1
            if v is None or v == "":
                nullish[k] += 1
    n_status = sum(1 for r in recs if r.get("status") is not None)
    n_job = sum(1 for r in recs if r.get("job") and r.get("start"))
    n_task = sum(1 for r in recs if r.get("task_type"))
    n_cost = sum(1 for r in recs if num(r.get("cost_usd")))
    n_cost_pos = sum(1 for r in recs if num(r.get("cost_usd")) and r["cost_usd"] > 0)
    n_model = sum(1 for r in recs if r.get("model"))
    n_vc = sum(1 for r in recs if "verified_correct" in r)
    n_vc_nonnull = sum(1 for r in recs if r.get("verified_correct") is not None)
    n_vb_nonnull = sum(1 for r in recs if r.get("verified_by") is not None)
    status_counts = Counter(str(r.get("status")) for r in recs if r.get("status") is not None)
    task_counts = Counter(str(r.get("task_type")) for r in recs if r.get("task_type"))
    times = [rec_time(r) for r in recs]
    times = [t for t in times if t is not None]
    tmin = min(times).isoformat() if times else None
    tmax = max(times).isoformat() if times else None
    return {
        "n_records": n,
        "n_with_status": n_status,
        "n_job_runs_with_start": n_job,
        "n_with_task_type": n_task,
        "n_with_numeric_cost_usd": n_cost,
        "n_with_positive_cost_usd": n_cost_pos,
        "n_with_model": n_model,
        "n_rows_with_verified_correct_field": n_vc,
        "n_verified_correct_nonnull": n_vc_nonnull,
        "n_verified_by_nonnull": n_vb_nonnull,
        "status_counts": dict(status_counts),
        "task_type_counts": dict(task_counts),
        "t_min": tmin,
        "t_max": tmax,
        "top_fields": [
            {"field": k, "n": c, "nullish": int(nullish[k])}
            for k, c in keys.most_common(25)
        ],
    }


def build_rows(recs):
    """Status-bearing rows with pre-call running totals per (model, task_type)."""
    usable = []
    for r in recs:
        if r.get("status") is None or not r.get("model"):
            continue
        t = rec_time(r)
        usable.append((t or datetime.min, r["_i"], r))
    usable.sort(key=lambda x: (x[0], x[1]))

    running = defaultdict(lambda: {"calls": 0, "cost": 0.0})
    rows = []
    for t, _i, r in usable:
        model = str(r.get("model"))
        task = str(r.get("task_type") or "unknown")
        key = (model, task)
        st = running[key]
        cost_here = float(r["cost_usd"]) if num(r.get("cost_usd")) else 0.0
        rows.append(
            {
                "t": t,
                "i": _i,
                "model": model,
                "task_type": task,
                "calls_so_far": float(st["calls"]),
                "cost_so_far": float(st["cost"]),
                "cost_usd": cost_here,
                "y": 1.0 if r.get("status") == "ok" else 0.0,
                "status": str(r.get("status")),
            }
        )
        st["calls"] += 1
        st["cost"] += cost_here
    return rows


def split_rows(rows, frac):
    n = len(rows)
    n_train = int(n * frac)
    if n_train < 10 or n - n_train < 10:
        raise RuntimeError("not enough status rows for a chronological split")
    return rows[:n_train], rows[n_train:]


def dummy_levels(train, min_model_n):
    mc = Counter(r["model"] for r in train)
    keep_models = sorted(m for m, c in mc.items() if c >= min_model_n)
    tasks = sorted(set(r["task_type"] for r in train))
    return keep_models, tasks, mc


def map_model(m, keep_models):
    return m if m in keep_models else "OTHER"


def design(rows, keep_models, tasks, drop_first=True):
    """Intercept + cost_so_far + calls_so_far + model dummies + task dummies."""
    model_levels = list(keep_models) + ["OTHER"]
    if drop_first:
        model_use = model_levels[1:]  # reference = most-kept? keep list order
        # reference model = first keep_models entry (highest stability: most common)
        # Reorder: most common kept model is reference.
        task_use = tasks[1:] if len(tasks) > 1 else []
        model_use = model_levels[1:]
    else:
        model_use = model_levels
        task_use = tasks
    n = len(rows)
    cols = ["intercept", "cost_so_far", "calls_so_far"]
    cols += ["model=" + m for m in model_use]
    cols += ["task=" + t for t in task_use]
    X = np.zeros((n, len(cols)), dtype=float)
    y = np.array([r["y"] for r in rows], dtype=float)
    cost = np.array([r["cost_so_far"] for r in rows], dtype=float)
    calls = np.array([r["calls_so_far"] for r in rows], dtype=float)
    X[:, 0] = 1.0
    X[:, 1] = cost
    X[:, 2] = calls
    col = {c: j for j, c in enumerate(cols)}
    for i, r in enumerate(rows):
        mk = "model=" + map_model(r["model"], keep_models)
        if mk in col:
            X[i, col[mk]] = 1.0
        tk = "task=" + r["task_type"]
        if tk in col:
            X[i, col[tk]] = 1.0
    return X, y, cols


def standardize_train_test(Xtr, Xte, cols):
    """Z-score cost_so_far and calls_so_far using train moments. sd=0 stays 0."""
    Xtr = Xtr.copy()
    Xte = Xte.copy()
    stats = {}
    for name in ("cost_so_far", "calls_so_far"):
        j = cols.index(name)
        mu = float(Xtr[:, j].mean())
        sd = float(Xtr[:, j].std())
        stats[name] = {"mean": mu, "sd": sd}
        if sd > 0:
            Xtr[:, j] = (Xtr[:, j] - mu) / sd
            Xte[:, j] = (Xte[:, j] - mu) / sd
        else:
            Xtr[:, j] = 0.0
            Xte[:, j] = 0.0
    return Xtr, Xte, stats


def fit_ols(X, y):
    beta, residuals, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    return beta, int(rank)


def predict_lin(X, beta):
    return X @ beta


def r2_score(y, yhat):
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    if ss_tot <= 0:
        return float("nan")
    return 1.0 - ss_res / ss_tot


def sigmoid(z):
    z = np.clip(z, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))


def fit_logistic_irls(X, y, l2=L2, max_iter=40):
    n, d = X.shape
    w = np.zeros(d, dtype=float)
    I = np.eye(d)
    I[0, 0] = 0.0  # do not penalise intercept
    for _ in range(max_iter):
        p = sigmoid(X @ w)
        W = np.clip(p * (1.0 - p), 1e-6, None)
        z = X @ w + (y - p) / W
        XtW = X.T * W
        A = XtW @ X + l2 * I
        b = XtW @ z
        try:
            w_new = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            w_new = np.linalg.lstsq(A, b, rcond=None)[0]
        if float(np.max(np.abs(w_new - w))) < 1e-8:
            w = w_new
            break
        w = w_new
    return w


def mcfadden_r2(X, y, w):
    p = np.clip(sigmoid(X @ w), 1e-12, 1 - 1e-12)
    ll = float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))
    p0 = float(np.clip(y.mean(), 1e-12, 1 - 1e-12))
    ll0 = float(np.sum(y * np.log(p0) + (1 - y) * np.log(1 - p0)))
    if ll0 == 0:
        return float("nan")
    return 1.0 - ll / ll0


def roc_auc(y, scores):
    y = np.asarray(y, dtype=float)
    s = np.asarray(scores, dtype=float)
    n_pos = float(y.sum())
    n_neg = float(len(y) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    y_sorted = y[order]
    s_sorted = s[order]
    # average ranks for ties
    ranks = np.empty(len(y), dtype=float)
    i = 0
    while i < len(y):
        j = i
        while j + 1 < len(y) and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        avg = 0.5 * (i + 1 + j + 1)
        ranks[i : j + 1] = avg
        i = j + 1
    sum_ranks_pos = float(ranks[y_sorted == 1].sum())
    return (sum_ranks_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def subset_cols(X, cols, keep_names):
    idx = [i for i, c in enumerate(cols) if c in keep_names]
    return X[:, idx], [cols[i] for i in idx]


def round_or_none(x, nd=6):
    if x is None:
        return None
    try:
        if x != x:  # nan
            return None
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def main():
    started = time.time()
    started_iso = now_iso()
    out_root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "results")
    out_dir = os.path.join(out_root, QID)
    os.makedirs(out_dir, exist_ok=True)
    result_path = os.path.join(out_dir, "result.json")
    notes_path = os.path.join(out_dir, "notes.md")

    if not os.path.isfile(LOG_PATH):
        result = {
            "qid": QID,
            "title": TITLE,
            "status": "blocked",
            "started": started_iso,
            "finished": now_iso(),
            "runtime_s": round(time.time() - started, 3),
            "method": "Looked for data/routing/job-usage-log.jsonl; file missing.",
            "assumptions": [],
            "headline": {"reason": "missing log file", "quality_labels": False},
            "records_written": [result_path, notes_path],
        }
        with open(result_path, "w") as f:
            json.dump(result, f, indent=2)
        with open(notes_path, "w") as f:
            f.write("# Q281 blocked — log file missing\n")
        print(json.dumps({"qid": QID, "status": "blocked"}))
        return 2

    recs = load_log(LOG_PATH)
    prof = profile_log(recs)
    rows = build_rows(recs)
    train, test = split_rows(rows, TRAIN_FRAC)
    keep_models, tasks, train_model_n = dummy_levels(train, MIN_MODEL_N)
    # most-common kept model / task as reference (drop_first uses list order)
    keep_models = sorted(keep_models, key=lambda m: -train_model_n[m])
    task_n = Counter(r["task_type"] for r in train)
    tasks = sorted(tasks, key=lambda t: -task_n[t])

    Xtr_raw, ytr, cols = design(train, keep_models, tasks, drop_first=True)
    Xte_raw, yte, _ = design(test, keep_models, tasks, drop_first=True)
    Xtr, Xte, zstats = standardize_train_test(Xtr_raw, Xte_raw, cols)

    # intercept-only
    Xtr0, cols0 = subset_cols(Xtr, cols, {"intercept"})
    Xte0, _ = subset_cols(Xte, cols, {"intercept"})
    beta0, _ = fit_ols(Xtr0, ytr)
    w0 = fit_logistic_irls(Xtr0, ytr)
    # categoricals only (no cost/calls)
    cat_names = {"intercept"} | {c for c in cols if c.startswith("model=") or c.startswith("task=")}
    Xtr1, cols1 = subset_cols(Xtr, cols, cat_names)
    Xte1, _ = subset_cols(Xte, cols, cat_names)
    beta1, _ = fit_ols(Xtr1, ytr)
    w1 = fit_logistic_irls(Xtr1, ytr)
    # full
    beta, rank = fit_ols(Xtr, ytr)
    w = fit_logistic_irls(Xtr, ytr)

    yhat_ols = predict_lin(Xte, beta)
    yhat_ols1 = predict_lin(Xte1, beta1)
    yhat_ols0 = predict_lin(Xte0, beta0)
    p = sigmoid(Xte @ w)
    p1 = sigmoid(Xte1 @ w1)
    p0 = sigmoid(Xte0 @ w0)
    p_tr = sigmoid(Xtr @ w)

    auc_full = roc_auc(yte, p)
    auc_cats = roc_auc(yte, p1)
    auc_int = roc_auc(yte, p0)
    r2_full = r2_score(yte, yhat_ols)
    r2_cats = r2_score(yte, yhat_ols1)
    r2_int = r2_score(yte, yhat_ols0)
    r2_tr = r2_score(ytr, predict_lin(Xtr, beta))
    auc_tr = roc_auc(ytr, p_tr)
    mcf_te = mcfadden_r2(Xte, yte, w)
    mcf_tr = mcfadden_r2(Xtr, ytr, w)

    col_index = {c: i for i, c in enumerate(cols)}
    b_cost = float(beta[col_index["cost_so_far"]])
    b_calls = float(beta[col_index["calls_so_far"]])
    w_cost = float(w[col_index["cost_so_far"]])
    w_calls = float(w[col_index["calls_so_far"]])

    # Predicted P(ok) shift at +1 SD of each continuous feature, others at train mean.
    x_mean = Xtr.mean(axis=0)
    p_mean = float(sigmoid(x_mean @ w))
    x_cost = x_mean.copy()
    x_cost[col_index["cost_so_far"]] = x_mean[col_index["cost_so_far"]] + 1.0
    x_calls = x_mean.copy()
    x_calls[col_index["calls_so_far"]] = x_mean[col_index["calls_so_far"]] + 1.0
    p_cost_plus1sd = float(sigmoid(x_cost @ w))
    p_calls_plus1sd = float(sigmoid(x_calls @ w))

    # Top model logistic effects (vs reference = most common train model)
    model_effects = []
    for c in cols:
        if c.startswith("model="):
            model_effects.append({"level": c.split("=", 1)[1], "log_odds": round(float(w[col_index[c]]), 4)})
    model_effects.sort(key=lambda d: d["log_odds"])
    task_effects = []
    for c in cols:
        if c.startswith("task="):
            task_effects.append({"level": c.split("=", 1)[1], "log_odds": round(float(w[col_index[c]]), 4)})
    task_effects.sort(key=lambda d: d["log_odds"])

    # --- routing / config choice on the later slice ---
    # Primary: among models with enough train AND later-slice mass, pick
    # the one with the highest mean training predicted P(ok) and compare
    # its later-slice ok-rate to the mix of the same eligible models.
    # That does not assign a 26-row ok-rate to thousands of other rows.
    # Per-task_type recommendations are reported only when the chosen
    # model also has >= MIN_TEST_PAIR later-slice rows of that type.
    MIN_TRAIN_MODEL = 30
    MIN_TEST_MODEL = 50
    MIN_TRAIN_PAIR = 20
    MIN_TEST_PAIR = 30

    p_tr_full = sigmoid(Xtr @ w)
    tr_m = defaultdict(lambda: [0.0, 0.0, 0])  # pred_sum, y_sum, n
    tr_tm = defaultdict(lambda: [0.0, 0.0, 0])
    te_m = defaultdict(lambda: [0.0, 0])
    te_t = defaultdict(lambda: [0.0, 0])
    te_tm = defaultdict(lambda: [0.0, 0])
    for r, pr in zip(train, p_tr_full):
        m = map_model(r["model"], keep_models)
        t = r["task_type"]
        tr_m[m][0] += float(pr)
        tr_m[m][1] += r["y"]
        tr_m[m][2] += 1
        tr_tm[(t, m)][0] += float(pr)
        tr_tm[(t, m)][1] += r["y"]
        tr_tm[(t, m)][2] += 1
    for r in test:
        m = map_model(r["model"], keep_models)
        t = r["task_type"]
        te_m[m][0] += r["y"]
        te_m[m][1] += 1
        te_t[t][0] += r["y"]
        te_t[t][1] += 1
        te_tm[(t, m)][0] += r["y"]
        te_tm[(t, m)][1] += 1

    eligible = [
        m
        for m in (list(keep_models) + ["OTHER"])
        if tr_m[m][2] >= MIN_TRAIN_MODEL and te_m[m][1] >= MIN_TEST_MODEL
    ]
    eligible_ranked = sorted(
        eligible,
        key=lambda m: (tr_m[m][0] / tr_m[m][2] if tr_m[m][2] else -1, tr_m[m][2]),
        reverse=True,
    )
    mix_ok = float(yte.mean()) if len(yte) else float("nan")
    if eligible_ranked:
        best = eligible_ranked[0]
        policy_ok = te_m[best][0] / te_m[best][1]
        mix_eligible = sum(te_m[m][0] for m in eligible) / sum(te_m[m][1] for m in eligible)
        n_best_test = te_m[best][1]
        top3 = eligible_ranked[:3]
        bot3 = eligible_ranked[-3:] if len(eligible_ranked) >= 3 else eligible_ranked
        top3_ok = sum(te_m[m][0] for m in top3) / sum(te_m[m][1] for m in top3)
        bot3_ok = sum(te_m[m][0] for m in bot3) / sum(te_m[m][1] for m in bot3)
    else:
        best = None
        policy_ok = float("nan")
        mix_eligible = float("nan")
        n_best_test = 0
        top3, bot3 = [], []
        top3_ok = float("nan")
        bot3_ok = float("nan")
    delta_ok = (
        policy_ok - mix_ok
        if policy_ok == policy_ok and mix_ok == mix_ok
        else float("nan")
    )
    delta_ok_eligible = (
        policy_ok - mix_eligible
        if policy_ok == policy_ok and mix_eligible == mix_eligible
        else float("nan")
    )

    covered_tasks = []
    pair_w_num = 0.0
    pair_w_den = 0
    for t, (ok_t, n_t) in sorted(te_t.items(), key=lambda kv: -kv[1][1]):
        cands = []
        for m in list(keep_models) + ["OTHER"]:
            if tr_tm[(t, m)][2] < MIN_TRAIN_PAIR:
                continue
            if te_tm[(t, m)][1] < MIN_TEST_PAIR:
                continue
            mean_p = tr_tm[(t, m)][0] / tr_tm[(t, m)][2]
            cands.append((mean_p, tr_tm[(t, m)][2], m))
        if not cands:
            continue
        cands.sort(reverse=True)
        mstar = cands[0][2]
        n_m = te_tm[(t, mstar)][1]
        p_m = te_tm[(t, mstar)][0] / n_m
        p_mix = ok_t / n_t
        covered_tasks.append(
            {
                "task_type": t,
                "n_test": int(n_t),
                "mix_ok_rate": round(p_mix, 4),
                "recommended_model": mstar,
                "recommended_n_test": int(n_m),
                "recommended_ok_rate": round(p_m, 4),
                "delta": round(p_m - p_mix, 4),
            }
        )
        pair_w_num += (p_m - p_mix) * n_m
        pair_w_den += n_m
    pair_delta = pair_w_num / pair_w_den if pair_w_den else float("nan")

    train_task_mix = {
        t: round(c / len(train), 4)
        for t, c in Counter(r["task_type"] for r in train).most_common()
    }
    test_task_mix = {
        t: round(c / len(test), 4)
        for t, c in Counter(r["task_type"] for r in test).most_common()
    }

    collection_cost = float(sum(r["cost_usd"] for r in train))
    # Spec net benefit: improvement in outcome/cost minus collection cost.
    # Status-bearing rows are almost all $0, so outcome/cost is not a
    # dollar ratio; we report the sign of the later-slice ok-rate delta
    # given a ~$0 collection cost. Primary delta is the well-powered
    # model-level comparison (recommended eligible model vs full mix).
    if delta_ok != delta_ok:
        net_sign = "unknown"
    elif delta_ok > 0:
        net_sign = "positive"
    elif delta_ok < 0:
        net_sign = "negative"
    else:
        net_sign = "zero"

    ok_tr = float(ytr.mean())
    ok_te = float(yte.mean())
    cost_sd = zstats["cost_so_far"]["sd"]
    calls_sd = zstats["calls_so_far"]["sd"]

    headline = {
        "outcome_definition": (
            "log status only (ok vs not-ok). The logs carry status and cost "
            "and NO quality labels — this is not a quality prediction."
        ),
        "quality_labels_in_log": False,
        "verified_correct_nonnull": prof["n_verified_correct_nonnull"],
        "n_log_records": prof["n_records"],
        "n_status_rows_used": len(rows),
        "n_train": len(train),
        "n_test": len(test),
        "train_frac": TRAIN_FRAC,
        "ok_rate_train": round(ok_tr, 4),
        "ok_rate_test": round(ok_te, 4),
        "heldout_auc_logistic": round_or_none(auc_full, 4),
        "heldout_auc_categoricals_only": round_or_none(auc_cats, 4),
        "heldout_auc_intercept_only": round_or_none(auc_int, 4),
        "heldout_r2_ols": round_or_none(r2_full, 4),
        "heldout_r2_categoricals_only": round_or_none(r2_cats, 4),
        "heldout_r2_intercept_only": round_or_none(r2_int, 4),
        "train_auc_logistic": round_or_none(auc_tr, 4),
        "train_r2_ols": round_or_none(r2_tr, 4),
        "mcfadden_r2_train": round_or_none(mcf_tr, 4),
        "mcfadden_r2_test": round_or_none(mcf_te, 4),
        "effect_cost_so_far_log_odds_per_sd": round_or_none(w_cost, 4),
        "effect_calls_so_far_log_odds_per_sd": round_or_none(w_calls, 4),
        "effect_cost_so_far_ols_per_sd": round_or_none(b_cost, 4),
        "effect_calls_so_far_ols_per_sd": round_or_none(b_calls, 4),
        "cost_so_far_train_sd_usd": round_or_none(cost_sd, 8),
        "calls_so_far_train_sd": round_or_none(calls_sd, 4),
        "p_ok_at_train_mean_features": round_or_none(p_mean, 4),
        "p_ok_at_cost_so_far_plus_1sd": round_or_none(p_cost_plus1sd, 4),
        "p_ok_at_calls_so_far_plus_1sd": round_or_none(p_calls_plus1sd, 4),
        "reference_model": keep_models[0] if keep_models else None,
        "reference_task_type": tasks[0] if tasks else None,
        "n_model_levels_kept": len(keep_models),
        "routing_ok_rate_actual_mix": round_or_none(mix_ok, 4),
        "routing_recommended_model": best,
        "routing_recommended_n_test": int(n_best_test),
        "routing_ok_rate_recommended": round_or_none(policy_ok, 4),
        "routing_ok_rate_eligible_mix": round_or_none(mix_eligible, 4),
        "routing_delta_ok_rate_vs_full_mix": round_or_none(delta_ok, 4),
        "routing_delta_ok_rate_vs_eligible_mix": round_or_none(delta_ok_eligible, 4),
        "n_eligible_models_train30_test50": len(eligible_ranked),
        "routing_top3_models": top3,
        "routing_bottom3_models": bot3,
        "routing_top3_ok_rate": round_or_none(top3_ok, 4),
        "routing_bottom3_ok_rate": round_or_none(bot3_ok, 4),
        "routing_per_task_n_identified": len(covered_tasks),
        "routing_per_task_delta_weighted_by_recommended_n": round_or_none(pair_delta, 4),
        "train_task_type_mix": train_task_mix,
        "test_task_type_mix": test_task_mix,
        "predictor_collection_cost_usd": round(collection_cost, 6),
        "net_benefit_sign": net_sign,
        "net_benefit": (
            "Later-slice log-status ok-rate of the model with the highest training "
            "predicted P(ok) among models with >=30 train and >=50 later-slice rows, "
            "minus the later-slice mix, with predictor collection cost equal to the "
            "sum of logged cost_usd on the training slice. Sign is the sign of that "
            "ok-rate delta; collection cost is essentially zero because status-bearing "
            "rows are free-lane calls. This is NOT a quality improvement."
        ),
    }

    assumptions = [
        "Outcome is the logged status field only (1 if status=='ok', else 0). The log has no quality labels: verified_correct and verified_by are null on every row that carries them. CHECKS.md and the assignment both require this limit in the headline and the notes.",
        "Unit of analysis is a status-bearing per-call / per-job row with a model field. Job-run quota records without status are out of this regression (they are used by Q505).",
        "cost_so_far and calls_so_far are running totals of prior rows with the same (model, task_type), in timestamp order (file order as tie-break). Missing cost_usd is treated as 0.",
        "Chronological split: first 70% of status rows by time are train, last 30% are held-out. No shuffle.",
        "Models with fewer than 30 training rows collapse to OTHER. Dummy reference levels are the most common training model and task_type.",
        "Logistic regression is IRLS (hand-rolled) with L2=0.01 on non-intercept weights. OLS is numpy.linalg.lstsq on the same standardized design. Continuous features are z-scored on train.",
        "Routing value is observational. Primary comparison: among models with >=30 training rows and >=50 later-slice rows, pick the one with the highest mean training predicted P(ok) and compare its later-slice ok-rate to the full mix and to the mix of those eligible models. Per-task_type recommendations are shown only when the chosen model also has >=30 later-slice rows of that type; those deltas are weighted by the recommended model's later-slice n, not by the task_type's n (a 26-row ok-rate is not assigned to thousands of other rows).",
        "Predictor collection cost is the sum of logged cost_usd on the training slice. That is the cost of the records the predictor saw, not a separate labelling budget.",
        "The spec's dollar net-benefit formula is not fully recoverable: status-bearing rows have essentially $0 cost_usd, so there is no outcome/cost dollar ratio to subtract collection cost from. Closest faithful reading is the sign of the later-slice ok-rate delta at ~$0 collection cost.",
        "Card C-meta-models-model-learning is not in the staged cards/ directory; the question text is taken from TOP10-TEST-SPECS-DRAFT.md and data/backlog-full.json.",
    ]

    method = (
        "Profiled job-usage-log.jsonl, then on every row with a logged status and "
        "model built the pre-call features (cost so far, calls so far) for that "
        "(model, task_type), dummy-coded model and task_type, fit a hand-rolled "
        "IRLS logistic and a least-squares linear probability model on the earliest "
        "70% of rows, and scored held-out AUC / R2 plus a later-slice routing "
        "policy against the mix actually used. Outcome is log status, not quality."
    )

    result = {
        "qid": QID,
        "title": TITLE,
        "status": "done",
        "started": started_iso,
        "finished": now_iso(),
        "runtime_s": round(time.time() - started, 3),
        "method": method,
        "assumptions": assumptions,
        "headline": headline,
        "records_written": [result_path, notes_path],
        "profile": prof,
        "routing_by_task_type": covered_tasks,
        "model_log_odds_vs_reference_lowest": model_effects[:5],
        "model_log_odds_vs_reference_highest": model_effects[-5:],
        "task_type_log_odds_vs_reference": task_effects,
        "ols_rank": rank,
        "n_design_cols": len(cols),
    }

    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)

    # notes — include the mandatory quality-label limit in prose
    cost_deg = (
        "nearly degenerate (train SD of cost_so_far is "
        f"{cost_sd:.8f} USD)"
        if cost_sd < 1e-6
        else f"train SD {cost_sd:.6f} USD"
    )
    notes = f"""# {QID} — {TITLE}

Implements spec item 4 (TOP10-TEST-SPECS-DRAFT.md) against card
C-meta-models-model-learning, reduced per CHECKS.md. Data:
`data/routing/job-usage-log.jsonl`.

## Mandatory limit

**The logs carry status and cost and NO quality labels.** Outcome in
this test is the logged `status` field (`ok` vs anything else:
ratelimit, refused, empty, error, timeout, truncated, auth, …).
`verified_correct` is present on {prof["n_rows_with_verified_correct_field"]}
rows and non-null on {prof["n_verified_correct_nonnull"]};
`verified_by` is non-null on {prof["n_verified_by_nonnull"]}. A higher
predicted P(ok) is a higher chance the logger wrote `status=ok`, not a
higher chance the answer was good. That limit is also in the headline.

## Data profile (computed, not assumed)

- {prof["n_records"]} records, times {prof["t_min"]} → {prof["t_max"]}.
- Two shapes, mixed in one file:
  - job runs with `start`/`end`/`model` and quota deltas
    (`5h_used_before`/`after`, `wk_used_before`/`after`): 
    {prof["n_job_runs_with_start"]} rows with `start`.
  - per-call rows with `task_type`/`provider`/`status`/`cost_usd`/`ts`
    (and a richer `row_kind=call` variant with route, latency,
    failure_type): {prof["n_with_status"]} rows with `status`,
    {prof["n_with_task_type"]} with `task_type`.
- `cost_usd` is numeric on {prof["n_with_numeric_cost_usd"]} rows and
  **positive on only {prof["n_with_positive_cost_usd"]}**. Almost all
  status-bearing rows are free-lane calls at $0. Paid-call rows
  (`job=hydra paid call`) carry dollars and **no status**.
- Status mix: {json.dumps(prof["status_counts"], sort_keys=True)}.
- Task types: {json.dumps(prof["task_type_counts"], sort_keys=True)}.
- Top fields (n, nullish): {json.dumps(prof["top_fields"][:12])}.

## Method

Status-bearing rows with a `model` ({len(rows)}) sorted by timestamp.
For each row the features are the running totals of prior rows with the
same `(model, task_type)`: `cost_so_far`, `calls_so_far`, plus dummy
codes for model (levels with ≥{MIN_MODEL_N} train rows; rest OTHER) and
task_type (missing → `unknown`). Chronological split: first
{TRAIN_FRAC:.0%} train (n={len(train)}), last {100 - TRAIN_FRAC * 100:.0f}%
held-out (n={len(test)}).

Two estimators, numpy only:

1. Least-squares linear probability (numpy.linalg.lstsq) — held-out R².
2. Hand-rolled logistic IRLS with L2={L2} — held-out AUC.

Nested versions (intercept only; model+task_type only; full) show how
much `cost_so_far` and `calls_so_far` add on top of the categoricals.
Continuous features are z-scored on train so logistic/OLS coefficients
on those two columns are per training SD.

Routing/config value (spec): among models with ≥30 train and ≥50
later-slice rows, pick the one with the highest mean training
predicted P(ok) and compare its later-slice ok-rate to the mix
actually used. Per-task_type picks are reported only when the chosen
model has ≥30 later-slice rows of that type. Net benefit sign is the
sign of the model-level ok-rate delta, minus collection cost = sum of
training-slice `cost_usd` ({collection_cost:.6f} USD).

## What the numbers mean

- Held-out logistic AUC **{round_or_none(auc_full, 4)}** vs categoricals-only
  **{round_or_none(auc_cats, 4)}** vs intercept-only
  **{round_or_none(auc_int, 4)}**. Intercept-only should sit at 0.5;
  the jump from intercept to categoricals is the model/task_type base
  rate. The increment from categoricals to full is the value of cost
  so far and calls so far.
- Held-out OLS R² **{round_or_none(r2_full, 4)}** vs categoricals-only
  **{round_or_none(r2_cats, 4)}**.
- Effect of cost so far: {round_or_none(w_cost, 4)} log-odds per train SD
  ({cost_deg}). Predicted P(ok) at mean features
  {round_or_none(p_mean, 4)} vs +1 SD cost
  {round_or_none(p_cost_plus1sd, 4)}.
- Effect of calls so far: {round_or_none(w_calls, 4)} log-odds per train SD
  (SD={round_or_none(calls_sd, 4)}). Predicted P(ok) at +1 SD calls
  {round_or_none(p_calls_plus1sd, 4)}.
- Later-slice ok-rate, actual mix: **{round_or_none(mix_ok, 4)}**.
  Recommended model `{best}` (n_test={int(n_best_test)}):
  **{round_or_none(policy_ok, 4)}**. Delta vs full mix:
  **{round_or_none(delta_ok, 4)}**. Vs eligible-model mix:
  **{round_or_none(delta_ok_eligible, 4)}**. Top-3 later ok-rate
  {round_or_none(top3_ok, 4)} vs bottom-3 {round_or_none(bot3_ok, 4)}.
  Net-benefit sign: **{net_sign}**. Collection cost
  {collection_cost:.6f} USD.
- Train ok-rate {round(ok_tr, 4)}, test ok-rate {round(ok_te, 4)}
  (base rates can shift across the split; that is why intercept-only
  AUC on a shifted test set can differ slightly from 0.5 when scores
  are constant — here intercept-only uses a constant, so AUC is 0.5
  whenever both classes appear).

## Limits

- Status is not quality. Soak and ceiling rows dominate; `ok` there
  means the provider returned a completion, not that a judge scored
  the answer. Do not read the AUC as "the predictor finds good models".
- `cost_so_far` is {cost_deg}. Paid dollars live on a different row
  shape with no status, so this regression cannot speak to dollar
  cost-awareness. That is a log-schema gap, not a modelling choice.
- Routing delta is observational. Later-slice tasks were not randomly
  assigned to models; the recommended model's later ok-rate may mix
  selection with model skill. Chronological shift: ceiling is
  {train_task_mix.get("ceiling", 0):.1%} of train and
  {test_task_mix.get("ceiling", 0):.1%} of test; soak is
  {train_task_mix.get("soak", 0):.1%} of train and
  {test_task_mix.get("soak", 0):.1%} of test. That is why train
  R²/AUC overstate held-out fit.
- The spec asked for net benefit in outcome/cost minus collection
  cost. Dollars are not on the status rows, so the sign is reported
  on the ok-rate delta instead of a dollar net. Closest faithful
  reading; stated as an assumption.
- Card C-meta-models-model-learning is not staged under cards/; the
  protocol follows the spec text plus CHECKS.md's reduced outcome.
"""
    with open(notes_path, "w") as f:
        f.write(notes)

    print(
        json.dumps(
            {
                "qid": QID,
                "status": "done",
                "heldout_auc": round_or_none(auc_full, 4),
                "heldout_r2": round_or_none(r2_full, 4),
                "delta_ok": round_or_none(delta_ok, 4),
                "recommended_model": best,
                "net_benefit_sign": net_sign,
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
