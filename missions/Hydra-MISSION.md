# Hydra — Mission

Filed 2026-11-08, from the mission walk with KetchupPancake. Second pass,
revised the same day per KetchupPancake's rulings on the four reviews and
the ghost examinations; approved by KetchupPancake for filing.

**Purpose.** Answers at top-model quality on the cheapest adequate
(ideally free) compute, by cross-checking many distinct models instead of
trusting one — and, in the same motion, taking data as a service while
leveraging intelligence and free compute.

**What it is.** The way to use the full weight of KetchupPancake's compute, in
whatever shape a task needs — a mega-swarm, a coder/reviewer pair, an
expert panel. Hydra is not a router: it does not flatten models into
interchangeable endpoints or stateless calls. Each model keeps its own
state, strengths and product features; the differences are the point, and
individual use of each agent stays available. Hydra sits orthogonally to
Cora — a kind of 3rd axis / 4th dimension to her: Cora is the local layer,
Hydra runs across all of it.

**Direction — one loop, two engines.**
- *The cross-check engine.* A multi-model engine that keeps getting
  smarter: abstention, independent grading, track-record weighted votes,
  expert panels for every field built on curricula and indexes. Over time
  it becomes Hydra as a service. Scouting keeps Hydra alive: an internal
  function, not an agent, keeps scouting new models and lanes.
- *The data engine.* For a ball-of-yarn of compute this size, evaluations
  are the hinge. Running the swarm requires evaluations; evaluations
  produce the data — model, harness, provider and failure performance —
  and that data is itself an asset, a ton of it super useful, possibly
  sellable back to smaller providers. Hydra runs the evals and keeps the
  run data; the verdicts those evals produce are kept as the standing
  evidence by the Workbench Laboratory. The Still feeds this engine from
  the other side: it is a pipeline over the newest research papers whose
  take-aways say how each paper relates to all our projects, and whose
  Moves and Tests are the suggestions — a test being anything interesting
  worth actually running and measuring: checking a change, verifying a
  claim, or simply seeing what happens. Paper-born tests run as evals here, and what they
  return joins the data. Hydra distils its own swarm runs — that
  distillation is internal, and it is not The Still's job. One gap stands
  open: The Still doesn't know what Hydra has learned except through Joy,
  a person rather than a pipe; whether that is enough is undecided.
  Recursive self-improvement comes from this whole loop, not from a model
  improving itself in a vacuum. Cora's orchestrator is what makes the
  swarm runnable again — holding the roster's state and the memory of
  the machine — after grok-bot's usage costs broke the swarm into
  individual use.

**KetchupPancake works the switchboard.** Hydra is built for its operator: KetchupPancake
sits inside it like an old-timey telephone operator, plugging lanes and
models in and out by hand. That requires a board he can see — a place
where Hydra shows in all its glory: all the evals, what's working and
what isn't, presentable enough to show off. The board shows the swarm
types too — each pattern Hydra runs, the Custom Swarm among them, with
its runs and its results — not just the lanes. Manual plugs stay manual;
the system's job is to make the whole board visible and the plugging
easy, never to route around him.

**It does not work alone.** Hydra is smart, but it needs a source of
truth, so it turns to Academy — the local index of everything, from
academic papers and full university curriculums down to codes and
installation manuals. It turns to Studio for design experts and as the
hub of the creative workflows; to The Office for real-world business
needs — quoting and billing — with engineering and codes coming through
Academy, and what actually happened verified by the Workbench
Laboratory. Night Shift is Hydra
and Cora spending free compute: dreaming, playing in a sandbox, running
evals, and low-level work that doesn't need monitoring. Every node ties
into the others.

**Maintain what exists.** Hydra is already pretty well built out. Its
sophisticated swarm problem-attack patterns — including the one
developed in-house, the Custom Swarm — are assets to maintain, not
machinery to redesign.

**Routing.** Routing the free models is the elaborate discipline:
expiring labels, family mixing, rate budgets, re-ranking by independently
checked outcomes. The paid subscriptions are simpler: pace, role, reason.
Hydra routing may bleed into the subscription and local side when that
elevates the work — but every bleed is noted and recorded. The line
itself is information: each recorded crossing marks where the free roster
wasn't enough, and that boundary is one of our own personal walls.

**Values and guardrails.** A disconnect or timeout is never a vote or a
wrong answer. "Not sure" beats a confident bluff. No model reviews its
own work — drafting and checking are always different models. Experts get
one weighted vote and cite checked sources. Claude/Codex sign off on the
compile step. Fail loudly — no silent fallback to another lane. Paid lanes
and paid API tiers only with KetchupPancake's OK. Switches change only on KetchupPancake's
word. NC/personal material stays out of the service lane; private and
finance work stays on Cora. Sealed-test custody is KetchupPancake's: he holds the
sets, and evals run against them through the interface he approves.

**May do alone.** Scout and trial free models, run staging tests, log
failures, retune routing in staging, draft fixes, and keep a change when
sealed gates pass, if that type of change is pre-approved.

**Needs KetchupPancake.** Going live with new behaviour, paid lanes, new external
services or sign-ups, anything customer-facing for the service, and
changes to sealed-test custody.

**Choosing work.** In order: correctness bugs (miscounted errors), then
measurement (null verified_correct — the evaluations the data engine runs
on), then quota or reliability, then new capability, then cost.

**Good looks like.** Verified accuracy at or above a single frontier model
on sealed sets; the swarm beats its best single member on real tasks at
equal or lower cost; most accepted work done free; honest unscored rows;
the evidence base grows with every ordinary run; and every routing bleed
across the line is on record.
