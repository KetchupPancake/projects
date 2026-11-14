#!/usr/bin/env python3
"""Q505 — Cost prediction under verification and retries (Hydra, routing).

Implements spec item 5 in TOP10-TEST-SPECS-DRAFT.md against card
C-scout-before-you-route. Shares the job-usage-log with Q281.

Split reconstructed runs at escalating retry budgets. Per tier: outcome
rate (logged status ok — not quality) plus median and p90 quota cost.
Headline states whether cost-under-retries drops >=20% at some tier,
and which. A small with/without-predictor replay answers the spec's
"does per-query prediction still pay" question.

Usage: q505.py [output_root]   (default ./results)
Writes <output_root>/Q505/result.json and notes.md.
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

QID = "Q505"
TITLE = "Cost prediction under verification and retries"
LOG_PATH = os.path.join("data", "routing", "job-usage-log.jsonl")
CHAIN_GAP_S = 60
TRAIN_FRAC = 0.70
MIN_MODEL_N = 20
L2 = 1e-2
TIERS = [1, 2, 3, 4, 5, 8, 10]
DROP_THRESHOLD = 0.20


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
    n_status = sum(1 for r in recs if r.get("status") is not None)
    n_start = sum(1 for r in recs if r.get("start"))
    n_quota = 0
    n_attempt = sum(1 for r in recs if "attempt" in r or "retried" in r)
    n_vc_nonnull = sum(1 for r in recs if r.get("verified_correct") is not None)
    status_counts = Counter(str(r.get("status")) for r in recs if r.get("status") is not None)
    times = [t for t in (rec_time(r) for r in recs) if t]
    n_cost_pos = sum(1 for r in recs if num(r.get("cost_usd")) and r["cost_usd"] > 0)
    for r in recs:
        if quota_5h(r) is not None:
            n_quota += 1
    return {
        "n_records": n,
        "n_with_status": n_status,
        "n_with_start": n_start,
        "n_with_5h_quota_delta": n_quota,
        "n_with_attempt_or_retried_field": n_attempt,
        "n_verified_correct_nonnull": n_vc_nonnull,
        "n_positive_cost_usd": n_cost_pos,
        "status_counts": dict(status_counts),
        "t_min": min(times).isoformat() if times else None,
        "t_max": max(times).isoformat() if times else None,
    }


def quota_5h(r):
    b, a = r.get("5h_used_before"), r.get("5h_used_after")
    if num(b) and num(a):
        d = float(a) - float(b)
        if d < 0:
            return None
        return d
    return None


def quota_wk(r):
    b, a = r.get("wk_used_before"), r.get("wk_used_after")
    if num(b) and num(a):
        d = float(a) - float(b)
        if d < 0:
            return None
        return d
    return None


def family_key(job):
    """Group revision/retry series without merging distinct gui-plan variants."""
    s = (job or "").strip()
    if not s:
        return ""
    sl = re.sub(r"\s+", " ", s).lower()
    sl = re.sub(r"\([^)]*\)", " ", sl)
    if ":" in sl:
        left, right = sl.split(":", 1)
        left = left.strip()
        right = right.strip()
        left = re.sub(r"-v\d+(?:\.\d+)*", "", left)
        left = re.sub(r"-2026\d{4}", "", left)
        left = re.sub(r"-(?:review|fix\d*[a-z]?|r\d+)$", "", left)
        left = re.sub(r"-+$", "", left).strip()
        if re.search(r"\b(free|paid|canary)\b", right):
            right_n = re.sub(r"\b(?:codex|claude-code|claude|twin)\b", " ", right)
            right_n = re.sub(r"\b(?:review|build|draft|fix|sign-off|re-?check|re-?review|final)\b", " ", right_n)
            right_n = re.sub(r"\br\d+\b", " ", right_n)
            right_n = re.sub(r"\s+", " ", right_n).strip()
            return (left + ": " + right_n).strip() if right_n else left
        return left or sl
    sl = re.sub(r"\bv\d+(?:\.\d+)*\b", " ", sl)
    sl = re.sub(r"\b(?:round\s*\d+|r\d+)\b", " ", sl)
    sl = re.sub(r"\b(?:codex|claude-code|claude)\b", " ", sl)
    sl = re.sub(r"\b(?:re-?check|re-?review|review|draft|fix|refine)\b", " ", sl)
    sl = re.sub(r"\s+", " ", sl).strip(" :-/")
    return sl if len(sl) >= 6 else re.sub(r"\s+", " ", s).strip().lower()


def percentile(xs, p):
    if not xs:
        return None
    arr = np.sort(np.asarray(xs, dtype=float))
    if arr.size == 1:
        return float(arr[0])
    idx = (arr.size - 1) * p
    lo = int(np.floor(idx))
    hi = int(np.ceil(idx))
    if lo == hi:
        return float(arr[lo])
    w = idx - lo
    return float(arr[lo] * (1.0 - w) + arr[hi] * w)


def median(xs):
    return percentile(xs, 0.5)


def p90(xs):
    return percentile(xs, 0.9)


def sigmoid(z):
    z = np.clip(z, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))


def fit_logistic_irls(X, y, l2=L2, max_iter=40):
    n, d = X.shape
    w = np.zeros(d, dtype=float)
    I = np.eye(d)
    I[0, 0] = 0.0
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


def r2_score(y, yhat):
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    if ss_tot <= 0:
        return float("nan")
    return 1.0 - ss_res / ss_tot


def round_or_none(x, nd=4):
    if x is None:
        return None
    try:
        if x != x:
            return None
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def build_call_chains(recs, gap_s=CHAIN_GAP_S):
    """Consecutive same (model, provider, task_type) within gap_s seconds."""
    items = []
    for r in recs:
        if r.get("status") is None or not r.get("model"):
            continue
        t = rec_time(r)
        if t is None:
            continue
        items.append((t, r["_i"], r))
    items.sort(key=lambda x: (x[0], x[1]))
    chains = []
    cur = None
    for t, _i, r in items:
        key = (str(r.get("model")), str(r.get("provider") or ""), str(r.get("task_type") or "unknown"))
        rec = {
            "t": t,
            "model": key[0],
            "provider": key[1],
            "task_type": key[2],
            "status": str(r.get("status")),
            "ok": r.get("status") == "ok",
            "cost_usd": float(r["cost_usd"]) if num(r.get("cost_usd")) else 0.0,
            "latency_s": float(r["latency_s"]) if num(r.get("latency_s")) else 0.0,
            "quota_5h": quota_5h(r),
        }
        if cur is None:
            cur = {"key": key, "recs": [rec]}
            continue
        dt = (t - cur["recs"][-1]["t"]).total_seconds()
        # Extend only on a fail-then-retry: same config, close in time,
        # previous attempt was not ok. An ok ends the run so a later
        # soak hit of the same model is a new run, not a retry.
        if (
            key == cur["key"]
            and 0 <= dt <= gap_s
            and not cur["recs"][-1]["ok"]
        ):
            cur["recs"].append(rec)
        else:
            chains.append(cur)
            cur = {"key": key, "recs": [rec]}
    if cur:
        chains.append(cur)
    return chains


def build_job_families(recs):
    groups = defaultdict(list)
    for r in recs:
        if not r.get("start"):
            continue
        t = rec_time(r) or datetime.min
        groups[family_key(r.get("job"))].append((t, r["_i"], r))
    families = []
    for k, items in groups.items():
        if not k:
            continue
        items.sort(key=lambda x: (x[0], x[1]))
        recs_n = []
        for t, _i, r in items:
            recs_n.append(
                {
                    "t": t,
                    "job": r.get("job"),
                    "model": str(r.get("model") or ""),
                    "status": r.get("status"),
                    "ok": r.get("status") == "ok",
                    "has_status": r.get("status") is not None,
                    "cost_usd": float(r["cost_usd"]) if num(r.get("cost_usd")) else 0.0,
                    "quota_5h": quota_5h(r),
                    "quota_wk": quota_wk(r),
                }
            )
        families.append({"key": k, "recs": recs_n})
    return families


def replay_chain(recs, k, early_stop=True, cost_key="attempts"):
    """Truncate a run at budget k. Early-stop at first ok when status exists."""
    used = []
    accepted = False
    saw_status = False
    cap = len(recs) if k is None else min(int(k), len(recs))
    for rec in recs[:cap]:
        used.append(rec)
        if rec.get("has_status", rec.get("status") is not None):
            saw_status = True
        if rec.get("ok"):
            accepted = True
            if early_stop:
                break
    if cost_key == "attempts":
        cost = float(len(used))
    elif cost_key == "latency_s":
        cost = float(sum(x.get("latency_s") or 0.0 for x in used))
    elif cost_key == "cost_usd":
        cost = float(sum(x.get("cost_usd") or 0.0 for x in used))
    elif cost_key == "quota_5h":
        vals = [x.get("quota_5h") for x in used if x.get("quota_5h") is not None]
        cost = float(sum(vals)) if vals else 0.0
    else:
        raise ValueError(cost_key)
    return {
        "accepted": accepted,
        "saw_status": saw_status,
        "n_used": len(used),
        "cost": cost,
        "full_len": len(recs),
    }


def tier_table(runs, cost_key, early_stop=True, require_status=True):
    """runs: list of rec-lists. Tiers plus unconstrained (None)."""
    ks = list(TIERS) + [None]
    rows = []
    for k in ks:
        costs = []
        n_acc = 0
        n_out = 0
        n_all = 0
        total_cost = 0.0
        total_cost_acc = 0.0
        for recs in runs:
            if not recs:
                continue
            n_all += 1
            r = replay_chain(recs, k, early_stop=early_stop, cost_key=cost_key)
            costs.append(r["cost"])
            total_cost += r["cost"]
            if require_status and not r["saw_status"]:
                continue
            n_out += 1
            if r["accepted"]:
                n_acc += 1
                total_cost_acc += r["cost"]
        outcome_rate = (n_acc / n_out) if n_out else None
        cpa = (total_cost / n_acc) if n_acc else None  # spend on all runs / accepts
        rows.append(
            {
                "tier": "unconstrained" if k is None else k,
                "k": k,
                "n_runs": n_all,
                "n_with_status_outcome": n_out,
                "n_accepted": n_acc,
                "outcome_rate": round_or_none(outcome_rate, 4),
                "median_cost": round_or_none(median(costs), 4),
                "p90_cost": round_or_none(p90(costs), 4),
                "mean_cost": round_or_none(float(np.mean(costs)) if costs else None, 4),
                "cost_per_accepted": round_or_none(cpa, 4),
                "total_cost": round_or_none(total_cost, 4),
                "cost_key": cost_key,
            }
        )
    return rows


def drop_vs_unconstrained(table, metric):
    """Largest k (least cap) whose metric is >=20% below unconstrained.

    For unconstrained-baseline drops, lower cost is a cap. metric is a
    field on the tier rows (median_cost, p90_cost, cost_per_accepted).
    """
    by = {row["tier"]: row for row in table}
    base = by.get("unconstrained")
    if not base or base.get(metric) in (None, 0):
        return {
            "drops_ge_20pct": False,
            "metric": metric,
            "at_tier": None,
            "drop_pct": None,
            "unconstrained_value": base.get(metric) if base else None,
            "reason": "no unconstrained baseline",
        }
    base_v = base[metric]
    hits = []
    for row in table:
        if row["tier"] == "unconstrained":
            continue
        v = row.get(metric)
        if v is None or base_v == 0:
            continue
        drop = (base_v - v) / abs(base_v)
        if drop >= DROP_THRESHOLD:
            hits.append((row["k"], drop, v, row.get("outcome_rate")))
    if not hits:
        # report the max drop even if < 20%
        best = None
        for row in table:
            if row["tier"] == "unconstrained":
                continue
            v = row.get(metric)
            if v is None:
                continue
            drop = (base_v - v) / abs(base_v)
            if best is None or drop > best[1]:
                best = (row["k"], drop, v, row.get("outcome_rate"))
        return {
            "drops_ge_20pct": False,
            "metric": metric,
            "at_tier": None,
            "drop_pct": round_or_none(best[1] * 100 if best else None, 2),
            "best_tier_even_if_below_20": best[0] if best else None,
            "unconstrained_value": round_or_none(base_v, 4),
            "outcome_rate_unconstrained": base.get("outcome_rate"),
        }
    # largest k that still saves 20% (smallest outcome-rate damage among savers)
    hits.sort()
    k, drop, v, orate = hits[-1]
    return {
        "drops_ge_20pct": True,
        "metric": metric,
        "at_tier": k,
        "drop_pct": round(drop * 100, 2),
        "tier_value": round_or_none(v, 4),
        "unconstrained_value": round_or_none(base_v, 4),
        "outcome_rate_at_tier": orate,
        "outcome_rate_unconstrained": base.get("outcome_rate"),
    }


def drop_cpa_vs_single_shot(table):
    """Does allowing retries cut cost-per-accepted by >=20% vs K=1?"""
    by = {row["tier"]: row for row in table}
    base = by.get(1)
    if not base or not base.get("cost_per_accepted"):
        return {"drops_ge_20pct": False, "reason": "no k=1 cost_per_accepted"}
    base_v = base["cost_per_accepted"]
    hits = []
    for row in table:
        if row["tier"] == 1:
            continue
        v = row.get("cost_per_accepted")
        if v is None:
            continue
        drop = (base_v - v) / abs(base_v)
        if drop >= DROP_THRESHOLD:
            hits.append((row["tier"], drop, v, row.get("outcome_rate")))
    if not hits:
        best = None
        for row in table:
            if row["tier"] == 1:
                continue
            v = row.get("cost_per_accepted")
            if v is None:
                continue
            drop = (base_v - v) / abs(base_v)
            if best is None or drop > best[1]:
                best = (row["tier"], drop, v, row.get("outcome_rate"))
        return {
            "drops_ge_20pct": False,
            "metric": "cost_per_accepted_vs_k1",
            "at_tier": None,
            "drop_pct": round_or_none(best[1] * 100 if best else None, 2),
            "best_tier_even_if_below_20": best[0] if best else None,
            "k1_value": round_or_none(base_v, 4),
            "outcome_rate_k1": base.get("outcome_rate"),
        }
    # prefer unconstrained if it qualifies, else largest drop
    hits.sort(key=lambda x: (x[0] != "unconstrained", -x[1]))
    tier, drop, v, orate = hits[0]
    return {
        "drops_ge_20pct": True,
        "metric": "cost_per_accepted_vs_k1",
        "at_tier": tier,
        "drop_pct": round(drop * 100, 2),
        "tier_value": round_or_none(v, 4),
        "k1_value": round_or_none(base_v, 4),
        "outcome_rate_at_tier": orate,
        "outcome_rate_k1": base.get("outcome_rate"),
    }


def first_attempt_design(chains, keep_models, tasks):
    model_use = keep_models[1:]  # drop most common
    task_use = tasks[1:] if len(tasks) > 1 else []
    cols = ["intercept"] + ["model=" + m for m in model_use] + ["task=" + t for t in task_use]
    n = len(chains)
    X = np.zeros((n, len(cols)), dtype=float)
    y = np.zeros(n, dtype=float)
    X[:, 0] = 1.0
    col = {c: j for j, c in enumerate(cols)}
    keep_set = set(keep_models)
    for i, ch in enumerate(chains):
        rec = ch["recs"][0]
        y[i] = 1.0 if rec["ok"] else 0.0
        m = rec["model"] if rec["model"] in keep_set else "OTHER"
        mk = "model=" + m
        if mk in col:
            X[i, col[mk]] = 1.0
        tk = "task=" + rec["task_type"]
        if tk in col:
            X[i, col[tk]] = 1.0
    return X, y, cols


def predictor_sim(chains, p_hat, threshold, k=3, cost_key="attempts"):
    """Skip chains whose first-attempt predicted P(ok) < threshold."""
    n_started = 0
    n_acc = 0
    total_cost = 0.0
    for ch, p in zip(chains, p_hat):
        if p < threshold:
            continue
        n_started += 1
        r = replay_chain(ch["recs"], k, early_stop=True, cost_key=cost_key)
        total_cost += r["cost"]
        if r["accepted"]:
            n_acc += 1
    return {
        "threshold": threshold,
        "k": k,
        "n_chains": len(chains),
        "n_started": n_started,
        "n_skipped": len(chains) - n_started,
        "n_accepted": n_acc,
        "outcome_rate_among_started": round_or_none(n_acc / n_started if n_started else None, 4),
        "outcome_rate_among_all": round_or_none(n_acc / len(chains) if chains else None, 4),
        "total_cost": round_or_none(total_cost, 4),
        "cost_per_accepted": round_or_none(total_cost / n_acc if n_acc else None, 4),
        "cost_key": cost_key,
    }


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
            "headline": {"reason": "missing log file"},
            "records_written": [result_path, notes_path],
        }
        with open(result_path, "w") as f:
            json.dump(result, f, indent=2)
        with open(notes_path, "w") as f:
            f.write("# Q505 blocked — log file missing\n")
        print(json.dumps({"qid": QID, "status": "blocked"}))
        return 2

    recs = load_log(LOG_PATH)
    prof = profile_log(recs)
    chains = build_call_chains(recs)
    families = build_job_families(recs)
    fam_ge2 = [f for f in families if len(f["recs"]) >= 2]
    chain_lens = Counter(len(c["recs"]) for c in chains)
    fam_lens = Counter(len(f["recs"]) for f in families)

    # --- call-chain tiers (status-rich; dollars ~0; resource = attempts / latency)
    chain_runs = [c["recs"] for c in chains]
    table_attempts = tier_table(chain_runs, "attempts")
    table_latency = tier_table(chain_runs, "latency_s")
    table_usd = tier_table(chain_runs, "cost_usd")
    retry_runs = [c["recs"] for c in chains if len(c["recs"]) >= 2]
    table_attempts_retry = tier_table(retry_runs, "attempts") if retry_runs else []
    table_latency_retry = tier_table(retry_runs, "latency_s") if retry_runs else []

    drop_p90_att = drop_vs_unconstrained(table_attempts, "p90_cost")
    drop_med_att = drop_vs_unconstrained(table_attempts, "median_cost")
    drop_cpa_att_unc = drop_vs_unconstrained(table_attempts, "cost_per_accepted")
    drop_cpa_att_k1 = drop_cpa_vs_single_shot(table_attempts)
    drop_p90_lat = drop_vs_unconstrained(table_latency, "p90_cost")
    drop_cpa_lat_k1 = drop_cpa_vs_single_shot(table_latency)
    drop_p90_att_retry = (
        drop_vs_unconstrained(table_attempts_retry, "p90_cost")
        if table_attempts_retry
        else {"drops_ge_20pct": False, "reason": "no retry chains"}
    )
    drop_cpa_att_retry_k1 = (
        drop_cpa_vs_single_shot(table_attempts_retry)
        if table_attempts_retry
        else {"drops_ge_20pct": False, "reason": "no retry chains"}
    )

    # --- job-family quota tiers (quota-rich; status sparse)
    fam_runs_all = [f["recs"] for f in families]
    fam_runs_ge2 = [f["recs"] for f in fam_ge2]
    table_quota_all = tier_table(fam_runs_all, "quota_5h", require_status=False)
    table_quota_ge2 = tier_table(fam_runs_ge2, "quota_5h", require_status=False)
    table_quota_ge2_status = tier_table(fam_runs_ge2, "quota_5h", require_status=True)
    drop_p90_q = drop_vs_unconstrained(table_quota_ge2, "p90_cost")
    drop_med_q = drop_vs_unconstrained(table_quota_ge2, "median_cost")
    drop_cpa_q_unc = drop_vs_unconstrained(table_quota_ge2, "cost_per_accepted")
    drop_cpa_q_k1 = drop_cpa_vs_single_shot(table_quota_ge2)

    # Primary 20% test: job-family p90 quota among families with >=2 attempts,
    # because the brief asks for quota cost and retries. Call-chain p90
    # attempts is the status-complete companion.
    primary = drop_p90_q
    companion = drop_p90_att
    retry_comp = drop_p90_att_retry
    drops = bool(primary.get("drops_ge_20pct")) or bool(companion.get("drops_ge_20pct")) or bool(
        retry_comp.get("drops_ge_20pct")
    )
    if primary.get("drops_ge_20pct"):
        which = {
            "source": "job_family_quota_5h_pp",
            "metric": "p90_cost",
            "at_tier": primary["at_tier"],
            "drop_pct": primary["drop_pct"],
        }
    elif companion.get("drops_ge_20pct"):
        which = {
            "source": "call_chain_attempts",
            "metric": "p90_cost",
            "at_tier": companion["at_tier"],
            "drop_pct": companion["drop_pct"],
        }
    elif retry_comp.get("drops_ge_20pct"):
        which = {
            "source": "call_chain_attempts_len_ge2",
            "metric": "p90_cost",
            "at_tier": retry_comp.get("at_tier"),
            "drop_pct": retry_comp.get("drop_pct"),
        }
    else:
        which = {
            "source": None,
            "metric": "p90_cost",
            "at_tier": None,
            "drop_pct": None,
        }

    # --- predictor in the loop on later-slice call chains ---
    chains_sorted = sorted(chains, key=lambda c: (c["recs"][0]["t"], c["recs"][0]["model"]))
    n_tr = int(len(chains_sorted) * TRAIN_FRAC)
    ch_tr, ch_te = chains_sorted[:n_tr], chains_sorted[n_tr:]
    mc = Counter(c["recs"][0]["model"] for c in ch_tr)
    keep_models = sorted((m for m, n in mc.items() if n >= MIN_MODEL_N), key=lambda m: -mc[m])
    keep_models = keep_models + (["OTHER"] if keep_models else ["OTHER"])
    tasks = sorted(
        set(c["recs"][0]["task_type"] for c in ch_tr),
        key=lambda t: -sum(1 for c in ch_tr if c["recs"][0]["task_type"] == t),
    )
    Xtr, ytr, _cols = first_attempt_design(ch_tr, keep_models, tasks)
    Xte, yte, _ = first_attempt_design(ch_te, keep_models, tasks)
    w = fit_logistic_irls(Xtr, ytr)
    p_te = sigmoid(Xte @ w)
    auc_te = roc_auc(yte, p_te)

    no_pred = predictor_sim(ch_te, np.ones(len(ch_te)), threshold=0.0, k=3, cost_key="attempts")
    with_pred = {}
    for tau in (0.3, 0.5, 0.7):
        with_pred[str(tau)] = predictor_sim(ch_te, p_te, threshold=tau, k=3, cost_key="attempts")
    # net saving per accepted at tau=0.5 vs no predictor
    c_np = no_pred.get("cost_per_accepted")
    c_wp = with_pred["0.5"].get("cost_per_accepted")
    if c_np and c_wp is not None:
        saving = c_np - c_wp
        saving_pct = (saving / c_np) * 100 if c_np else None
    else:
        saving = None
        saving_pct = None

    # variance: later-slice unconstrained attempts_used ~ accepted vs ~ p_hat
    used = []
    acc = []
    for ch in ch_te:
        r = replay_chain(ch["recs"], None, early_stop=True, cost_key="attempts")
        used.append(r["cost"])
        acc.append(1.0 if r["accepted"] else 0.0)
    used = np.asarray(used, dtype=float)
    acc = np.asarray(acc, dtype=float)
    # OLS used ~ 1 + accepted
    Xa = np.column_stack([np.ones(len(used)), acc])
    ba, _, _, _ = np.linalg.lstsq(Xa, used, rcond=None)
    r2_verifier = r2_score(used, Xa @ ba)
    Xp = np.column_stack([np.ones(len(used)), p_te])
    bp, _, _, _ = np.linalg.lstsq(Xp, used, rcond=None)
    r2_pred = r2_score(used, Xp @ bp)

    headline = {
        "outcome_definition": (
            "log status only (accepted = some attempt in the budget has status=ok). "
            "NO quality labels in the log."
        ),
        "quality_labels_in_log": False,
        "cost_under_retries_drops_ge_20pct": drops,
        "at_tier": which["at_tier"],
        "drop_pct": which["drop_pct"],
        "drop_source": which["source"],
        "drop_metric": "p90 cost vs unconstrained logged retries",
        "primary_quota_p90_drop": primary,
        "companion_attempts_p90_drop": companion,
        "retry_subset_attempts_p90_drop": drop_p90_att_retry,
        "retry_subset_cost_per_accepted_vs_k1": drop_cpa_att_retry_k1,
        "quota_median_drop_vs_unconstrained": drop_med_q,
        "quota_cost_per_accepted_vs_k1": drop_cpa_q_k1,
        "call_chain_cost_per_accepted_vs_k1": drop_cpa_att_k1,
        "call_chain_latency_p90_drop": drop_p90_lat,
        "n_call_chains": len(chains),
        "n_call_chains_len_ge2": sum(1 for c in chains if len(c["recs"]) >= 2),
        "n_job_families": len(families),
        "n_job_families_len_ge2": len(fam_ge2),
        "explicit_attempt_or_retried_fields": prof["n_with_attempt_or_retried_field"],
        "quota_tiers_families_ge2": table_quota_ge2,
        "call_chain_attempt_tiers": table_attempts,
        "predictor_net_saving_per_accepted_attempts_tau0.5": round_or_none(saving, 4),
        "predictor_net_saving_pct_tau0.5": round_or_none(saving_pct, 2),
        "predictor_heldout_auc_first_attempt": round_or_none(auc_te, 4),
        "variance_share_attempts_explained_by_verifier_outcome": round_or_none(r2_verifier, 4),
        "variance_share_attempts_explained_by_predicted_p_ok": round_or_none(r2_pred, 4),
        "verifier_dominates_predicted_cost": (
            bool(r2_verifier == r2_verifier and r2_pred == r2_pred and r2_verifier > r2_pred)
        ),
    }

    assumptions = [
        "Outcome is logged status==ok, not quality. verified_correct is null everywhere it appears. Same limit as Q281 / CHECKS.md.",
        "Retries are reconstructed, not labelled: only %d rows carry attempt/retried fields. Call-level retry = consecutive same (model, provider, task_type) within %d seconds, extended only while the previous attempt was not ok. Job-level retry = job-title family (version/round/review tokens stripped; gui-plan variants kept distinct via the free/canary suffix)."
        % (prof["n_with_attempt_or_retried_field"], CHAIN_GAP_S),
        "Replay never invents attempts that were not logged. A budget K only has an effect on runs that actually continued past K in the log. Single-attempt failures stay failures at every K.",
        "Early-stop at the first status=ok inside the cap. Runs with no status (typical quota job families) do not early-stop; their outcome_rate is completion-unknown and is reported separately from status-bearing call chains.",
        "Quota cost is the 5-hour usage delta (percentage points) on job-run rows. Negative deltas are quota resets and are dropped, not treated as negative cost. Per-call cost_usd is almost always 0, so call-chain resource is attempt count and latency_s.",
        "The headline 20% test is p90 cost at a capped tier versus unconstrained logged retries, on job-family 5h quota (primary) and on call-chain attempts (companion). cost-per-accepted versus K=1 is reported alongside (do retries improve economics) but is not the headline boolean.",
        "Predictor-in-the-loop uses a first-attempt logistic P(ok | model, task_type) trained on the earliest 70% of chains and applied to the later 30%. Skipping a chain (p < tau) spends 0 and cannot accept it. This is the closest recoverable reading of the spec's with/without-predictor comparison; the log has no per-query prefill scout.",
        "Variance share is OLS R2 of unconstrained attempts-used on the later slice, explained by the verifier outcome (accepted) versus by predicted P(ok). Dollars are not the cost variable because they are ~0 on status rows.",
        "Card C-scout-before-you-route is not in the staged cards/ directory; the question text is taken from TOP10-TEST-SPECS-DRAFT.md and data/backlog-full.json.",
    ]

    method = (
        "Profiled job-usage-log.jsonl, reconstructed retry runs two ways "
        "(call-level rapid chains; job-title families with 5h quota deltas), "
        "replayed each run at escalating caps K=1,2,3,4,5,8,10 and unconstrained "
        "with early-stop at first logged status=ok, and recorded outcome rate plus "
        "median/p90 cost per tier. Headline 20% drop is p90 cost versus unconstrained. "
        "A later-slice first-attempt logistic then compares accepted-task attempt-cost "
        "with and without skipping low predicted-P(ok) queries."
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
        "chain_length_hist": {str(k): int(v) for k, v in sorted(chain_lens.items())},
        "family_length_hist": {str(k): int(v) for k, v in sorted(fam_lens.items())},
        "tables": {
            "call_chain_attempts": table_attempts,
            "call_chain_attempts_len_ge2": table_attempts_retry,
            "call_chain_latency_s": table_latency,
            "call_chain_latency_s_len_ge2": table_latency_retry,
            "call_chain_cost_usd": table_usd,
            "job_family_quota_5h_all": table_quota_all,
            "job_family_quota_5h_len_ge2": table_quota_ge2,
            "job_family_quota_5h_len_ge2_status_only": table_quota_ge2_status,
        },
        "drops": {
            "quota_p90_vs_unconstrained": drop_p90_q,
            "quota_median_vs_unconstrained": drop_med_q,
            "quota_cpa_vs_unconstrained": drop_cpa_q_unc,
            "quota_cpa_vs_k1": drop_cpa_q_k1,
            "attempts_p90_vs_unconstrained": drop_p90_att,
            "attempts_p90_len_ge2_vs_unconstrained": drop_p90_att_retry,
            "attempts_cpa_len_ge2_vs_k1": drop_cpa_att_retry_k1,
            "attempts_median_vs_unconstrained": drop_med_att,
            "attempts_cpa_vs_unconstrained": drop_cpa_att_unc,
            "attempts_cpa_vs_k1": drop_cpa_att_k1,
            "latency_p90_vs_unconstrained": drop_p90_lat,
            "latency_cpa_vs_k1": drop_cpa_lat_k1,
        },
        "predictor": {
            "n_train_chains": len(ch_tr),
            "n_test_chains": len(ch_te),
            "heldout_auc": round_or_none(auc_te, 4),
            "without_predictor_k3": no_pred,
            "with_predictor": with_pred,
        },
        "sample_job_families_ge2": [
            {"key": f["key"], "n": len(f["recs"]), "jobs": [x["job"] for x in f["recs"][:6]]}
            for f in sorted(fam_ge2, key=lambda f: -len(f["recs"]))[:12]
        ],
    }

    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)

    def fmt_table(table, cost_name):
        lines = [
            f"| tier | n | accepted | outcome_rate | median {cost_name} | p90 | cost/accepted |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for row in table:
            lines.append(
                "| {tier} | {n_runs} | {n_accepted} | {outcome_rate} | {median_cost} | {p90_cost} | {cost_per_accepted} |".format(
                    **{k: row[k] for k in ("tier", "n_runs", "n_accepted", "outcome_rate", "median_cost", "p90_cost", "cost_per_accepted")}
                )
            )
        return "\n".join(lines)

    drops_word = "YES" if drops else "NO"
    at = which["at_tier"]
    notes = f"""# {QID} — {TITLE}

