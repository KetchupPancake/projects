# Night Shift Pilot — Decision Brief (2026-11-12)

Prepared by Vera (proactive pass) after KetchupPancake approved the triage package
on 2026-11-11 evening MT and the sorter fold-in + site Triage tab were
built. Package approval was explicitly NOT pilot approval: the top-10
batch runs only when KetchupPancake approves the pilot separately.

## What is being decided

Approve, amend, or hold the first Night Shift pilot: the unanimous
Pile-A top-10 test specs in TOP10-TEST-SPECS-DRAFT.md, run as one
supervised night on one laptop (the pilot shape KetchupPancake approved when he
started the triage), with one morning digest before any standing
window/cluster decision.

## The ten, grouped by readiness

**Ready now — deterministic / arithmetic, no log dependencies:**
- Q401 — Proposition 14 arithmetic check (minutes of CPU; do first)
- Q137 — Engrim merge/provenance fixture test (deterministic pass/fail)
- Q364 — Routed Continual Learning repriced at Hydra's actual prices
  (Vertex prices are live ones — gate signed on in cora-wsl 2026-11-11)
- Q472 — e-means vs tuned Lloyd at small k/n (CPU grid)
- Q471 — e-means scaling laws on Academy text embeddings
  (Q472/Q471 share embedding prep; Q471 is the independent replication
  card 162 was filed as awaiting)

**Ready after a build-time log check (all three share log prep):**
- Q207 — joey-1 abstention threshold sweep (needs routing logs with
  outcome labels; location/format to confirm)
- Q281 — Pre-run prediction value on Hydra run records
- Q505 — Cost prediction under verification and retries (simulation
  over logged runs with retries)

**Ready after prep / with an honest demotion rule already in the spec:**
- Q136 — Hybrid recall vs store size (query set with known targets
  must be built from the decision log — costed as fixture work)
- Q308 — Coordination exponent (needs runs at ≥3 distinct agent
  counts; if the logs have only one scale it drops to Pile C and
  Q339 — Obelisk retrieval on session histories — takes its slot)

Alternates if any spec fails its open check: Q339, Q201, Q492.

## Corrections carried into the pilot

- Unique questions are 524, not 525 (one exact duplicate from the
  watermark-basins card; Pile A is 91 unique). The ten above are
  unaffected — all unanimous A across Claude, Codex and Argon.
- Grok is not a blocker: dropped from the critical path at KetchupPancake's
  ruling; its two finished chunks agreed with the 3-lane majority on
  146 of 210 (70%) and are preserved as a check, not a vote waited on.

## What approval would set in motion (no pilot runs on this brief alone)

1. Build-time checks for Q207/Q281/Q505 log labels, Q308 agent counts,
   Q136 query-set prep — any failure demotes per the spec, with the
   alternate slotting in; failures reported, not worked around.
2. One supervised pilot night on one laptop; Cora supervises/grades
   through the Laboratory pattern (sandbox never on Cora, per KetchupPancake's
   standing split).
3. One morning digest to KetchupPancake; no standing window or cluster decision
   follows automatically.

## Not decided by this brief

- Merging/deploying the sorter fold-in branch `triage-fold-in`
  (built, tested, committed locally; unmerged and undeployed) — a
  separate flip decision.
- Any standing Night Shift window, spend, or automation.
