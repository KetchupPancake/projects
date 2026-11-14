Engrim merge / provenance fixture

Source: TOP10-TEST-SPECS-DRAFT.md Q137; CHECKS.md Engrim paragraphs; card C-engrim.

Method: Create two diverging SQLite stores with shared ancestry using Engrim add/supersede; merge in both directions using merge_store, repeat for idempotence, compare every native provenance field and retrieve active contradictions plus stale history.

Assumptions and limits:
- Engrim 1.4.11 has status, links, source and origin_agent fields, but no dedicated supersedes edge. Fixture links use stable fixture URIs to express ancestry, not store-local numeric IDs.
- Contradiction success means both incompatible active facts remain and are retrievable with provenance; no automatic semantic contradiction detector is assumed.
- Embeddings are disabled for this deterministic provenance fixture; recall uses Engrim lexical retrieval. Q136 separately requires genuine hybrid retrieval.
- Numeric row IDs are local and excluded from provenance equality. Shared ancestor status must propagate monotonically.

Status: done
All fixture assertions passed.

Headline (null means unmeasured):
```json
{
  "fixture_records": 4,
  "provenance_intact_fraction": 1.0,
  "contradictions_retained": true,
  "both_versions_retrieved": true,
  "passed": true
}
```

Detailed fixture/mapping evidence is in result.json. A completed measurement is not a claim of production suitability.
