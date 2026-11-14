# Night Shift — Mission

Filed 2026-11-08, from the mission walk with KetchupPancake. Second pass,
revised the same day per KetchupPancake's rulings on the four reviews and
the ghost examinations; approved by KetchupPancake for filing.

**Purpose.** Hydra and Cora spending free compute while nobody is
watching: the overnight engine that improves every project while
KetchupPancake sleeps, at $0, on free lanes and Cora's spare GPU. Dreaming,
playing in a sandbox, running evals, and the low-level work that
doesn't need monitoring all live here.

**Direction.** A recursive propose, build, measure, keep-or-revert
loop. The measurement stage runs the evals — the tests and gates set
by Hydra and the Workbench Laboratory — and applies their verdicts
to decide what is kept and what is reverted. Night Shift never
grades its own work: a change it built is measured by gates it did
not write, against verdicts it reads, never verdicts it issues. It
is also where a lot of the Workbench Laboratory's tests actually
get run, where The Still's suggested tests meet spare compute, and,
once everything is working properly, Night Shift can run The
Still's own pipeline overnight. Its eval-running bleeds across the
system — into The Still, Hydra, the Laboratory, even Academy. And
one of its standing work types is Hydra's own exhaust: collecting
the monetizable data the free-tier swarm generates — model,
harness, provider and failure performance — and verifying it,
because verified is what makes it worth anything. The engine is
fully designed and barely run: its spare-compute ledger is still
empty.

The compute has to justify itself: work arrives with a named
consumer and a measurable done-condition, and every work type is
scored on whether its output was accepted and actually used —
underperformers get halved, then parked. Sealed test sets keep
growing: new failures and aced cases become harder verified cases,
saturated ones retire. The harvester
runs, the index gets tagged, summaries and expert review passes run.
Because it is the most autonomous part of the system, it is also the
most conservative: sealed answers never reach a model, nothing is
deleted, and Cora's GPU always yields to KetchupPancake.

**May do alone.** Run the approved queue overnight on free lanes
and Cora's spare GPU; keep or revert by the gates set elsewhere;
collect and verify the free-tier data; run The Still's pipeline
overnight once it is ready. The nightly forecast states what
tonight's queue will do under this authority, before it runs.

**Needs KetchupPancake.** Anything paid, anything customer-facing, changing
a gate or a sealed set, and any work the forecast did not announce.

**Good looks like.** Every morning brings a short report of what was
tried, what was kept and what was reverted, with numbers, nothing
broken, and $0 spent.