Implements spec item 5 (TOP10-TEST-SPECS-DRAFT.md) against card
C-scout-before-you-route. Data: `data/routing/job-usage-log.jsonl`
(shared with Q281).

## Headline

**Cost-under-retries drops ≥20% at some tier: {drops_word}**
{f"at tier K={at}, source={which['source']}, p90 drop {which['drop_pct']}% vs unconstrained logged retries." if drops else "No capped tier cuts p90 cost by 20% vs unconstrained on either the job-family 5h quota series or the call-chain attempt series."}

Outcome is **log status**, not quality. Same mandatory limit as Q281.

## Data profile (computed)

- {prof["n_records"]} records, {prof["t_min"]} → {prof["t_max"]}.
- {prof["n_with_status"]} rows with status; {prof["n_with_start"]} job
  runs with `start`; {prof["n_with_5h_quota_delta"]} with a non-negative
  5h quota delta; **{prof["n_with_attempt_or_retried_field"]}** with an
  explicit `attempt`/`retried` field (the glm-4.7-flash triple).
- `verified_correct` non-null: {prof["n_verified_correct_nonnull"]}.
- Positive `cost_usd`: {prof["n_positive_cost_usd"]} (almost none of
  the status-bearing retry chains).
- Status mix: {json.dumps(prof["status_counts"], sort_keys=True)}.

