# Night Shift Pilot — Run Plan (for the launch word)

Host: p53-wsl (Ubuntu 26.04 room on the P53), ~/sandbox.
Window: one night, supervised by Vera, one morning digest.
No model calls, no spend, nothing touches the sorter or the
gatekeeper, nothing leaves the sandbox except the digest.

## Order

1. Q401 (minutes) — arithmetic first, cheapest deterministic result.
2. Q364 (minutes) — repricing arithmetic over staged card + logs.
3. Q137 (fixture build + merge test, engrim).
4. Q136 (recall curve over the engrim store; reuses Q137's install).
5. Q281 + Q505 (shared log prep over job-usage-log.jsonl, then the
   tabular experiment and the simulation).
6. Q472 (small CPU grid).
7. Q471 (longest: embedding prep + scaling fit; timeboxed, partial
   results reported as partial, never padded).

Each test writes results/<QID>/result.json plus a short notes.md
into ~/sandbox/out/nightshift-pilot-20261112/. A runner logs start,
end, exit status per test to ~/sandbox/logs/. A test that crashes
is recorded as crashed with its error, and the runner moves on —
one failure never eats the night.

## Machine prep already done (2026-11-12 evening)

- P53 plugged-in sleep: never; plugged-in lid-close: do nothing
  (battery behavior untouched). Room caps 8 GB / 8 CPU.
- Room toolchain: python3, numpy, pip/venv, git (apt, at staging).
- Engrim installed into a venv in the sandbox (staging check).

## The digest (morning)

One message: per test — ran / demoted / crashed, the headline
number each spec asks for, and what it means. Raw results stay in
the sandbox out folder; the digest carries the findings, not the
files. No standing schedule follows from this pilot.
