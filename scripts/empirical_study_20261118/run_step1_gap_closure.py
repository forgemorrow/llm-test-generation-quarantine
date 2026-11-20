import datetime
import json
import os
import random
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts._audit_repos_state import audit_all_repos
from src.execution.structured_executor import _run_pytest_with_plugin, build_env
from src.utils.swebench_loader import load_swebench_instances, isolated_instance_environment

RESULTS_DIR = PROJECT_ROOT / "results" / "empirical_study_20261118"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_PATH = RESULTS_DIR / "empirical_funnel_audit.json"
OUT_JSON = RESULTS_DIR / "step1_gap_closure.json"

CONFTEST_REQUESTS = """# Backward compatibility shim for Python 3.11+
import collections, collections.abc
for name in ['Mapping', 'MutableMapping', 'Sequence', 'Callable', 'Iterable', 'Iterator']:
    if not hasattr(collections, name) and hasattr(collections.abc, name):
        setattr(collections, name, getattr(collections.abc, name))
"""

CONFTEST_XARRAY = """# Backward compatibility shim for Python 3.11+ and NumPy 2.0+
import numpy as np
if not hasattr(np, 'unicode_'):
    np.unicode_ = np.str_
import collections, collections.abc
for name in ['Mapping', 'MutableMapping', 'Sequence', 'Callable', 'Iterable', 'Iterator']:
    if not hasattr(collections, name) and hasattr(collections.abc, name):
        setattr(collections, name, getattr(collections.abc, name))
"""

MOCK_MINIMAL_FIXTURE = """
import io
from unittest.mock import patch
import pytest
import requests
from requests.structures import CaseInsensitiveDict

@pytest.fixture(autouse=True)
def _mock_http_adapter_minimal():
    def _fake_send(self, request, **kwargs):
        resp = requests.Response()
        resp.status_code = 200
        resp.reason = "OK"
        resp.url = getattr(request, "url", "")
        resp.request = request
        resp.encoding = "utf-8"
        resp._content = b"OK"
        resp._content_consumed = True
        resp.headers = CaseInsensitiveDict({"Content-Type": "text/plain"})
        resp.raw = io.BytesIO(resp._content)
        return resp
    with patch("requests.adapters.HTTPAdapter.send", new=_fake_send):
        yield
"""

MOCK_ECHO_FIXTURE = """
import io
import json
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch
import pytest
import requests
from requests.structures import CaseInsensitiveDict

@pytest.fixture(autouse=True)
def _mock_http_adapter_echo():
    def _fake_send(self, request, **kwargs):
        url = getattr(request, "url", "") or ""
        parsed = urlparse(url)
        args = {k: (v[0] if len(v) == 1 else v) for k, v in parse_qs(parsed.query).items()}
        raw_body = getattr(request, "body", None)
        if isinstance(raw_body, bytes):
            body_str = raw_body.decode("utf-8", errors="replace")
        elif raw_body is None:
            body_str = ""
        else:
            body_str = str(raw_body)
        parsed_json = None
        if body_str:
            try:
                parsed_json = json.loads(body_str)
            except Exception:
                parsed_json = None
        headers_dict = dict(getattr(request, "headers", {}) or {})
        cookie_hdr = headers_dict.get("Cookie") or headers_dict.get("cookie") or ""
        cookies_dict = {}
        for part in cookie_hdr.split(";"):
            if "=" in part:
                ck, cv = part.strip().split("=", 1)
                cookies_dict[ck] = cv
        payload = {
            "url": url,
            "method": getattr(request, "method", "GET"),
            "headers": headers_dict,
            "args": args,
            "data": body_str,
            "json": parsed_json,
            "cookies": cookies_dict,
            "origin": "127.0.0.1",
        }
        resp = requests.Response()
        resp.status_code = 200
        resp.reason = "OK"
        resp.url = url
        resp.request = request
        resp.encoding = "utf-8"
        resp._content = json.dumps(payload).encode("utf-8")
        resp._content_consumed = True
        resp.headers = CaseInsensitiveDict({
            "Content-Type": "application/json",
            "X-Mocked": "true",
        })
        resp.raw = io.BytesIO(resp._content)
        return resp
    with patch("requests.adapters.HTTPAdapter.send", new=_fake_send):
        yield
"""