Retries are reconstructed. CHECKS.md said "retries by repeated job
records"; the log does not carry a retry id, so two reconstructions
run in parallel.

## Method

1. **Call-level chains.** Sort status-bearing rows by time. A run is a
   streak of the same `(model, provider, task_type)` with successive
   gaps ≤ {CHAIN_GAP_S}s, extended only while the previous attempt
   was not `ok` (fail-then-retry; a success ends the run).
   {len(chains)} chains, of which
   {sum(1 for c in chains if len(c["recs"]) >= 2)} have length ≥2.
   Resource: attempt count (primary) and `latency_s`. Early-stop at
   first `status=ok`.
2. **Job-title families.** Job runs with `start`, grouped by a stem
   that strips version/round/review tokens and keeps gui-plan variants
   distinct. {len(families)} families, {len(fam_ge2)} with ≥2 attempts.
   Resource: 5h quota delta in percentage points. Negative deltas
   (quota resets) dropped.
3. Replay each run at K={TIERS} and unconstrained. A budget never
   invents attempts the log did not record.
4. **Predictor in the loop** (spec). First-attempt logistic P(ok |
   model, task_type) on the earliest 70% of chains; on the later 30%,
   compare K=3 replay of every chain against K=3 replay that skips
   chains with predicted P(ok) below 0.3 / 0.5 / 0.7.
