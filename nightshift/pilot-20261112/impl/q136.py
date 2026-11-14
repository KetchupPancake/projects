#!/usr/bin/env python3
"""Night Shift Engrim driver; run from the staged package directory."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

QID = 'Q136'
TITLE = 'Engrim hybrid recall as the store grows'
METHOD = 'Map backlog open questions to all takeaways with exactly the same card key. Keep the fixed cohort whose entire target set is present in the first 100 entries, insert original-order prefixes of 100/300/648, and invoke Engrim reciprocal-rank BM25/vector fusion separately at k=1,5,10. Report macro target recall, any-target hit rate, and OLS slope per 100 entries.'
ASSUMPTIONS = ['CHECKS.md substitutes card-level corpus relevance for decision-log ground truth. Same-card takeaways are proxy relevance labels, not verified answers to open questions.', 'All mappable questions and unmappable IDs are reported; the growth curve uses only questions with all targets already in the first prefix, so missing targets do not confound degradation.', 'Recall@k is mean retrieved relevant targets / all relevant targets per question; hit rate is a separate any-target metric. Each k is run separately because Engrim changes candidate depth with k.', 'Corpus order is unchanged, not randomly shuffled; growth is therefore card-ordered and not representative of arbitrary arrival orders.', 'Only a real cached Engrim model2vec embedder and FTS5 are accepted as hybrid; no synthetic vectors or replacement retrieval engine. Offline mode prevents downloads and writes outside the results directory.', 'Negative slope indicates degradation, positive slope improvement. No accuracy threshold is specified by the spec.']
INNER = "import contextlib, io, json, sys, traceback\nfrom pathlib import Path\np = json.load(sys.stdin)\ndef run():\n    try:\n        import engrim\n        import engrim.cli as e\n    except ImportError as exc:\n        return dict(status='blocked', reason='Engrim unavailable: '+str(exc), headline={})\n    if engrim.__version__ != '1.4.11':\n        return dict(status='blocked', reason='Requires Engrim 1.4.11; found '+engrim.__version__, headline={})\n    import statistics, time\n    fn, model = e._resolve_embedder()\n    if fn is None:\n        return dict(status='blocked', reason='Engrim semantic embedder unavailable (offline cached model2vec model required); lexical fallback is not hybrid.', headline=dict(mappable_queries=len(p['queries']), hybrid_recall_by_stage=[]))\n    c = e.connect(str(Path(p['scratch'])/'recall.db'))\n    if not e._fts_available(c):\n        return dict(status='blocked', reason='SQLite FTS5 unavailable; cannot measure BM25+vector hybrid.', headline={})\n    project = 'nightshift-q136'\n    queries, takes = p['queries'], p['takeaways']\n    first_ids = {t['tid'] for t in takes[:100]}\n    fixed = [q for q in queries if set(q['targets']) <= first_ids]\n    if not fixed:\n        return dict(status='blocked', reason='No mapped questions have all targets in first 100 entries.', headline={})\n    ids, stages, evidence = {}, [], []\n    previous = 0\n    for n in [100,300,648]:\n        for t in takes[previous:n]:\n            mid = e.add_memory(c, project=project, type='decision', summary=t['takeaway'],\n                               source=t['tid'], origin_agent='cli', links=[t['card']])\n            ids[mid] = t['tid']\n        embedded = c.execute('SELECT COUNT(*) FROM embedding').fetchone()[0]\n        if embedded != n:\n            return dict(status='partial', reason='Not all entries were embedded; hybrid measurement stopped.',\n                        headline=dict(hybrid_recall_by_stage=stages, mappable_queries=len(queries)), embedded=embedded)\n        values = {k:[] for k in [1,5,10]}\n        hits = {k:[] for k in values}\n        semantic_hits = 0\n        for q in fixed:\n            target = set(q['targets'])\n            per = dict(stage=n, qid=q['qid'], targets=q['targets'], retrieved={})\n            for k in values:\n                sem = e._semantic_rows(c, project, q['question'], k*2)\n                semantic_hits += int(bool(sem))\n                rows = e._minder_rows(c, project, q['question'], q['question'], k)\n                got = [ids[r['id']] for r in rows]\n                overlap = len(target & set(got))\n                values[k].append(overlap/len(target))\n                hits[k].append(int(overlap>0))\n                per['retrieved'][str(k)] = got\n            evidence.append(per)\n        stages.append(dict(entries=n, fixed_queries=len(fixed), embedded=embedded,\n            recall_at_k={str(k):statistics.mean(v) for k,v in values.items()},\n            hit_rate_at_k={str(k):statistics.mean(v) for k,v in hits.items()},\n            queries_with_semantic_candidates_across_k=semantic_hits))\n        previous=n\n    slopes={}\n    xs=[s['entries'] for s in stages]; mx=statistics.mean(xs)\n    for k in ['1','5','10']:\n        ys=[s['recall_at_k'][k] for s in stages]; my=statistics.mean(ys)\n        slopes[k]=100*sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs)\n    c.close()\n    return dict(status='done', headline=dict(mappable_queries=len(queries), fixed_queries=len(fixed),\n                hybrid_recall_by_stage=stages, recall_slope_per_100_entries=slopes),\n                embedding_model=model, query_target_map=queries, fixed_query_ids=[q['qid'] for q in fixed], retrieval_evidence=evidence)\n\ntry:\n    with contextlib.redirect_stdout(io.StringIO()):\n        answer = run()\nexcept Exception as exc:\n    answer = dict(status='failed', reason=type(exc).__name__+': '+str(exc), traceback=traceback.format_exc(), headline={})\nprint(json.dumps(answer))\n"

def prepare_payload():
    takes = json.loads(Path('data/takeaways-full.json').read_text())
    backlog = json.loads(Path('data/backlog-full.json').read_text())
    if len(takes) != 648:
        raise ValueError('Expected staged corpus of 648 takeaways, found '+str(len(takes)))
    if len({t['tid'] for t in takes}) != len(takes):
        raise ValueError('Duplicate takeaway IDs')
    cards = {}
    for t in takes:
        cards.setdefault(t['card'], []).append(t['tid'])
    mapped, unmapped = [], []
    for q in backlog:
        targets = cards.get(q.get('card'), [])
        if targets and q.get('question', '').strip():
            mapped.append(dict(qid=q['qid'], card=q['card'], question=q['question'], targets=targets))
        else:
            unmapped.append(q.get('qid'))
    return dict(takeaways=takes, queries=mapped, mapping_report=dict(
        mapping_counts=dict(backlog_queries=len(backlog), mappable_queries=len(mapped), unmappable_queries=len(unmapped),
                            fixed_queries=sum(set(q['targets']) <= {t['tid'] for t in takes[:100]} for q in mapped)),
        unmappable_query_ids=unmapped, query_target_map=mapped))

def main():
    started = datetime.datetime.now().astimezone().isoformat()
    clock = time.monotonic()
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else './results') / QID
    dest.mkdir(parents=True, exist_ok=True)
    result = dict(qid=QID, title=TITLE, status='blocked', started=started,
                  method=METHOD, assumptions=ASSUMPTIONS, headline={})
    try:
        payload = prepare_payload()
        result.update(payload.get('mapping_report', {}))
        result['headline'].update(payload['mapping_report']['mapping_counts'])
        with tempfile.TemporaryDirectory(prefix='scratch-', dir=dest) as scratch:
            env = os.environ.copy()
            env.update(PYTHONDONTWRITEBYTECODE='1', ENGRIM_NO_GLOBAL='1',
                       HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                       HF_HUB_DISABLE_PROGRESS_BARS='1', TMPDIR=str(Path(scratch).resolve()))
            payload['scratch'] = str(Path(scratch).resolve())
            proc = subprocess.run([env.get('ENGRIM_PY', '/home/user/sandbox/venvs/engrim/bin/python'),
                                   '-B', '-c', INNER], input=json.dumps(payload),
                                  capture_output=True, text=True, env=env, timeout=1140)
            result['inner_stderr'] = proc.stderr[-6000:]
            if proc.returncode:
                result.update(status='failed', reason='Engrim inner process exited %s' % proc.returncode,
                              inner_stdout=proc.stdout[-6000:])
            else:
                answer = json.loads(proc.stdout)
                answer['headline'] = {**result['headline'], **answer.get('headline', {})}
                result.update(answer)
    except (FileNotFoundError, PermissionError) as exc:
        result.update(status='blocked', reason='Engrim interpreter or input unavailable: ' + str(exc))
    except subprocess.TimeoutExpired:
        result.update(status='partial', reason='Stopped at 1140-second child time budget; no complete benchmark reported.')
    except Exception as exc:
        result.update(status='failed', reason=type(exc).__name__ + ': ' + str(exc))
    result.update(finished=datetime.datetime.now().astimezone().isoformat(),
                  runtime_s=round(time.monotonic()-clock, 6),
                  records_written=[str(dest/'result.json'), str(dest/'notes.md')])
    (dest/'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
    notes = (TITLE+'\n\nSource: TOP10-TEST-SPECS-DRAFT.md '+QID+
             '; CHECKS.md Engrim paragraphs; card C-engrim.\n\nMethod: '+METHOD+
             '\n\nAssumptions and limits:\n'+''.join('- '+a+'\n' for a in ASSUMPTIONS)+
             '\nStatus: '+result['status']+'\n'+result.get('reason', '')+
             '\n\nHeadline (null means unmeasured):\n```json\n'+json.dumps(result['headline'], indent=2)+
             '\n```\n\nDetailed fixture/mapping evidence is in result.json. A completed measurement is not a claim of production suitability.\n')
    (dest/'notes.md').write_text(notes)

if __name__ == '__main__':
    main()
