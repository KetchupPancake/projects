# Night Shift Triage — Top-10 Test-Spec Package (DRAFT for KetchupPancake's approval)

Prepared 2026-11-11 by Vera (proactive research pass), from the 3-lane
consolidation in `CONSOLIDATION-3LANE.md` / `consolidated-3lane.csv`.
Grok's pass is still running (chunks 1–2 done, chunk 3 in progress at
19:59 MT check); when it lands it becomes a fourth vote and may move
borderline picks, but all ten below are **unanimous Pile A** across
Claude, Codex and Argon, so a Grok dissent would flag, not silently
overturn, them.

Selection rule: unanimous machine-testable, Hydra/Laboratory/Still
consumers first, own logged data before public benchmarks, cheapest
deterministic runs first. No pilot run is authorised by this draft —
the package returns to KetchupPancake for approval first, per the triage goal.

## The ten

### 1. Q401 — Proposition 14 arithmetic check (Still)
- **Question:** What reconciles the printed 26x with the Proposition 14
  ratio at r = 0.01, rho_u = 0.02? (card C-sys1-sys2-codesign)
- **Run:** Pure computation. Substitute the stated parameters into the
  Proposition 14 formula; also solve for the parameter values that
  would yield 26x.
- **Metric / settles when:** Computed ratio printed next to the claimed
  26x; if they differ, the parameter set that produces 26x is reported
  (typo, different regime, or error — each is a distinct finding).
- **Cost:** Minutes of CPU. No model judgement. Do this one first.

### 2. Q137 — Engrim merge / provenance fixture test (Hydra, memory)
- **Question:** How are superseded records handled, and does provenance
  survive a merge between two stores? (card C-engrim)
- **Run:** Build two small fixture stores with known supersession
  chains, merge them with the engrim code path, inspect the result.
- **Metric / settles when:** Provenance chain intact for 100% of
  fixture records, or the exact records whose provenance breaks are
  listed. Deterministic pass/fail.
- **Cost:** Local CPU, fixture-scale. No external data.

### 3. Q207 — joey-1 abstention threshold sweep (Hydra, routing)
- **Question:** What abstention rate and threshold give the best
  trade-off between cost, latency, and accuracy on Hydra routing?
  (card C-joey-1-decision-model)
- **Run:** Replay Hydra routing logs across a threshold grid; for each
  threshold compute abstention rate, accuracy on non-abstained,
  mean latency and cost.
