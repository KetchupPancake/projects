# Follow-up from the pilot checks — logging gaps (KetchupPancake's ruling, 2026-11-12)

Source: pilot build-time checks (CHECKS.md). Q207 demoted because no
scored routing decisions are logged anywhere; Q308 demoted because
no run record carries an agent count. KetchupPancake, 2026-11-12 ~22:01 MT:
"we should definitely record scored routing decisions and agent
counts."

## The two records to add

1. **Scored routing decisions** — one record per routing choice:
   timestamp, task/job id, the candidates considered with the score
   each was given, the candidate chosen, and the outcome when it
   becomes known (status at minimum; quality label if one exists).
   A decision without its considered-and-rejected alternatives
   cannot be replayed — that is exactly what Q207 needed.

2. **Agent counts on runs** — every multi-agent run record carries
   the agent count and the composition (which models, how many of
   each). Single-agent runs record 1. Without this, no
   coordination-scaling question (Q308) can ever be answered from
   our own data.

## Where it lands

- The job logger (job-usage-log.jsonl shape) gains the agent-count
  fields — small change, backward compatible.
- Scored decisions want their own append-only log beside it
  (routing-decisions.jsonl), keyed by job id so outcomes can join.
- The durable home for both is the hydra-evals schema when that
  track resumes (it already demands provenance-first run records).

## What it unblocks

The first night these records exist with any history behind them,
Q207 (abstention sweep) and Q308 (coordination exponent) come off
the demoted list and into the run set. Instrumentation first,
questions second — the pilot's demotions are the specification.

Status: direction decided by KetchupPancake; the wiring is a build, awaiting
his go like every other build. Not started.