5. Variance share: later-slice attempts-used OLS-R² on verifier
   accepted vs on predicted P(ok).

## Call-chain attempt tiers

{fmt_table(table_attempts, "attempts")}

Among chains that actually retried (unconstrained length ≥2):

{fmt_table(table_attempts_retry, "attempts") if table_attempts_retry else "_none_"}

p90-vs-unconstrained (all chains): {"YES" if companion.get("drops_ge_20pct") else "NO"}
(drop {companion.get("drop_pct")}%{"" if companion.get("at_tier") is None else " at K="+str(companion.get("at_tier"))}).
Among chains with unconstrained length ≥2 (the ones that actually
retried): {"YES" if drop_p90_att_retry.get("drops_ge_20pct") else "NO"} at
K={drop_p90_att_retry.get("at_tier")} (drop {drop_p90_att_retry.get("drop_pct")}%).
Cost-per-accepted vs K=1 (all chains): {"YES" if drop_cpa_att_k1.get("drops_ge_20pct") else "NO"}
(drop {drop_cpa_att_k1.get("drop_pct")}%).

## Job-family 5h quota tiers (families with ≥2 attempts)

{fmt_table(table_quota_ge2, "5h pp")}

p90-vs-unconstrained: drops≥20%={primary.get("drops_ge_20pct")} at
K={primary.get("at_tier")} (drop {primary.get("drop_pct")}%).
Median-vs-unconstrained: drops≥20%={drop_med_q.get("drops_ge_20pct")}
at K={drop_med_q.get("at_tier")} (drop {drop_med_q.get("drop_pct")}%).

