#!/usr/bin/env python3
"""Q364 — Routed Continual Learning cost at Hydra's actual prices (Hydra, memory).

Implements spec item 6 in TOP10-TEST-SPECS-DRAFT.md against card
C-routed-continual-learning and data/prices.json + data/routing/job-usage-log.jsonl.

Protocol from card C-routed-continual-learning (arXiv:2610.38796v1):
- 398 instances per rollout (301 CL-Bench + 97 tau-bench), 5 matched rollouts.
- 1 structured-output router call before each instance.
- Author-reported estimated API cost under frozen public prices:
  * Routed full library is 65% to 72% cheaper than one global history
    (i.e. routed/global cost ratio = 0.28 to 0.35).
  * Against routed histories, routed full library is 25% to 33% cheaper on
    three models, and 5% more expensive on Claude Opus 4.7.
  * Routing a single fixed ReasoningBank system raises cost 8% to 29%.

This script:
1. Parses data/routing/job-usage-log.jsonl to establish Hydra's actual model mix
   (by call share and token share) and empirical token footprints per call.
2. Loads data/prices.json (Vertex Argon effective 2026-11-12, Dec 2026 schedule,
   50% credit promotion; subscription/free lanes at $0 marginal dollar cost per
   the prices.json convention, explicitly stated wherever used).
3. Evaluates per-instance and per-stream (398-instance) economics under:
   (a) Authors' frozen public price schedule (using the card's stated 65-72%
       reduction ratios, since the card does not print raw per-instance token
       counts or dollar totals).
   (b) Hydra's actual model mix and Vertex Argon pricing (both homogeneous
       single-model rollouts, where any non-zero rate cancels in the relative
       percentage, and heterogeneous/decoupled routing vs execution across
       paid Vertex Argon and $0 subscription lanes).
4. Computes the exact router-call break-even point (as a fraction of global
   history per-instance cost / token footprint, and in tokens/dollars at
   empirical log averages).

Usage: q364.py [output_root]   (default ./results)
Writes <output_root>/Q364/result.json and <output_root>/Q364/notes.md.
"""
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
import numpy as np

QID = "Q364"
TITLE = "Routed Continual Learning cost at Hydra's actual prices"

# Verbatim constants from card C-routed-continual-learning
STREAM_INSTANCES = 398
CL_BENCH_INSTANCES = 301
TAU_BENCH_INSTANCES = 97
MATCHED_ROLLOUTS = 5
ROUTER_CALLS_PER_INSTANCE = 1

# Author-reported cost comparisons (from card text)
AUTHOR_SAVINGS_PCT_MIN = 65.0
AUTHOR_SAVINGS_PCT_MAX = 72.0
AUTHOR_SAVINGS_PCT_MID = 68.5
# Corresponding routed_full_library / global_history cost ratios:
AUTHOR_COST_RATIO_MIN = 1.0 - (AUTHOR_SAVINGS_PCT_MAX / 100.0)  # 0.28
AUTHOR_COST_RATIO_MAX = 1.0 - (AUTHOR_SAVINGS_PCT_MIN / 100.0)  # 0.35
AUTHOR_COST_RATIO_MID = 1.0 - (AUTHOR_SAVINGS_PCT_MID / 100.0)  # 0.315

AUTHOR_VS_ROUTED_HIST_SAVINGS_3MODELS_PCT = [25.0, 33.0]
AUTHOR_VS_ROUTED_HIST_OPUS47_SURCHARGE_PCT = 5.0
AUTHOR_REASONINGBANK_SURCHARGE_PCT = [8.0, 29.0]


def now_iso_local():
    return datetime.now().astimezone().isoformat()


def _extract_first(record, keys, default=None):
    for k in keys:
        if k in record and record[k] is not None:
            return record[k]
    # Check nested usage dict if present
    usage = record.get("usage")
    if isinstance(usage, dict):
        for k in keys:
            if k in usage and usage[k] is not None:
                return usage[k]
    return default


def _to_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def is_vertex_argon(model_str, provider_str=""):
    m = (model_str or "").lower()
    p = (provider_str or "").lower()
    if "argon" in m or "gemini-4-argon" in m:
        return True
    if "vertex" in p and ("argon" in m or "gemini" in m):
        return True
    return False


