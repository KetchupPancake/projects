# Night Shift Pilot — Build-Time Checks (run 2026-11-12 evening, Vera)

Package: nightshift-pilot-20261112, staged into p53-wsl ~/sandbox.
Rule (from the specs): a test whose open check fails DEMOTES, reported
with its reason, never worked around. Splits are flagged, not averaged.

## Verdicts

### RUN (8)

- **Q401 — Proposition 14 arithmetic (Still). PASS.**
  Self-contained. The source card (C-sys1-sys2-codesign) prints the
  Proposition 14 formula (cost fraction rho_u + r; speedup -> 1/rho_u)
  and itself flags that at r=0.01, rho_u=0.02 the ratio is 1/0.03 =
  33.3x, not the printed 26x. The run computes both, and solves for
  the parameter sets that yield exactly 26x.

- **Q137 — Engrim merge / provenance fixture (Hydra, memory). PASS.**
  Engrim is an external MIT tool (github.com/timgordontg/engrim,
  card C-engrim), not Hydra code — so the check was: does it install
  cleanly inside the room? RESULT (2026-11-12 ~21:5x MT): installed
  from PyPI into a sandbox venv, imports cleanly, version 1.4.11 —
  the exact version the card read on Oct 31. Check fully passed.
  Fixture: two small stores with known supersession chains, merge,
  provenance must survive 100% or the broken records are listed.

- **Q281 — Pre-run prediction value (Hydra, routing). PASS, reduced.**
  Logs exist: routing/job-usage-log.jsonl, 13,003 records,
  2026-10-15 to 2026-11-09, two record shapes (job runs with quota
  deltas; per-call records with status). Outcome = status / duration
  / quota cost AS LOGGED. No quality labels exist in the logs; the
  run states that limit in its result rather than inventing labels.

- **Q505 — Cost prediction under verification and retries. PASS.**
  Same log set as Q281 (shared prep, as the spec intends). Verifier
  outcome proxied by the logged status field; retries by repeated
  job records. Simulation compares accepted-task cost with and
  without a per-query predictor in the loop.

- **Q364 — Routed Continual Learning repriced (Hydra, memory). PASS.**
  Card C-routed-continual-learning carries the paper's protocol and
  cost ratios (routed full library 65-72% cheaper than one global
  history under the authors' frozen public prices). Repricing uses
  Hydra's logged model mix (from job-usage-log.jsonl) and the live
  Vertex rates. Assumptions (per-call token sizes per role) are
  stated in the run plan and in the result, not hidden.

- **Q136 — Hybrid recall vs store size (Hydra, memory). PASS.**
  Its open check was fixture cost: a query set with known targets
  built from the decision log. Built from the staged corpus instead:
  the store is seeded from the 648 take-aways (each tagged with its
  card); queries are the cards' own open questions, whose known
  targets are that card's take-aways. Recall@k measured at growing
  store sizes (subsampled prefixes), degradation slope stated.
  Uses the engrim engine installed for Q137 (hybrid lexical+vector
  recall is engrim's own path).

- **Q472 — e-means vs tuned Lloyd, small k/n (Academy). PASS.**
  CPU grid by design. Embedding sets: synthetic Gaussian mixtures
  with known structure + the corpus embedding set shared with Q471.

- **Q471 — e-means scaling laws on Academy text (Academy). PASS.**
  Corpus text staged (648 take-aways + 524 questions from the Still
  corpus — Academy-adjacent Hydra text at real scale). Embedding
  method: a small neural embedder if it downloads cleanly in the
  room, else TF-IDF/SVD; the result records which was used. This is
  the independent replication card 162 was filed as awaiting.

### DEMOTE (3)

- **Q207 — joey-1 abstention sweep. DEMOTED by its own open check.**
  The spec required routing logs carrying outcome labels, location
  and format to be confirmed at build time. Confirmed absent: no
  joey-1 scored decision logs exist anywhere in the rescued routing
  tree (no joey files at all). Nothing to replay. Needs joey-1's own
  decision records, which Hydra does not currently log.

- **Q308 — Coordination exponent. DEMOTED by its own open check.**
  Needs runs at >=3 distinct agent counts. The job-usage log carries
  no agent-count field (job titles, model, status, quota only).
  Per the spec, Q339 takes its slot — and also demotes:

- **Q339 — Obelisk retrieval on session histories. DEMOTED at check.**
  Session histories in usable form are not in the rescued material
  (routing tmp logs are test-suite outputs, not agent session
  transcripts), and KetchupPancake's chat transcripts are not exported into a
  sandbox fixture on a pilot's say-so. Remaining alternates also
  fail their checks tonight: Q201 needs a local judge model (Cora's
  27B — outside the laptop sandbox by design); Q492 needs cache
  hit/miss fields the usage logs do not carry.

## Net

8 tests run, 3 demote with named reasons. Demotion is a result:
Q207 and Q308 together say Hydra's logs do not yet record the two
things (scored routing decisions, agent counts) that two of its own
open questions need — that gap is itself a Laboratory finding.
