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

QID = 'Q137'
TITLE = 'Engrim merge / provenance fixture'
METHOD = 'Create two diverging SQLite stores with shared ancestry using Engrim add/supersede; merge in both directions using merge_store, repeat for idempotence, compare every native provenance field and retrieve active contradictions plus stale history.'
ASSUMPTIONS = ['Engrim 1.4.11 has status, links, source and origin_agent fields, but no dedicated supersedes edge. Fixture links use stable fixture URIs to express ancestry, not store-local numeric IDs.', 'Contradiction success means both incompatible active facts remain and are retrievable with provenance; no automatic semantic contradiction detector is assumed.', 'Embeddings are disabled for this deterministic provenance fixture; recall uses Engrim lexical retrieval. Q136 separately requires genuine hybrid retrieval.', 'Numeric row IDs are local and excluded from provenance equality. Shared ancestor status must propagate monotonically.']
INNER = "import contextlib, io, json, sys, traceback\nfrom pathlib import Path\np = json.load(sys.stdin)\ndef run():\n    try:\n        import engrim\n        import engrim.cli as e\n    except ImportError as exc:\n        return dict(status='blocked', reason='Engrim unavailable: '+str(exc), headline={})\n    if engrim.__version__ != '1.4.11':\n        return dict(status='blocked', reason='Requires Engrim 1.4.11; found '+engrim.__version__, headline={})\n    import os, argparse\n    os.environ['ENGRIM_EMBED'] = 'off'\n    root = Path(p['scratch'])\n    a = e.connect(str(root/'a.db'))\n    b = e.connect(str(root/'b.db'))\n    project = 'nightshift-q137'\n    def add(c, label, value, agent, parent=None):\n        return e.add_memory(c, project=project, type='fact',\n            summary='Aster service deployment region is '+value+'.',\n            detail='fixture record '+label, tags=['aster', label],\n            links=['fixture://'+parent] if parent else [],\n            source='fixture://'+label, origin_agent=agent)\n    old = add(a, 'base', 'us-east', 'codex')\n    a.backup(b)  # shared ancestor with identical content identity and provenance\n    add(a, 'lane-a', 'eu-west', 'codex', 'base')\n    e.cmd_supersede(a, argparse.Namespace(id=old, status='superseded'))\n    newer = add(b, 'lane-b-old', 'ap-south', 'claude', 'base')\n    add(b, 'lane-b', 'ap-northeast', 'claude', 'lane-b-old')\n    e.cmd_supersede(b, argparse.Namespace(id=newer, status='superseded'))\n    def rows(c):\n        return [dict(r) for r in c.execute('SELECT * FROM memories ORDER BY id')]\n    before_a, before_b = rows(a), rows(b)\n    expected = {r['source']:r for r in before_a+before_b}\n    expected['fixture://base']['status'] = 'superseded'\n    b.commit()\n    first = e.merge_store(a, str(root/'b.db'), project=project)\n    second = e.merge_store(a, str(root/'b.db'), project=project)\n    reverse = e.merge_store(b, str(root/'a.db'), project=project)\n    after = rows(a)\n    fields = ['ts','project','type','summary','detail','status','tags','links','source','origin_agent']\n    broken = []\n    for source, want in expected.items():\n        found = [r for r in after if r['source']==source]\n        diffs = [f for f in fields if len(found)!=1 or found[0][f]!=want[f]]\n        if diffs: broken.append(dict(source=source, fields=diffs, actual=found))\n    from engrim.mcp_server import _tool_recall\n    active = json.loads(_tool_recall(a, dict(project=project, query='Aster deployment region', k=10)))['records']\n    stale = json.loads(_tool_recall(a, dict(project=project, query='Aster deployment region', k=10, include_stale=True)))['records']\n    active_sources = {r['source'] for r in active}\n    checks = dict(provenance_intact=not broken,\n        contradictions_retained={'fixture://lane-a','fixture://lane-b'} <= {r['source'] for r in after},\n        contradictions_retrieved_with_provenance=all(any(r['source']==s and r['origin_agent']==expected[s]['origin_agent'] and r['links']==expected[s]['links'] for r in active) for s in ['fixture://lane-a','fixture://lane-b']),\n        stale_history_retrieved=set(expected) <= {r['source'] for r in stale},\n        stale_hidden_by_default=active_sources=={'fixture://lane-a','fixture://lane-b'},\n        idempotent=second[0]==0 and second[1]==0 and len(after)==len(expected),\n        bidirectional_convergence=sorted(tuple(r[f] for f in fields) for r in after)==sorted(tuple(r[f] for f in fields) for r in rows(b)))\n    a.close(); b.close()\n    return dict(status='done' if all(checks.values()) else 'failed',\n        reason='All fixture assertions passed.' if all(checks.values()) else 'Fixture assertions failed; see checks and broken_records.',\n        headline=dict(fixture_records=len(expected), provenance_intact_fraction=(len(expected)-len(broken))/len(expected),\n                      contradictions_retained=checks['contradictions_retained'],\n                      both_versions_retrieved=checks['contradictions_retrieved_with_provenance'], passed=all(checks.values())),\n        checks=checks, broken_records=broken, expected_records=list(expected.values()), merged_records=after,\n        retrieval_active=active, retrieval_include_stale=stale, merge_first=first, merge_repeat=second, merge_reverse=reverse)\n\ntry:\n    with contextlib.redirect_stdout(io.StringIO()):\n        answer = run()\nexcept Exception as exc:\n    answer = dict(status='failed', reason=type(exc).__name__+': '+str(exc), traceback=traceback.format_exc(), headline={})\nprint(json.dumps(answer))\n"

def main():
    started = datetime.datetime.now().astimezone().isoformat()
    clock = time.monotonic()
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else './results') / QID
    dest.mkdir(parents=True, exist_ok=True)
    result = dict(qid=QID, title=TITLE, status='blocked', started=started,
                  method=METHOD, assumptions=ASSUMPTIONS, headline={})
    try:
        payload = {}
        result.update(payload.get('mapping_report', {}))
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
                result.update(json.loads(proc.stdout))
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
