#!/usr/bin/env python3
"""Night Shift pilot runner — Vera (Muse lane).

Runs the eight pilot tests in RUN-PLAN order, sequentially, each
with its timeout. A crash or timeout is recorded and the run moves
on — the night never dies on one test. Before the first test, the
runner writes MANIFEST.json into the results root: the exact
inputs this run consumed (path, size, sha256), so every output
traces to a recorded input.

Each test writes its own results/<QID>/result.json + notes.md
(the shared contract). If a test exits without producing a
result.json, the runner writes one itself with status "failed"
and says plainly that the runner wrote it.
"""
import hashlib, json, subprocess, sys, time
from datetime import datetime
from pathlib import Path

ORDER = ["Q401", "Q364", "Q137", "Q136", "Q281", "Q505", "Q472", "Q471"]
TIMEOUTS = {"Q471": 5400, "Q472": 2700}
DEFAULT_TIMEOUT = 1200

def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    pkg = Path(__file__).resolve().parent
    results = Path(sys.argv[1]) if len(sys.argv) > 1 else pkg / "results"
    results.mkdir(parents=True, exist_ok=True)
    log_path = results / "runner.log"

    def log(msg):
        line = f"{now()} {msg}"
        print(line, flush=True)
        with open(log_path, "a") as f:
            f.write(line + "\n")

    inputs = []
    for pat in ("cards/*.md", "data/*.json", "data/*.jsonl",
                "data/routing/*.jsonl", "*.py", "*.md"):
        for p in sorted(pkg.glob(pat)):
            if p.is_file() and "results" not in p.parts:
                inputs.append({"path": str(p.relative_to(pkg)),
                               "bytes": p.stat().st_size,
                               "sha256": sha256(p)})
    manifest = {"run": "nightshift-pilot-20261112", "started": now(),
                "host": "p53-wsl", "inputs": inputs, "tests": []}
    (results / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    log(f"RUN START — manifest records {len(inputs)} inputs")

    for qid in ORDER:
        script = pkg / f"{qid.lower()}.py"
        rdir = results / qid
        rdir.mkdir(parents=True, exist_ok=True)
        timeout = TIMEOUTS.get(qid, DEFAULT_TIMEOUT)
        log(f"{qid} START (timeout {timeout}s)")
        t0 = time.time()
        exit_code, tail = None, ""
        if not script.exists():
            tail = f"script missing: {script}"
        else:
            try:
                proc = subprocess.run(
                    [sys.executable, str(script), str(results)],
                    cwd=pkg, capture_output=True, text=True,
                    timeout=timeout)
                exit_code = proc.returncode
                tail = (proc.stdout + proc.stderr)[-2000:]
            except subprocess.TimeoutExpired as e:
                exit_code = "timeout"
                tail = ((e.stdout or b"").decode(errors="replace")
                        + (e.stderr or b"").decode(errors="replace"))[-2000:]
        dt = round(time.time() - t0, 1)
        (rdir / "stdout-tail.log").write_text(tail)
        rj = rdir / "result.json"
        status = None
        if rj.exists():
            try:
                status = json.loads(rj.read_text()).get("status")
            except Exception:
                status = "unreadable-result"
        if status is None:
            rj.write_text(json.dumps({
                "qid": qid, "status": "failed",
                "title": "runner-recorded failure",
                "started": None, "finished": now(), "runtime_s": dt,
                "method": "Written by runner.py: the test exited "
                          f"(exit={exit_code}) without producing a "
                          "result.json. See stdout-tail.log.",
                "assumptions": [], "headline": {},
                "records_written": [str(rj)]}, indent=1))
            status = "failed"
        log(f"{qid} END status={status} exit={exit_code} runtime={dt}s")
        manifest["tests"].append({"qid": qid, "status": status,
                                  "exit": exit_code, "runtime_s": dt})
        (results / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))

    manifest["finished"] = now()
    (results / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    done = sum(1 for t in manifest["tests"] if t["status"] in ("done", "partial"))
    log(f"RUN END — {done}/{len(ORDER)} tests produced results")

if __name__ == "__main__":
    main()
