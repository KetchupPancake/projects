Engrim hybrid recall as the store grows

Source: TOP10-TEST-SPECS-DRAFT.md Q136; CHECKS.md Engrim paragraphs; card C-engrim.

Method: Map backlog open questions to all takeaways with exactly the same card key. Keep the fixed cohort whose entire target set is present in the first 100 entries, insert original-order prefixes of 100/300/648, and invoke Engrim reciprocal-rank BM25/vector fusion separately at k=1,5,10. Report macro target recall, any-target hit rate, and OLS slope per 100 entries.

Assumptions and limits:
- CHECKS.md substitutes card-level corpus relevance for decision-log ground truth. Same-card takeaways are proxy relevance labels, not verified answers to open questions.
- All mappable questions and unmappable IDs are reported; the growth curve uses only questions with all targets already in the first prefix, so missing targets do not confound degradation.
- Recall@k is mean retrieved relevant targets / all relevant targets per question; hit rate is a separate any-target metric. Each k is run separately because Engrim changes candidate depth with k.
- Corpus order is unchanged, not randomly shuffled; growth is therefore card-ordered and not representative of arbitrary arrival orders.
- Only a real cached Engrim model2vec embedder and FTS5 are accepted as hybrid; no synthetic vectors or replacement retrieval engine. Offline mode prevents downloads and writes outside the results directory.
- Negative slope indicates degradation, positive slope improvement. No accuracy threshold is specified by the spec.

Status: blocked
Engrim semantic embedder unavailable (offline cached model2vec model required); lexical fallback is not hybrid.

Headline (null means unmeasured):
```json
{
  "backlog_queries": 525,
  "mappable_queries": 519,
  "unmappable_queries": 6,
  "fixed_queries": 76,
  "hybrid_recall_by_stage": []
}
```

Detailed fixture/mapping evidence is in result.json. A completed measurement is not a claim of production suitability.