def parse_job_log(log_path):
    """Parse data/routing/job-usage-log.jsonl and return model mix & token stats."""
    stats = {
        "log_path": log_path,
        "exists": os.path.isfile(log_path),
        "total_lines": 0,
        "valid_records": 0,
        "malformed_lines": 0,
        "by_model": {},
        "by_provider": {},
        "vertex_argon_calls": 0,
        "subscription_or_free_calls": 0,
        "tokens_available_records": 0,
    }
    if not stats["exists"]:
        return stats

    model_counts = defaultdict(int)
    provider_counts = defaultdict(int)
    model_tokens = defaultdict(lambda: {"input": 0.0, "cached_input": 0.0, "output": 0.0, "calls_with_tokens": 0})

    all_in, all_cached, all_out = [], [], []

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line_s = line.strip()
            if not line_s:
                continue
            stats["total_lines"] += 1
            try:
                rec = json.loads(line_s)
            except Exception:
                stats["malformed_lines"] += 1
                continue
            if not isinstance(rec, dict):
                stats["malformed_lines"] += 1
                continue

            stats["valid_records"] += 1

            model = str(_extract_first(
                rec,
                ["model", "model_id", "model_name", "lane_model", "target_model", "llm_model", "lane"],
                "unknown_model"
            ))
            provider = str(_extract_first(
                rec,
                ["provider", "vendor", "backend", "api_provider", "platform"],
                ""
            ))
            if not provider and "/" in model:
                provider = model.split("/", 1)[0]
            if not provider:
                provider = "unspecified"

            # Normalize key as provider/model if model doesn't already have provider prefix
            full_model = model if "/" in model else f"{provider}/{model}" if provider != "unspecified" else model

            model_counts[full_model] += 1
            provider_counts[provider] += 1

            if is_vertex_argon(full_model, provider):
                stats["vertex_argon_calls"] += 1
            else:
                stats["subscription_or_free_calls"] += 1

            in_tok = _extract_first(rec, [
                "input_tokens", "prompt_tokens", "tokens_in", "in_tokens",
                "input_token_count", "prompt_token_count"
            ])
            cached_tok = _extract_first(rec, [
                "cached_input_tokens", "cached_tokens", "cache_read_input_tokens",
                "cached_prompt_tokens", "cache_read_tokens"
            ])
            out_tok = _extract_first(rec, [
                "output_tokens", "completion_tokens", "tokens_out", "out_tokens",
                "output_token_count", "candidates_token_count", "completion_token_count"
            ])

            if in_tok is not None or out_tok is not None:
                in_v = _to_float(in_tok, 0.0)
                cached_v = _to_float(cached_tok, 0.0)
                out_v = _to_float(out_tok, 0.0)
                stats["tokens_available_records"] += 1
                model_tokens[full_model]["input"] += in_v
                model_tokens[full_model]["cached_input"] += cached_v
                model_tokens[full_model]["output"] += out_v
                model_tokens[full_model]["calls_with_tokens"] += 1
                all_in.append(in_v)
                all_cached.append(cached_v)
                all_out.append(out_v)

    total = stats["valid_records"]
    if total > 0:
        stats["vertex_argon_call_share"] = round(stats["vertex_argon_calls"] / total, 6)
        stats["subscription_or_free_call_share"] = round(stats["subscription_or_free_calls"] / total, 6)
    else:
        stats["vertex_argon_call_share"] = 0.0
        stats["subscription_or_free_call_share"] = 0.0

    for m, cnt in sorted(model_counts.items(), key=lambda x: (-x[1], x[0])):
        mt = model_tokens[m]
        c_wt = mt["calls_with_tokens"]
        is_paid = is_vertex_argon(m, "")
        stats["by_model"][m] = {
            "calls": cnt,
            "call_share": round(cnt / total, 6) if total > 0 else 0.0,
            "pricing_tier": "vertex_argon_paid" if is_paid else "subscription_or_free_$0_marginal",
            "calls_with_token_counts": c_wt,
            "total_input_tokens": round(mt["input"], 1),
            "total_cached_input_tokens": round(mt["cached_input"], 1),
            "total_output_tokens": round(mt["output"], 1),
            "mean_input_tokens": round(mt["input"] / c_wt, 2) if c_wt > 0 else None,
            "mean_cached_input_tokens": round(mt["cached_input"] / c_wt, 2) if c_wt > 0 else None,
            "mean_output_tokens": round(mt["output"] / c_wt, 2) if c_wt > 0 else None,
        }

    for p, cnt in sorted(provider_counts.items(), key=lambda x: (-x[1], x[0])):
        stats["by_provider"][p] = {
            "calls": cnt,
            "call_share": round(cnt / total, 6) if total > 0 else 0.0,
        }

    if all_in:
        in_arr = np.array(all_in, dtype=float)
        cached_arr = np.array(all_cached, dtype=float)
        out_arr = np.array(all_out, dtype=float)
        stats["token_summary"] = {
            "mean_input_tokens_per_call": round(float(np.mean(in_arr)), 2),
            "median_input_tokens_per_call": round(float(np.median(in_arr)), 2),
            "mean_cached_input_tokens_per_call": round(float(np.mean(cached_arr)), 2),
            "mean_output_tokens_per_call": round(float(np.mean(out_arr)), 2),
            "median_output_tokens_per_call": round(float(np.median(out_arr)), 2),
            "total_input_tokens": round(float(np.sum(in_arr)), 1),
            "total_cached_input_tokens": round(float(np.sum(cached_arr)), 1),
            "total_output_tokens": round(float(np.sum(out_arr)), 1),
        }
    else:
        stats["token_summary"] = None

    return stats


def load_prices(prices_path):
    """Load data/prices.json with fallback to the verbatim contract schema if missing."""
    default_prices = {
        "note": (
            "Hydra's other lanes are subscriptions (metered by quota, not dollars) "
            "or free tiers. For repricing, subscription lanes carry $0 marginal "
            "dollar cost; quota cost is reported in calls/tokens where the logs "
            "carry it. State which convention a result used."
        ),
        "vertex_argon": {
            "effective_for_2026-11-12": {
                "cached_input_per_mtok_usd": 0.1,
                "input_per_mtok_usd": 2.0,
                "output_per_mtok_usd": 10.0,
            },
            "from_2026-12-01": {
                "cached_input_per_mtok_usd": 0.2,
                "input_per_mtok_usd": 4.0,
                "output_per_mtok_usd": 20.0,
            },
            "model": "google/gemini-4-argon",
            "promotion": "50% credits back on net spend",
        },
    }
    if os.path.isfile(prices_path):
        with open(prices_path, "r", encoding="utf-8") as f:
            return json.load(f), True
    return default_prices, False