INSTANCE_CONFIGS = {
    "psf__requests-1724": {"repo_dir": "psf__requests", "py": ["."], "conftest": CONFTEST_REQUESTS},
    "psf__requests-1766": {"repo_dir": "psf__requests", "py": ["."], "conftest": CONFTEST_REQUESTS},
    "psf__requests-1921": {"repo_dir": "psf__requests", "py": ["."], "conftest": CONFTEST_REQUESTS},
    "psf__requests-2317": {"repo_dir": "psf__requests", "py": ["."], "conftest": CONFTEST_REQUESTS},
    "psf__requests-6028": {"repo_dir": "psf__requests", "py": ["."], "conftest": CONFTEST_REQUESTS},
    "pallets__flask-5014": {"repo_dir": "pallets__flask", "py": ["src"], "conftest": None},
    "sympy__sympy-15809": {"repo_dir": "sympy__sympy", "py": ["."], "conftest": None},
    "sympy__sympy-17630": {"repo_dir": "sympy__sympy", "py": ["."], "conftest": None},
    "sympy__sympy-21930": {"repo_dir": "sympy__sympy", "py": ["."], "conftest": None},
    "pydata__xarray-4075": {"repo_dir": "pydata__xarray", "py": ["."], "conftest": CONFTEST_XARRAY},
    "pydata__xarray-4356": {"repo_dir": "pydata__xarray", "py": ["."], "conftest": CONFTEST_XARRAY},
    "pydata__xarray-4966": {"repo_dir": "pydata__xarray", "py": ["."], "conftest": CONFTEST_XARRAY},
    "pydata__xarray-6744": {"repo_dir": "pydata__xarray", "py": ["."], "conftest": CONFTEST_XARRAY},
    "sympy__sympy-17139": {"repo_dir": "sympy__sympy", "py": ["."], "conftest": None},
    "sympy__sympy-22080": {"repo_dir": "sympy__sympy", "py": ["."], "conftest": None},
    "pydata__xarray-6992": {"repo_dir": "pydata__xarray", "py": ["."], "conftest": CONFTEST_XARRAY},
    "pytest-dev__pytest-7521": {"repo_dir": "pytest-dev__pytest", "py": ["src"], "conftest": None},
}

MODEL_DIRS = {
    "qwen3_8b": PROJECT_ROOT / "data" / "study_gate3",
    "qwen25_7b": PROJECT_ROOT / "data" / "cross_model_qwen25",
    "deepseek_coder_67b": PROJECT_ROOT / "data" / "cross_model_deepseek",
    "codellama_7b": PROJECT_ROOT / "data" / "cross_model_codellama",
}

def is_network_violation(t):
    et = str(t.get("error_type", ""))
    em = str(t.get("error_message", ""))
    inds = ["Hermetic CI Violation", "ConnectionError", "NewConnectionError", "Max retries exceeded with url", "Connection refused", "connection blocked"]
    if "OSError" in et and ("Hermetic CI" in em or "connectionpool" in em or "urlopen" in em):
        return True
    return any(i in em or i in et for i in inds)

def clean_wt_tests(wt: Path):
    for p in list(wt.glob("test_gen_*.py")) + list(wt.glob("_rep_*.json")) + list(wt.glob("_rep_*.json.error")):
        p.unlink(missing_ok=True)