- **Metric / settles when:** A cost–latency–accuracy curve with a
  stated knee; the deliverable is the curve, not a chosen threshold
  (choosing is KetchupPancake's).
- **Open check before pilot:** routing logs must carry outcome labels;
  confirm location/format at build time.

### 4. Q281 — Pre-run prediction value on Hydra run records (Hydra, routing)
- **Question:** Does pre-run prediction improve Hydra routing or
  configuration choice on Hydra's own run records, measured against
  the cost of collecting them? (card C-meta-models-model-learning)
- **Run:** Tabular experiment on historical run records: train the
  predictor on an early slice, score routing/config choices on a
  later slice against the choices actually made.
- **Metric / settles when:** Net benefit = measured improvement in
  outcome/cost minus predictor collection cost, with the sign stated.
- **Cost:** CPU only; pairs naturally with the hydra-evals schema.

### 5. Q505 — Cost prediction under verification and retries (Hydra, routing)
- **Question:** In a swarm with verification and retries, does
  per-query cost prediction still pay, or does the verifier's outcome
  dominate the economics? (card C-scout-before-you-route)
- **Run:** Simulation over logged runs with retries: compare total
  accepted-task cost with and without the per-query predictor in
  the loop.
- **Metric / settles when:** Predictor's net saving (or loss) per
  accepted task, and the share of variance explained by verifier
  outcomes vs. predicted cost.
- **Cost:** CPU script on logs; shares log prep with Q207/Q281.

### 6. Q364 — Routed Continual Learning cost at Hydra's actual prices (Hydra, memory)
- **Question:** Does the cost advantage survive when routing, adapter,
  and extractor calls are priced at Hydra's actual model mix and
  Vertex budget? (card C-routed-continual-learning)
- **Run:** Cost arithmetic: take the paper's call counts, reprice
  every call at Hydra's logged model mix and current Vertex rates.
- **Metric / settles when:** Repriced advantage stated as a ratio
  against the paper's claimed advantage; advantage survives or it
  doesn't, at stated prices.
- **Note:** Timely — the vertex_paid gate was signed and verified on
  in cora-wsl today (2026-11-11), so the Vertex prices are live ones.

### 7. Q136 — Hybrid recall on Hydra's own decisions (Hydra, memory)
- **Question:** How accurate is hybrid recall on Hydra's own
  decisions, and how does it degrade as the store grows?
  (card C-engrim)
- **Run:** Recall benchmark over the logged decision store at
  increasing store sizes (subsampled prefixes), fixed query set
  with known targets.
- **Metric / settles when:** Recall@k curve against store size;
  degradation slope stated.
- **Open check before pilot:** query set with known targets must be
  built from the decision log; that prep is part of the spec, costed
  as fixture work like Q137.

### 8. Q308 — Coordination exponent on Hydra's own workloads (Hydra, swarm)
- **Question:** What is the measured coordination exponent of today's
  multi-agent systems on Hydra's own workloads, and is it anywhere
  near 1? (card C-organizing-intelligence)
- **Run:** Statistical fit over logged multi-agent workload records:
  outcome/throughput against agent count, fit the exponent.
- **Metric / settles when:** Fitted exponent with confidence
  interval, stated against the paper's threshold of 1.
- **Open check before pilot:** needs runs at ≥3 distinct agent
  counts in the logs; if the logs only have one scale, this drops
  to Pile C honestly and Q339 (Obelisk retrieval on session
  histories) takes its slot.

### 9. Q472 — e-means vs tuned Lloyd at small k and n (Academy, retrieval)
- **Question:** At small k and small n (the regime of most practical
  index builds), does e-means still beat a well-tuned Lloyd, or is
  the advantage a large-scale phenomenon? (card 162, filed today)
- **Run:** CPU benchmark grid over small k/n on representative
  embedding sets; e-means vs Lloyd with matched restarts/tuning.
- **Metric / settles when:** Objective value and wall-time per cell;
  the k/n region where the advantage flips, if it flips.
- **Cost:** CPU, small scale by design. Directly serves Academy
  index builds.

### 10. Q471 — e-means scaling laws on Academy text embeddings (Academy, retrieval)
- **Question:** Do the scaling-law formulas hold off the authors'
  dataset family — text embeddings at Academy scale, not just image
  embeddings at Meta scale? (card 162, filed today)
- **Run:** Fit the paper's scaling formulas on Academy text
  embeddings across sizes; compare predicted vs measured objective.
- **Metric / settles when:** Fit error of the authors' formulas on
  text embeddings, stated against their reported image-embedding
  fit. This is the independent replication card 162 was filed as
  awaiting (its numbers are still the authors' own).
- **Cost:** Local CPU/GPU at Academy scale; shares embedding prep
  with Q472.

## Alternates (next in line if any of the ten fails its open check)

- **Q339** — Obelisk retrieval on Hydra's own session histories vs a
  baseline (Hydra, retrieval). First alternate; takes Q308's slot if
  the agent-count check fails.
- **Q201** — jevact decision gate on Hydra's own tasks with a local
  judge, false flags and revision cost counted (Hydra, eval-verifier).
- **Q492** — Event-driven orchestrator cache-penalty measurement
  from API usage logs (Hydra, routing).

## What this package is not

- Not a pilot authorisation. Test specs return to KetchupPancake as a package
  for approval before any pilot night, per the triage goal.
- Split questions (220 of 525) are not averaged into these picks;
  they stay flagged in `consolidated-3lane.csv` for Grok's fourth
  vote and, where the split is A-vs-C, for KetchupPancake.
- Log-location checks flagged above are build-time verifications,
  not assumptions: each spec names what would demote it.