def price_tokens_usd(in_tok, cached_tok, out_tok, schedule, apply_promo=False):
    """Compute USD cost for given token counts under a Vertex rate schedule.

    Note: uncached_in is max(0, in_tok - cached_tok) if in_tok includes cached,
    or if cached_tok is tracked separately we price uncached at input_per_mtok_usd
    and cached at cached_input_per_mtok_usd. Here we treat in_tok as total input
    if cached_tok <= in_tok, else additive.
    """
    uncached_in = max(0.0, in_tok - cached_tok) if cached_tok <= in_tok else in_tok
    cost = (
        (uncached_in / 1e6) * schedule["input_per_mtok_usd"]
        + (cached_tok / 1e6) * schedule["cached_input_per_mtok_usd"]
        + (out_tok / 1e6) * schedule["output_per_mtok_usd"]
    )
    if apply_promo:
        cost *= 0.5
    return cost


def compute_economics(log_stats, prices_data):
    """Reprice Routed Continual Learning under authors' schedule and Hydra's schedule."""
    va = prices_data.get("vertex_argon", {})
    sched_nov = va.get("effective_for_2026-11-12", {
        "cached_input_per_mtok_usd": 0.1,
        "input_per_mtok_usd": 2.0,
        "output_per_mtok_usd": 10.0,
    })
    sched_dec = va.get("from_2026-12-01", {
        "cached_input_per_mtok_usd": 0.2,
        "input_per_mtok_usd": 4.0,
        "output_per_mtok_usd": 20.0,
    })

    s_paid = log_stats.get("vertex_argon_call_share", 0.0)
    s_free = log_stats.get("subscription_or_free_call_share", 1.0 - s_paid)

    # 1. Authors' schedule (from card C-routed-continual-learning)
    # In the authors' single-model rollouts, all roles (router, adapter, extractor,
    # agent) use the same model per rollout. Cost is reduced by 65% to 72% vs
    # one global history (cost ratio 0.28 to 0.35).
    authors_schedule = {
        "stream_instances": STREAM_INSTANCES,
        "rollouts": MATCHED_ROLLOUTS,
        "router_calls_per_instance": ROUTER_CALLS_PER_INSTANCE,
        "router_calls_per_stream": STREAM_INSTANCES * ROUTER_CALLS_PER_INSTANCE,
        "routed_vs_global_savings_pct_range": [AUTHOR_SAVINGS_PCT_MIN, AUTHOR_SAVINGS_PCT_MAX],
        "routed_vs_global_savings_pct_midpoint": AUTHOR_SAVINGS_PCT_MID,
        "routed_over_global_cost_ratio_range": [
            round(AUTHOR_COST_RATIO_MIN, 4),
            round(AUTHOR_COST_RATIO_MAX, 4),
        ],
        "routed_over_global_cost_ratio_midpoint": round(AUTHOR_COST_RATIO_MID, 4),
        "routed_full_vs_routed_histories_savings_pct_3models": AUTHOR_VS_ROUTED_HIST_SAVINGS_PCT
        if False else AUTHOR_VS_ROUTED_HIST_SAVINGS_3MODELS_PCT,
        "routed_full_vs_routed_histories_opus47_surcharge_pct": AUTHOR_VS_ROUTED_HIST_OPUS47_SURCHARGE_PCT,
        "single_reasoningbank_surcharge_pct_range": AUTHOR_REASONINGBANK_SURCHARGE_PCT,
    }

    # 2. Hydra repricing — Case A: Homogeneous single-model rollouts (matching paper protocol)
    # In a single-model rollout where router, adapter, and agent all run on the SAME model:
    # - On Vertex Argon (paid per token): the dollar price per MTok is a constant scalar
    #   factor across both routed and global conditions (assuming matched output/input mix
    #   and cache hit rate), so the relative percentage cost reduction is invariant at
    #   65.0% to 72.0% (ratio 1.0x of authors' claimed advantage).
    # - With prompt caching active on Vertex Argon ($0.10/MTok cached vs $2.00/MTok uncached,
    #   a 95% discount on cached prefix tokens): one global history has a monotonically
    #   growing shared prefix across the 398 instances, whereas routed clusters partition
    #   context into smaller cluster histories and add an uncached/partially-cached router
    #   call per instance. We compute the sensitivity to differential cache hit rate (alpha_global vs alpha_routed).
    # - On Hydra subscription lanes ($0 marginal USD cost): both routed and global carry $0.00
    #   marginal dollar cost (undefined 0/0 in dollars), while in token/quota terms the
    #   65.0% to 72.0% savings survives identically.
    # - Across Hydra's logged model mix (expected cost per call weighted by s_paid):
    #   if every role draws independently from Hydra's model mix (paid share s_paid,
    #   $0 subscription share s_free), both global and routed expected dollar costs scale
    #   by s_paid, preserving the 65.0% to 72.0% relative dollar reduction whenever s_paid > 0.

    # Cache sensitivity on Vertex Argon:
    # Suppose per-instance execution is input-dominated (since history grows over 398 instances).
    # Effective input price with cache hit fraction c is: P_eff(c) = (1 - c)*P_in + c*P_cached.
    p_in_nov = sched_nov["input_per_mtok_usd"]
    p_cache_nov = sched_nov["cached_input_per_mtok_usd"]
    p_out_nov = sched_nov["output_per_mtok_usd"]

    # If global history achieves high prefix cache reuse (e.g., c_global = 0.80) while routed
    # clusters achieve lower cache reuse (e.g., c_routed = 0.40) due to switching across clusters:
    eff_in_global_c80 = 0.20 * p_in_nov + 0.80 * p_cache_nov  # $0.48 / MTok
    eff_in_routed_c40 = 0.60 * p_in_nov + 0.40 * p_cache_nov  # $1.24 / MTok
    cache_price_multiplier = eff_in_routed_c40 / eff_in_global_c80  # ~2.5833x
    # Adjusted routed/global input cost ratio under asymmetric caching (c_global=0.8, c_routed=0.4):
    asym_cache_ratio_min = AUTHOR_COST_RATIO_MIN * cache_price_multiplier
    asym_cache_ratio_max = AUTHOR_COST_RATIO_MAX * cache_price_multiplier
    asym_cache_savings_pct_range = [
        round((1.0 - asym_cache_ratio_max) * 100.0, 2),
        round((1.0 - asym_cache_ratio_min) * 100.0, 2),
    ]

    # 3. Hydra repricing — Case B: Decoupled / cross-lane routing (Hydra's multi-model reality)
    # What if the router call runs on paid Vertex Argon, while the agent/memory execution runs
    # on a $0 marginal-cost subscription lane (or vice versa)?
    # - Subcase B1: Router on subscription ($0 marginal USD), Executor on Vertex Argon (paid).
    #   Router dollar cost = $0. Routed dollar advantage is strictly GREATER than or equal to
    #   authors' 65-72% (improves by the router's share of total cost, rho_router).
    # - Subcase B2: Router on Vertex Argon (paid), Executor on subscription ($0 marginal USD).
    #   Global history has 0 router calls -> $0.00 marginal USD cost!
    #   Routed full library has 398 paid router calls -> >$0 marginal USD cost!
    #   In marginal dollars, global history costs $0 while routed costs 398 * C_router_usd,
    #   so the marginal dollar advantage flips completely (infinite relative dollar increase,
    #   though quota/token savings of 65-72% on the subscription lane still hold).

    # 4. Router-call break-even analysis
    # Let:
    #   G = per-instance cost (or token volume) of the one-global-history baseline.
    #   E_routed = per-instance non-router (agent + adapter + extractor) cost in routed full library.
    #   R = per-instance router call cost (1 call per instance).
    # Under the authors' reported total routed cost T_routed = E_routed + R = (1 - s) * G,
    # where s in [0.65, 0.72] is the reported total savings fraction:
    #   - The net savings margin per instance is M = G - T_routed = s * G (i.e. 65% to 72% of G).
    #   - If E_routed is fixed, the maximum total router call cost R_max per instance before
    #     routed equals global cost (T_routed = G) is:
    #       R_break_even = G - E_routed = M + R_baseline >= s * G (at least 65% to 72% of G).
    #   - Equivalently, if R increases by a surcharge factor k (so new router cost is k * R)
    #     or if an extra per-instance router overhead Delta_R is added on top of the authors'
    #     routed cost T_routed, break-even occurs when:
    #       Delta_R / G = s   (i.e. additional router cost equals 65% to 72% of global history cost),
    #     or as a multiple of total routed cost T_routed:
    #       Delta_R / T_routed = s / (1 - s)  -> 1.857x to 2.571x of the entire routed instance cost!

    breakeven_additional_router_fraction_of_global = [
        round(AUTHOR_SAVINGS_PCT_MIN / 100.0, 4),
        round(AUTHOR_SAVINGS_PCT_MAX / 100.0, 4),
    ]
    breakeven_additional_router_midpoint_of_global = round(AUTHOR_SAVINGS_PCT_MID / 100.0, 4)
    breakeven_additional_router_multiple_of_routed = [
        round((AUTHOR_SAVINGS_PCT_MIN / 100.0) / AUTHOR_COST_RATIO_MAX, 4),
        round((AUTHOR_SAVINGS_PCT_MAX / 100.0) / AUTHOR_COST_RATIO_MIN, 4),
    ]

    # Empirical valuation using logged token footprints (if available in job-usage-log.jsonl)
    tok_sum = log_stats.get("token_summary")
    if tok_sum:
        mean_in = tok_sum["mean_input_tokens_per_call"]
        mean_cached = tok_sum["mean_cached_input_tokens_per_call"]
        mean_out = tok_sum["mean_output_tokens_per_call"]
    else:
        # If log has no token fields, use 0.0 and report clearly
        mean_in, mean_cached, mean_out = 0.0, 0.0, 0.0

    # Cost of 1 average logged call on Vertex Argon under each schedule
    one_call_usd_nov = price_tokens_usd(mean_in, mean_cached, mean_out, sched_nov, apply_promo=False)
    one_call_usd_nov_promo = price_tokens_usd(mean_in, mean_cached, mean_out, sched_nov, apply_promo=True)
    one_call_usd_dec = price_tokens_usd(mean_in, mean_cached, mean_out, sched_dec, apply_promo=False)
    one_call_usd_dec_promo = price_tokens_usd(mean_in, mean_cached, mean_out, sched_dec, apply_promo=True)

    # Cost of 398 router calls (1 full stream) if each router call has the average logged call footprint:
    stream_398_router_calls_usd = {
        "vertex_argon_2026_11_12_list_usd": round(STREAM_INSTANCES * one_call_usd_nov, 6),
        "vertex_argon_2026_11_12_with_50pct_promo_usd": round(STREAM_INSTANCES * one_call_usd_nov_promo, 6),
        "vertex_argon_2026_12_01_list_usd": round(STREAM_INSTANCES * one_call_usd_dec, 6),
        "vertex_argon_2026_12_01_with_50pct_promo_usd": round(STREAM_INSTANCES * one_call_usd_dec_promo, 6),
        "hydra_actual_mix_weighted_2026_11_12_list_usd": round(
            STREAM_INSTANCES * one_call_usd_nov * s_paid, 6
        ),
        "hydra_actual_mix_weighted_2026_11_12_with_50pct_promo_usd": round(
            STREAM_INSTANCES * one_call_usd_nov_promo * s_paid, 6
        ),
        "subscription_lanes_marginal_usd": 0.0,
    }

    # Also compute break-even global-history per-instance cost if a router call costs one_call_usd_nov
    # and all non-router execution is on $0 subscription lanes (Subcase B2 vs paid global):
    # If global history is priced on Vertex Argon and routed execution is on Vertex Argon,
    # any router call costing R_usd breaks even against the 65-72% savings only if the global
    # instance cost G_usd <= R_usd / s (if R were purely additive overhead).
    if one_call_usd_nov > 0:
        min_global_instance_usd_to_absorb_1_logged_call_overhead = [
            round(one_call_usd_nov / (AUTHOR_SAVINGS_PCT_MAX / 100.0), 6),
            round(one_call_usd_nov / (AUTHOR_SAVINGS_PCT_MIN / 100.0), 6),
        ]
    else:
        min_global_instance_usd_to_absorb_1_logged_call_overhead = None

    hydra_schedule = {
        "pricing_convention": (
            "Per data/prices.json: Vertex Argon (google/gemini-4-argon) is priced at "
            "$2.00/MTok input, $0.10/MTok cached input, $10.00/MTok output effective 2026-11-12 "
            "(doubling 2026-12-01; 50% credit promotion available). All other Hydra lanes are "
            "subscriptions or free tiers carrying $0.00 marginal dollar cost (metered by quota/tokens)."
        ),
        "logged_vertex_argon_call_share": s_paid,
        "logged_subscription_or_free_call_share": s_free,
        "homogeneous_rollout_routed_vs_global_savings_pct_range": [
            AUTHOR_SAVINGS_PCT_MIN,
            AUTHOR_SAVINGS_PCT_MAX,
        ],
        "homogeneous_rollout_routed_over_global_cost_ratio_range": [
            round(AUTHOR_COST_RATIO_MIN, 4),
            round(AUTHOR_COST_RATIO_MAX, 4),
        ],
        "repriced_advantage_over_paper_advantage_ratio_homogeneous": 1.0,
        "asymmetric_cache_sensitivity_c80_global_vs_c40_routed_savings_pct_range": asym_cache_savings_pct_range,
        "cross_lane_router_paid_executor_free_marginal_usd_savings_survives": False,
        "cross_lane_router_free_executor_paid_marginal_usd_savings_survives": True,
        "per_logged_call_mean_usd": {
            "vertex_argon_2026_11_12_list_usd": round(one_call_usd_nov, 6),
            "vertex_argon_2026_11_12_with_50pct_promo_usd": round(one_call_usd_nov_promo, 6),
            "vertex_argon_2026_12_01_list_usd": round(one_call_usd_dec, 6),
            "vertex_argon_2026_12_01_with_50pct_promo_usd": round(one_call_usd_dec_promo, 6),
            "hydra_mix_weighted_2026_11_12_list_usd": round(one_call_usd_nov * s_paid, 6),
        },
        "stream_398_router_calls_usd": stream_398_router_calls_usd,
    }

    breakeven = {
        "router_calls_per_instance": ROUTER_CALLS_PER_INSTANCE,
        "router_calls_per_stream": STREAM_INSTANCES * ROUTER_CALLS_PER_INSTANCE,
        "max_additional_router_cost_as_fraction_of_global_instance_cost_range": (
            breakeven_additional_router_fraction_of_global
        ),
        "max_additional_router_cost_as_fraction_of_global_instance_cost_midpoint": (
            breakeven_additional_router_midpoint_of_global
        ),
        "max_additional_router_cost_as_multiple_of_routed_instance_cost_range": (
            breakeven_additional_router_multiple_of_routed
        ),
        "min_global_instance_usd_to_absorb_1_avg_logged_call_on_argon_nov2026": (
            min_global_instance_usd_to_absorb_1_logged_call_overhead
        ),
        "cross_lane_paid_router_free_executor_breakeven_router_price_usd": 0.0,
        "explanation": (
            "In single-model or uniformly-mixed rollouts, routed full library saves 65% to 72% "
            "of the global history baseline (routed cost is 28% to 35% of global). Thus, the "
            "1 router call per instance would have to add an extra 65% to 72% of the entire "
            "per-instance global-history cost (or 1.86x to 2.57x of the total routed per-instance "
            "cost) to erase the savings. However, in a split-lane setup where the agent executes "
            "on a $0 marginal-cost subscription lane and only the router runs on paid Vertex Argon, "
            "global history costs $0.00 marginal USD while routed costs 398 paid router calls, "
            "so break-even in marginal dollars is $0.00."
        ),
    }

    return authors_schedule, hydra_schedule, breakeven


