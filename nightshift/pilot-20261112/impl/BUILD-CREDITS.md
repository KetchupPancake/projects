# Who built what — pilot implementations (2026-11-12 evening)

Built in parallel by all five lanes, one shared contract
(../CONTRACT rules: same result format, no invented numbers,
blocked tests still file a result):

- q471.py, q472.py — Claude (e-means pair)
- q137.py, q136.py — Codex (Engrim pair)
- q281.py, q505.py — Grok (job-log pair)
- q364.py, q401.py — Argon via Vertex (arithmetic pair; q401 also
  verifies the earlier single-builder draft, which it replaced)
- runner.py — Vera/Muse (integration, manifest, sequencing)

Integration fixes by Vera: one spaced-identifier typo in Argon's
q364.py (`asym_cache_savings_pct_ range`), fixed by exact-string
replacement against Argon's pristine reply; nothing else altered.
All eight scripts pass py_compile. Lane caveats live in each
script's assumptions and in the results' notes.md.

Room layout note: in the run room the scripts sit flat in the
package root beside runner.py (its manifest globs the package
root); this impl/ folder is the archival layout.