def main():
    t0 = time.time()
    pre = audit_all_repos()
    if not pre.get("all_repos_clean", False):
        raise RuntimeError(f"Repos dirty before start: {pre}")
    print("[+] Pre-run repo audit PASSED.")

    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    swe_map = {i.instance_id: i for i in load_swebench_instances()}

    if OUT_JSON.exists():
        out = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        out["timestamp_utc"] = datetime.datetime.utcnow().isoformat() + "Z"
        print("[+] Resuming from existing checkpoint:", OUT_JSON)
    else:
        out = {
            "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
            "collection_error_full": {},
            "deepseek_timeout_resolution": {},
            "hermetic_repeatability_n20": {},
            "open_network_repeatability": {},
            "mock_remediation": {},
        }

    # ------------------------------------------------------------------
    # PART 1: Re-collect collection error files with -W ignore --tb=short
    # ------------------------------------------------------------------
    if out.get("collection_error_full"):
        print("\n=== PART 1: SKIPPED (already in checkpoint) ===")
    else:
        print("\n=== PART 1: EXACT COLLECTION ERROR TRACEBACKS (-W ignore) ===")
        coll_tasks = {}
        for mkey, mdata in audit["models"].items():
            for iid, idata in mdata["instances"].items():
                for fn, errs in idata["collection_errors_by_file"].items():
                    finfo = idata["files"][fn]
                    if finfo["syntax_ok"] and len(finfo["ast_funcs"]) > 0 and (errs or len(idata["collected_by_file"].get(fn, [])) == 0):
                        coll_tasks.setdefault(iid, []).append((mkey, fn))

        for iid, items in coll_tasks.items():
            cfg = INSTANCE_CONFIGS[iid]
            repo_dir = PROJECT_ROOT / "data" / "repos" / cfg["repo_dir"]
            with isolated_instance_environment(repo_dir, swe_map[iid], version="fixed") as wt:
                if cfg["conftest"]:
                    (wt / "conftest.py").write_text(cfg["conftest"], encoding="utf-8")
                py_paths = [str(wt / p) for p in cfg["py"]]
                env = build_env(py_paths)
                for mkey, fn in items:
                    clean_wt_tests(wt)
                    shutil.copy(MODEL_DIRS[mkey] / iid / "generated_tests" / fn, wt / fn)
                    cmd = [sys.executable, "-m", "pytest", fn, "--collect-only", "-q", "-W", "ignore", "--tb=short", "--assert=plain", "-p", "no:anyio"]
                    try:
                        proc = subprocess.run(cmd, cwd=str(wt), env=env, capture_output=True, text=True, timeout=30)
                        msg = (proc.stdout + "\n" + proc.stderr).strip()
                    except subprocess.TimeoutExpired:
                        msg = "TIMEOUT"
                    e_lines = [l.strip() for l in msg.splitlines() if l.strip().startswith("E   ")]
                    out["collection_error_full"].setdefault(mkey, {}).setdefault(iid, {})[fn] = {
                        "e_lines": e_lines,
                        "full_output": msg[:4000],
                    }
                    print(f"  {mkey:18s} {iid:23s} {fn}: {e_lines[:2]}")
        OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------
    # PART 2: Complete DeepSeek-Coder-6.7B open-network per-test resolution
    # ------------------------------------------------------------------
    print("\n=== PART 2: DEEPSEEK OPEN-NETWORK PER-TEST RESOLUTION (1724, 2317) ===")
    for iid in ["psf__requests-1724", "psf__requests-2317"]:
        if iid in out.get("deepseek_timeout_resolution", {}):
            print(f"  [SKIP] {iid} already resolved in checkpoint")
            continue
        cfg = INSTANCE_CONFIGS[iid]
        repo_dir = PROJECT_ROOT / "data" / "repos" / cfg["repo_dir"]
        all_coll = []
        for fn, nids in sorted(audit["models"]["deepseek_coder_67b"]["instances"][iid]["collected_by_file"].items()):
            all_coll.extend(nids)
        res_inst = {"fixed_open": {}, "buggy_open": {}}
        for ver, key_ver in [("fixed", "fixed_open"), ("buggy", "buggy_open")]:
            with isolated_instance_environment(repo_dir, swe_map[iid], version=ver) as wt:
                if cfg["conftest"]:
                    (wt / "conftest.py").write_text(cfg["conftest"], encoding="utf-8")
                for tf in sorted((MODEL_DIRS["deepseek_coder_67b"] / iid / "generated_tests").glob("test_gen_*.py")):
                    shutil.copy(tf, wt / tf.name)
                py_paths = [str(wt / p) for p in cfg["py"]]
                for idx_t, nid in enumerate(all_coll):
                    rep = wt / f"_rep_ds_{ver}_{idx_t}.json"
                    code, rdata, _, stderr = _run_pytest_with_plugin(
                        [nid], cwd=wt, report_file=rep, python_paths=py_paths, timeout=12
                    )
                    tests_map = rdata.get("tests", {})
                    if nid in tests_map:
                        tinfo = tests_map[nid]
                    elif tests_map:
                        tinfo = next(iter(tests_map.values()))
                    elif code == -1:
                        tinfo = {"nodeid": nid, "outcome": "TIMEOUT", "duration": 12.0, "error_type": "TimeoutExpired", "error_message": stderr[:300]}
                    else:
                        tinfo = {"nodeid": nid, "outcome": "MISSING_OBSERVATION", "duration": 0.0, "error_type": f"EXIT_{code}", "error_message": stderr[:300]}
                    tinfo["exit_code"] = code
                    res_inst[key_ver][nid] = tinfo
                    rep.unlink(missing_ok=True)
            cnt = Counter(v.get("outcome") for v in res_inst[key_ver].values())
            print(f"  deepseek {iid} {ver}: {dict(cnt)}")
        # Check bug detection cleanly
        bug_det = [
            nid for nid in all_coll
            if res_inst["fixed_open"].get(nid, {}).get("outcome") == "PASSED"
            and res_inst["buggy_open"].get(nid, {}).get("outcome") in ("ASSERTION_FAILED", "EXCEPTION")
        ]
        res_inst["bug_detected_nodeids"] = bug_det
        print(f"  deepseek {iid} bug_detected={len(bug_det)} {bug_det}")
        out["deepseek_timeout_resolution"][iid] = res_inst
    OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------
    # PART 3: N=20 SUITE_RANDOM under HERMETIC_CI=1 across ALL 4 Models
    # ------------------------------------------------------------------
    print("\n=== PART 3: N=20 SUITE_RANDOM REPEATABILITY UNDER HERMETIC_CI=1 (ALL 4 MODELS) ===")
    N_RUNS = 20
    # Collect unique instances where at least one model has collected > 0
    active_iids = sorted({
        iid
        for mkey, mdata in audit["models"].items()
        for iid, idata in mdata["instances"].items()
        if idata["collected_count"] > 0
    })
    for iid in active_iids:
        pending_models = [
            mkey for mkey in MODEL_DIRS
            if audit["models"][mkey]["instances"].get(iid, {}).get("collected_count", 0) > 0
            and iid not in out["hermetic_repeatability_n20"].get(mkey, {})
        ]
        if not pending_models:
            print(f"  [SKIP HERM N=20] {iid} (all models in checkpoint)")
            continue
        cfg = INSTANCE_CONFIGS[iid]
        repo_dir = PROJECT_ROOT / "data" / "repos" / cfg["repo_dir"]
        with isolated_instance_environment(repo_dir, swe_map[iid], version="fixed") as wt:
            if cfg["conftest"]:
                (wt / "conftest.py").write_text(cfg["conftest"], encoding="utf-8")
            py_paths = [str(wt / p) for p in cfg["py"]]

            for mkey in pending_models:
                idata = audit["models"][mkey]["instances"].get(iid)
                all_coll = []
                for fn, nids in sorted(idata["collected_by_file"].items()):
                    all_coll.extend(nids)
                clean_wt_tests(wt)
                for tf in sorted((MODEL_DIRS[mkey] / iid / "generated_tests").glob("test_gen_*.py")):
                    shutil.copy(tf, wt / tf.name)

                per_test_outcomes = {nid: [] for nid in all_coll}
                per_test_errs = {nid: set() for nid in all_coll}
                per_test_durs = {nid: [] for nid in all_coll}
                run_summaries = []

                for r_idx in range(N_RUNS):
                    seed = 42 + r_idx * 7919
                    shuffled = list(all_coll)
                    random.Random(seed).shuffle(shuffled)
                    rep = wt / f"_rep_herm_{mkey}_{r_idx}.json"
                    code, rdata, _, _ = _run_pytest_with_plugin(
                        shuffled, cwd=wt, report_file=rep, python_paths=py_paths, seed=seed,
                        timeout=45, extra_env={"HERMETIC_CI": "1"}
                    )
                    tests_map = rdata.get("tests", {})
                    oc_cnt = Counter()
                    for nid in all_coll:
                        t = tests_map.get(nid)
                        if t is None:
                            oc = "TIMEOUT_NOT_RUN" if code == -1 else "MISSING"
                            et = None
                            dur = 0.0
                        else:
                            oc = t.get("outcome", "UNKNOWN")
                            et = t.get("error_type")
                            dur = float(t.get("duration", 0.0))
                        per_test_outcomes[nid].append(oc)
                        if et:
                            per_test_errs[nid].add(et)
                        per_test_durs[nid].append(dur)
                        oc_cnt[oc] += 1
                    run_summaries.append({"run": r_idx, "seed": seed, "exit": code, "counts": dict(oc_cnt)})
                    rep.unlink(missing_ok=True)

                per_test_summary = {}
                flaky_tests = []
                for nid in all_coll:
                    ocs = per_test_outcomes[nid]
                    uniq = sorted(set(ocs))
                    c = Counter(ocs)
                    is_flaky = len(uniq) > 1
                    if is_flaky:
                        flaky_tests.append((nid, dict(c)))
                    per_test_summary[nid] = {
                        "outcomes_count": dict(c),
                        "unique_outcomes": uniq,
                        "is_flaky": is_flaky,
                        "error_types": sorted(per_test_errs[nid]),
                        "mean_duration": round(sum(per_test_durs[nid]) / len(per_test_durs[nid]), 4),
                    }
                out["hermetic_repeatability_n20"].setdefault(mkey, {})[iid] = {
                    "n_runs": N_RUNS,
                    "collected": len(all_coll),
                    "flaky_count": len(flaky_tests),
                    "flaky_tests": flaky_tests,
                    "per_test": per_test_summary,
                    "run_summaries": run_summaries,
                }
                print(f"  [HERM N=20] {mkey:18s} {iid:23s} coll={len(all_coll):3d} | flaky={len(flaky_tests):2d} {flaky_tests[:2]}", flush=True)
        OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    NET_PAIRS = [
        ("qwen3_8b", "psf__requests-1724"),
        ("qwen3_8b", "psf__requests-2317"),
        ("qwen25_7b", "psf__requests-2317"),
        ("deepseek_coder_67b", "psf__requests-1921"),
        ("deepseek_coder_67b", "psf__requests-1724"),
        ("deepseek_coder_67b", "psf__requests-2317"),
        ("codellama_7b", "psf__requests-1921"),
    ]

    # ------------------------------------------------------------------
    # PART 4A (fast!): Systematic Mock-Injection Remediation (Minimal-200 & HTTP-Echo)
    # ------------------------------------------------------------------
    print("\n=== PART 4: MOCK-INJECTION REMEDIATION UNDER HERMETIC_CI=1 ===")
    MOCK_LEVELS = [
        ("minimal_200", MOCK_MINIMAL_FIXTURE),
        ("http_echo", MOCK_ECHO_FIXTURE),
    ]
    for mkey, iid in NET_PAIRS:
        if iid in out.get("mock_remediation", {}).get(mkey, {}):
            print(f"  [SKIP MOCK] {mkey} {iid} already in checkpoint")
            continue
        cfg = INSTANCE_CONFIGS[iid]
        repo_dir = PROJECT_ROOT / "data" / "repos" / cfg["repo_dir"]
        idata = audit["models"][mkey]["instances"][iid]
        all_coll = []
        for fn, nids in sorted(idata["collected_by_file"].items()):
            all_coll.extend(nids)
        herm_orig = idata["fixed_hermetic_tests"]
        viol_nids = [nid for nid in all_coll if is_network_violation(herm_orig.get(nid, {}))]

        pair_res = {"violating_nodeids": viol_nids, "levels": {}}
        for lvl_name, lvl_code in MOCK_LEVELS:
            lvl_res = {}
            for ver in ("fixed", "buggy"):
                with isolated_instance_environment(repo_dir, swe_map[iid], version=ver) as wt:
                    conftest_txt = (cfg["conftest"] or "") + "\n" + lvl_code
                    (wt / "conftest.py").write_text(conftest_txt, encoding="utf-8")
                    py_paths = [str(wt / p) for p in cfg["py"]]
                    for tf in sorted((MODEL_DIRS[mkey] / iid / "generated_tests").glob("test_gen_*.py")):
                        shutil.copy(tf, wt / tf.name)
                    rep = wt / f"_rep_mock_{lvl_name}_{ver}.json"
                    code, rdata, _, _ = _run_pytest_with_plugin(
                        all_coll, cwd=wt, report_file=rep, python_paths=py_paths, timeout=30,
                        extra_env={"HERMETIC_CI": "1"}
                    )
                    tests_map = rdata.get("tests", {})
                    lvl_res[ver] = {"exit": code, "tests": tests_map}
            fixed_map = lvl_res["fixed"]["tests"]
            buggy_map = lvl_res["buggy"]["tests"]
            rescued_viol = [n for n in viol_nids if fixed_map.get(n, {}).get("outcome") == "PASSED"]
            still_fail_viol = {
                n: (fixed_map.get(n, {}).get("outcome"), fixed_map.get(n, {}).get("error_type"))
                for n in viol_nids if fixed_map.get(n, {}).get("outcome") != "PASSED"
            }
            new_bug_det = [
                n for n in all_coll
                if fixed_map.get(n, {}).get("outcome") == "PASSED"
                and buggy_map.get(n, {}).get("outcome") in ("ASSERTION_FAILED", "EXCEPTION")
            ]
            total_pass_fixed = sum(1 for t in fixed_map.values() if t.get("outcome") == "PASSED")
            pair_res["levels"][lvl_name] = {
                "rescued_viol_count": len(rescued_viol),
                "total_viol": len(viol_nids),
                "rescued_viol_nodeids": rescued_viol,
                "still_fail_viol": still_fail_viol,
                "total_pass_fixed": total_pass_fixed,
                "bug_detected_nodeids": new_bug_det,
                "fixed_tests": fixed_map,
                "buggy_tests": buggy_map,
            }
            print(f"  [MOCK:{lvl_name:11s}] {mkey:18s} {iid:20s} | viol_rescued={len(rescued_viol):2d}/{len(viol_nids):2d} | tot_pass={total_pass_fixed:2d}/{len(all_coll):2d} | bug_det={len(new_bug_det)}", flush=True)
        out["mock_remediation"].setdefault(mkey, {})[iid] = pair_res
        OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------
    # PART 5: Live Open-Network Repeatability (N=10) on Network Instances
    # ------------------------------------------------------------------
    print("\n=== PART 5: LIVE OPEN-NETWORK REPEATABILITY (N=10) ===")
    N_OPEN = 10
    for mkey, iid in NET_PAIRS:
        if iid in out.get("open_network_repeatability", {}).get(mkey, {}):
            print(f"  [SKIP OPEN N=10] {mkey} {iid} already in checkpoint")
            continue
        cfg = INSTANCE_CONFIGS[iid]
        repo_dir = PROJECT_ROOT / "data" / "repos" / cfg["repo_dir"]
        idata = audit["models"][mkey]["instances"][iid]
        all_coll = []
        for fn, nids in sorted(idata["collected_by_file"].items()):
            all_coll.extend(nids)
        runnable_coll = list(all_coll)

        with isolated_instance_environment(repo_dir, swe_map[iid], version="fixed") as wt:
            if cfg["conftest"]:
                (wt / "conftest.py").write_text(cfg["conftest"], encoding="utf-8")
            py_paths = [str(wt / p) for p in cfg["py"]]
            for tf in sorted((MODEL_DIRS[mkey] / iid / "generated_tests").glob("test_gen_*.py")):
                shutil.copy(tf, wt / tf.name)

            per_test_ocs = {nid: [] for nid in runnable_coll}
            per_test_errs = {nid: set() for nid in runnable_coll}
            for r_idx in range(N_OPEN):
                seed = 101 + r_idx * 7919
                shuffled = list(runnable_coll)
                random.Random(seed).shuffle(shuffled)
                rep = wt / f"_rep_open_{mkey}_{r_idx}.json"
                code, rdata, _, _ = _run_pytest_with_plugin(
                    shuffled, cwd=wt, report_file=rep, python_paths=py_paths, seed=seed, timeout=60
                )
                tests_map = rdata.get("tests", {})
                for nid in runnable_coll:
                    t = tests_map.get(nid)
                    oc = t.get("outcome", "UNKNOWN") if t else ("TIMEOUT_NOT_RUN" if code == -1 else "MISSING")
                    per_test_ocs[nid].append(oc)
                    if t and t.get("error_type"):
                        per_test_errs[nid].add(t.get("error_type"))
                rep.unlink(missing_ok=True)

            flaky = []
            per_test_sum = {}
            for nid in runnable_coll:
                ocs = per_test_ocs[nid]
                uniq = sorted(set(ocs))
                c = Counter(ocs)
                if len(uniq) > 1:
                    flaky.append((nid, dict(c)))
                per_test_sum[nid] = {"outcomes_count": dict(c), "is_flaky": len(uniq) > 1, "error_types": sorted(per_test_errs[nid])}
            out["open_network_repeatability"].setdefault(mkey, {})[iid] = {
                "n_runs": N_OPEN,
                "excluded_timeout_nodeids": [],
                "tested_count": len(runnable_coll),
                "flaky_count": len(flaky),
                "flaky_tests": flaky,
                "per_test": per_test_sum,
            }
            print(f"  [OPEN N=10] {mkey:18s} {iid:23s} tested={len(runnable_coll):2d} | flaky={len(flaky):2d} {flaky}", flush=True)
        OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    post = audit_all_repos()
    if not post.get("all_repos_clean", False):
        raise RuntimeError(f"Repos dirty after run: {post}")
    print("\n[+] Post-run repo audit PASSED: All 5 repos 100% clean.")
    out["duration_seconds"] = round(time.time() - t0, 2)
    OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Saved {OUT_JSON} in {out['duration_seconds']}s")

if __name__ == "__main__":
    main()