def main():
    started = time.time()
    started_iso = now_iso_local()

    out_root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "results")
    out_dir = os.path.join(out_root, QID)
    os.makedirs(out_dir, exist_ok=True)

    log_path = os.path.join(os.getcwd(), "data", "routing", "job-usage-log.jsonl")
    prices_path = os.path.join(os.getcwd(), "data", "prices.json")

    log_stats = parse_job_log(log_path)
    prices_data, prices_loaded = load_prices(prices_path)

    authors_sched, hydra_sched, breakeven = compute_economics(log_stats, prices_data)

    # Determine status: if log_path was missing or had 0 valid records, mark partial or blocked,
    # otherwise done.
    if not log_stats["exists"]:
        status = "blocked"
    elif log_stats["valid_records"] == 0:
        status = "partial"
    else:
        status = "done"

    result_path = os.path.join(out_dir, "result.json")
    notes_path = os.path.join(out_dir, "notes.md")
    records_written = [result_path, notes_path]

    headline = {
        "authors_routed_vs_global_savings_pct_range": [
            AUTHOR_SAVINGS_PCT_MIN,
            AUTHOR_SAVINGS_PCT_MAX,
        ],
        "authors_routed_over_global_cost_ratio_range": [
            round(AUTHOR_COST_RATIO_MIN, 4),
            round(AUTHOR_COST_RATIO_MAX, 4),
        ],
        "hydra_homogeneous_routed_vs_global_savings_pct_range": (
            hydra_sched["homogeneous_rollout_routed_vs_global_savings_pct_range"]
        ),
        "hydra_homogeneous_routed_over_global_cost_ratio_range": (
            hydra_sched["homogeneous_rollout_routed_over_global_cost_ratio_range"]
        ),
        "repriced_advantage_over_paper_advantage_ratio": (
            hydra_sched["repriced_advantage_over_paper_advantage_ratio_homogeneous"]
        ),
        "hydra_asymmetric_cache_c80_vs_c40_savings_pct_range": (
            hydra_sched["asymmetric_cache_sensitivity_c80_global_vs_c40_routed_savings_pct_range"]
        ),
        "router_breakeven_additional_fraction_of_global_cost_range": (
            breakeven["max_additional_router_cost_as_fraction_of_global_instance_cost_range"]
        ),
        "router_breakeven_additional_multiple_of_routed_cost_range": (
            breakeven["max_additional_router_cost_as_multiple_of_routed_instance_cost_range"]
        ),
        "logged_total_calls": log_stats["valid_records"],
        "logged_vertex_argon_call_share": log_stats["vertex_argon_call_share"],
        "logged_subscription_or_free_call_share": log_stats["subscription_or_free_call_share"],
        "stream_398_router_calls_usd_by_schedule": hydra_sched["stream_398_router_calls_usd"],
        "advantage_survives_homogeneous_and_quota": True,
        "advantage_survives_paid_router_on_free_subscription_executor_usd": False,
        "verdict": (
            f"Across {log_stats['valid_records']} logged calls "
            f"(Vertex Argon share={log_stats['vertex_argon_call_share']:.1%}, "
            f"$0 marginal subscription/free share={log_stats['subscription_or_free_call_share']:.1%}), "
            "the authors' 65-72% routed-vs-global cost reduction (cost ratio 0.28-0.35) survives "
            "at 1.0x in token/quota terms and in homogeneous or uniformly-mixed Vertex Argon dollar "
            "runs. Break-even requires additional router overhead equal to 65-72% of global per-instance "
            "cost (1.86x-2.57x of total routed cost). Two Hydra-specific caveats can erode or flip the "
            "dollar advantage: (1) if global history gets high Vertex prefix-cache reuse (e.g. 80% at "
            "$0.10/MTok vs $2.00/MTok uncached) while routed clusters get low reuse (40%), savings "
            "shrink from 65-72% to 9.6-27.7%; (2) if execution runs on a $0 marginal-cost subscription "
            "lane while the router runs on paid Vertex Argon, marginal dollar cost is higher for routed "
            "(398 paid calls vs $0), though the 65-72% quota/token reduction on the subscription lane remains."
        ),
    }

    assumptions = [
        "Protocol and author figures taken verbatim from card C-routed-continual-learning: 398 instances per rollout (301 CL-Bench + 97 tau-bench), 5 matched rollouts, 1 structured-output router call per instance, and 65% to 72% lower estimated API cost for routed full library vs one global history.",
        "Card C-routed-continual-learning reports relative cost percentages (65-72% cheaper than global history; 25-33% cheaper than routed histories on 3 models and +5% on Opus 4.7; +8-29% for single ReasoningBank) and does not print raw per-role token counts or absolute dollar totals.",
        "Pricing convention from data/prices.json: Vertex Argon (google/gemini-4-argon) is priced at $2.00/MTok input, $0.10/MTok cached input, $10.00/MTok output effective 2026-11-12 ($4.00/$0.20/$20.00 from 2026-12-01; 50% credit promotion on net spend). All other Hydra lanes are subscriptions or free tiers carrying $0.00 marginal dollar cost (metered by quota/tokens).",
        "When repricing empirical call footprints from data/routing/job-usage-log.jsonl under Vertex Argon, uncached input tokens are computed as max(0, input_tokens - cached_input_tokens) where cached tokens are logged.",
        "For Vertex prefix-cache sensitivity, we evaluate an illustrative asymmetric cache regime where one global history achieves 80% cached input reuse ($0.10/MTok) and routed clusters achieve 40% cached input reuse due to partition switching.",
    ]

    result = {
        "qid": QID,
        "title": TITLE,
        "status": status,
        "started": started_iso,
        "finished": now_iso_local(),
        "runtime_s": round(time.time() - started, 3),
        "method": (
            "Parsed data/routing/job-usage-log.jsonl to extract Hydra's actual provider/model call shares "
            "and empirical per-call input, cached-input, and output token distributions. Loaded Hydra's "
            "pricing schedules from data/prices.json (Vertex Argon 2026-11-12 and 2026-12-01 rates with "
            "and without the 50% credit promotion, plus the $0 marginal dollar convention for subscription "
            "lanes). Evaluated the 398-instance Routed Continual Learning protocol under (a) the authors' "
            "frozen public price schedule (65-72% cost reduction vs one global history) and (b) Hydra's "
            "model mix and Vertex Argon rates across homogeneous, cache-asymmetric, and cross-lane "
            "(paid router vs $0 subscription executor) regimes, and solved for the router-call break-even point."
        ),
        "assumptions": assumptions,
        "headline": headline,
        "details": {
            "job_log_summary": log_stats,
            "prices_loaded_from_file": prices_loaded,
            "authors_schedule_economics": authors_sched,
            "hydra_schedule_economics": hydra_sched,
            "router_breakeven_analysis": breakeven,
        },
        "records_written": records_written,
    }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Build model mix markdown table for notes.md
    model_rows = []
    for m, mdata in log_stats["by_model"].items():
        model_rows.append(
            f"| `{m}` | {mdata['calls']} | {mdata['call_share']:.2%} | "
            f"`{mdata['pricing_tier']}` | {mdata['mean_input_tokens']} | "
            f"{mdata['mean_cached_input_tokens']} | {mdata['mean_output_tokens']} |"
        )
    model_table = "\n".join(model_rows) if model_rows else "| (no models logged) | 0 | 0% | - | - | - | - |"

    notes = f"""# {QID} — {TITLE}

Implements spec item 6 (`TOP10-TEST-SPECS-DRAFT.md`) against card `C-routed-continual-learning` (arXiv:2610.38796v1), `data/routing/job-usage-log.jsonl`, and `data/prices.json`.

## Method

1. **Log parsing (`data/routing/job-usage-log.jsonl`):** Parsed all {log_stats['valid_records']} valid run records ({log_stats['malformed_lines']} malformed lines skipped) to establish Hydra's empirical model mix by call share and token footprint (input, cached input, and output tokens per call).
2. **Price schedule (`data/prices.json`):** Applied the explicit convention from `data/prices.json`:
   - **Vertex Argon (`google/gemini-4-argon`):** Effective 2026-11-12: `$2.00 / MTok` uncached input, `$0.10 / MTok` cached input, `$10.00 / MTok` output (doubling on 2026-12-01 to `$4.00 / $0.20 / $20.00`; 50% credit promotion on net spend also reported).
   - **Subscription / free lanes:** Carry **$0.00 marginal dollar cost** (metered by quota/tokens, not marginal dollars).
3. **Protocol repricing (398 instances, 1 router call/instance):** Compared the routed full library against one global history under (a) the authors' frozen public schedule as reported in the card and (b) Hydra's logged model mix and Vertex Argon rates, solving for the router-call break-even point.

## Assumptions & Honest Limits

- **Card granularity:** `C-routed-continual-learning` states the stream size (398 instances: 301 CL-Bench + 97 tau-bench, 5 matched rollouts), the router frequency (1 structured-output call before each instance), and the relative cost reductions (**65% to 72% lower cost** than one global history; **25% to 33% cheaper** than routed histories on 3 models and **+5% more expensive** on Claude Opus 4.7; **+8% to +29% cost** for routing a single fixed ReasoningBank). The card does not print raw per-role (router vs. Context Memory Adapter vs. extractor vs. agent) token counts or absolute dollar figures.
- **Closest faithful reading:** Because the card gives relative cost ratios across single-model rollouts, we evaluate:
  1. The exact algebraic survival of the 65–72% reduction under homogeneous and mix-weighted Hydra pricing.
  2. The sensitivity to Vertex Argon's 20:1 uncached-to-cached input price ratio (`$2.00` vs `$0.10/MTok`).
  3. Concrete dollar costs for the 398 router calls sized at Hydra's empirical logged per-call token footprint.
  4. The exact router-call break-even threshold in both relative and dollar terms.

## Hydra Logged Model Mix

- **Total valid logged calls:** `{log_stats['valid_records']}`
- **Vertex Argon (paid) call share:** `{log_stats['vertex_argon_call_share']:.2%}` (`{log_stats['vertex_argon_calls']}` calls)
- **Subscription / free ($0 marginal USD) call share:** `{log_stats['subscription_or_free_call_share']:.2%}` (`{log_stats['subscription_or_free_calls']}` calls)

| Model | Calls | Call Share | Pricing Tier (`prices.json` convention) | Mean In Tokens | Mean Cached Tokens | Mean Out Tokens |
|---|---:|---:|---|---:|---:|---:|
{model_table}

## Repricing Results & What the Numbers Mean

### (a) Authors' Schedule (Card `C-routed-continual-learning`)
- **Routed full library vs. One global history:** **65.0% to 72.0% cheaper** (routed/global cost ratio = **0.28 to 0.35**, midpoint **0.315** / **68.5% savings**).
- **Routed full library vs. Routed histories:** **25.0% to 33.0% cheaper** on 3 models; **5.0% more expensive** on Claude Opus 4.7.

### (b) Hydra Schedule (`data/prices.json` + Logged Mix)
1. **Homogeneous Rollouts & Uniformly-Mixed Rollouts (Advantage Survives at 1.0x):**
   - When a rollout runs end-to-end on Vertex Argon (at matching input/output/cache proportions), the per-token rate scales both conditions equally: routed full library remains **65.0% to 72.0% cheaper** in dollars (ratio of repriced advantage to paper's advantage = **1.0**).
   - When roles draw from Hydra's overall mix (`{log_stats['vertex_argon_call_share']:.2%}` paid Vertex Argon, `{log_stats['subscription_or_free_call_share']:.2%}` `$0` marginal subscription lanes) uniformly across conditions, expected marginal dollar cost scales by `{log_stats['vertex_argon_call_share']:.4f}` in both numerator and denominator, preserving the **65.0% to 72.0%** reduction in expected marginal dollars (and **65.0% to 72.0%** reduction in subscription quota/tokens).
2. **Vertex Argon Prefix-Cache Sensitivity (Advantage Narrows if Global History Caches Better):**
   - Vertex Argon discounts cached input by **95%** (`$0.10/MTok` vs `$2.00/MTok` uncached). Because one global history appends monotonically to a single shared prefix across all 398 instances whereas routed continual learning switches across isolated clusters and issues a fresh router call per instance, global history can achieve a higher cache hit rate.
   - In an illustrative asymmetric regime where global history achieves **80% cached input** (`$0.48/MTok` effective input rate) and routed clusters achieve **40% cached input** (`$1.24/MTok` effective input rate, `2.583x` higher per input token), the input-cost reduction shrinks from **65.0–72.0%** down to **{hydra_sched['asymmetric_cache_sensitivity_c80_global_vs_c40_routed_savings_pct_range'][0]}%–{hydra_sched['asymmetric_cache_sensitivity_c80_global_vs_c40_routed_savings_pct_range'][1]}%** (routed/global ratio `0.723` to `0.904`). It still survives, but loses more than half its dollar margin.
3. **Cross-Lane Split Routing (Paid Router vs. `$0` Subscription Executor):**
   - If the agent executes on a `$0` marginal-cost subscription lane while the 398 router calls are sent to paid Vertex Argon, one global history costs **`$0.00` marginal USD** (0 router calls) while routed costs **398 paid router calls**:
     - Effective 2026-11-12 list rates: **`${hydra_sched['stream_398_router_calls_usd']['vertex_argon_2026_11_12_list_usd']:.4f}`** per 398-instance stream (`${hydra_sched['stream_398_router_calls_usd']['vertex_argon_2026_11_12_with_50pct_promo_usd']:.4f}` with 50% promo).
     - From 2026-12-01 list rates: **`${hydra_sched['stream_398_router_calls_usd']['vertex_argon_2026_12_01_list_usd']:.4f}`** per 398-instance stream (`${hydra_sched['stream_398_router_calls_usd']['vertex_argon_2026_12_01_with_50pct_promo_usd']:.4f}` with 50% promo).
     - Weighted by Hydra's logged paid share (`{log_stats['vertex_argon_call_share']:.2%}`): **`${hydra_sched['stream_398_router_calls_usd']['hydra_actual_mix_weighted_2026_11_12_list_usd']:.4f}`** list (`${hydra_sched['stream_398_router_calls_usd']['hydra_actual_mix_weighted_2026_11_12_with_50pct_promo_usd']:.4f}` promo).
   - Conversely, if the router runs on a `$0` subscription lane and the executor runs on paid Vertex Argon, the dollar savings exceed 65–72%.

### Router-Call Break-Even Point
- **Relative break-even:** Because routed full library costs `28% to 35%` of global history (saving `65% to 72%` of global cost `G`, already including the baseline router call), additional per-instance router overhead `Delta_R` only erases the cost advantage when:
  - `Delta_R / G` reaches **0.65 to 0.72** (i.e. the router call overhead alone must add **65% to 72% of the entire global-history per-instance cost**), or
  - `Delta_R / T_routed` reaches **1.857x to 2.571x** of the entire routed per-instance cost.
- **Cross-lane marginal dollar break-even:** When the executor is on a `$0` marginal-cost subscription lane, marginal dollar break-even for a paid router is **`$0.00`** (any non-zero dollar price on the router makes marginal USD cost higher than unrouted `$0` subscription execution, though the 65–72% quota/token savings on the subscription lane still hold).
"""

    with open(notes_path, "w", encoding="utf-8") as f:
        f.write(notes)

    print(json.dumps({
        "qid": QID,
        "status": status,
        "headline": {
            "authors_savings_pct": [AUTHOR_SAVINGS_PCT_MIN, AUTHOR_SAVINGS_PCT_MAX],
            "hydra_homogeneous_savings_pct": hydra_sched["homogeneous_rollout_routed_vs_global_savings_pct_range"],
            "router_breakeven_fraction_of_global": breakeven["max_additional_router_cost_as_fraction_of_global_instance_cost_range"],
        },
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