Outcome rate on this table uses `require_status=False`, so "accepted"
here is "some record in the cap has status=ok". Most quota families
have no status at all; the status-only companion table is in
result.json (`job_family_quota_5h_len_ge2_status_only`). Do not read
the quota-table outcome_rate as a quality rate.

## Predictor in the loop (later-slice call chains)

Held-out first-attempt AUC **{round_or_none(auc_te, 4)}**.
Without predictor (K=3): cost/accepted {no_pred.get("cost_per_accepted")}
attempts, accepted {no_pred.get("n_accepted")}/{no_pred.get("n_chains")}.
With predictor τ=0.5: cost/accepted {with_pred["0.5"].get("cost_per_accepted")},
started {with_pred["0.5"].get("n_started")}, accepted
{with_pred["0.5"].get("n_accepted")}, net saving
{round_or_none(saving, 4)} attempts/accepted ({round_or_none(saving_pct, 2)}%).

Variance share of unconstrained attempts-used: verifier outcome R²
**{round_or_none(r2_verifier, 4)}**, predicted P(ok) R²
**{round_or_none(r2_pred, 4)}**. Verifier dominates predicted cost:
**{headline["verifier_dominates_predicted_cost"]}**.

## What the numbers mean

Two ≥20% drops show up, on different reconstructions:

- Job-family 5h quota, families with ≥2 attempts: capping at K=1
  cuts p90 from {primary.get("unconstrained_value")} pp to
  {primary.get("tier_value")} pp ({primary.get("drop_pct")}%) and
  median from {drop_med_q.get("unconstrained_value")} to
  {drop_med_q.get("tier_value")} ({drop_med_q.get("drop_pct")}%).
  Logged-ok outcome rate does not move
  ({table_quota_ge2[0].get("n_accepted")}/{table_quota_ge2[0].get("n_runs")}
  at every K) — every family that ever logs `ok` already did so on
  the first attempt, so extra rounds spend quota without converting
  more logged-ok outcomes. That is the headline YES at K=1.
- Call-level fail-retry chains of length ≥2: capping at
  K={drop_p90_att_retry.get("at_tier")} cuts p90 attempts from
  {drop_p90_att_retry.get("unconstrained_value")} to
  {drop_p90_att_retry.get("tier_value")}
  ({drop_p90_att_retry.get("drop_pct")}%) while outcome rate only
  moves from {drop_p90_att_retry.get("outcome_rate_unconstrained")}
  to {drop_p90_att_retry.get("outcome_rate_at_tier")}. Most chains
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
"""
    with open(notes_path, "w") as f:
        f.write(notes)

    print(
        json.dumps(
            {
                "qid": QID,
                "status": "done",
                "drops_ge_20pct": drops,
                "at_tier": which["at_tier"],
                "source": which["source"],
                "drop_pct": which["drop_pct"],
                "predictor_auc": round_or_none(auc_te, 4),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
