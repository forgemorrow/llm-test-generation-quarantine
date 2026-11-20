import ast
import datetime
import json
import os
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts._audit_repos_state import audit_all_repos
from src.execution.structured_executor import (
    discover_test_nodeids,
    _run_pytest_with_plugin,
)
from src.triage.risk_triage import extract_static_features_from_file
from src.utils.swebench_loader import load_swebench_instances, isolated_instance_environment

RESULTS_DIR = PROJECT_ROOT / "results" / "empirical_study_20261118"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSON = RESULTS_DIR / "empirical_funnel_audit.json"

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

INSTANCE_CONFIGS = {
    "psf__requests-1724": {"repo": "psf/requests", "repo_dir": "psf__requests", "py": ["."], "conftest": CONFTEST_REQUESTS, "domain": "HTTP / Networking"},
    "psf__requests-1766": {"repo": "psf/requests", "repo_dir": "psf__requests", "py": ["."], "conftest": CONFTEST_REQUESTS, "domain": "HTTP / Networking"},
    "psf__requests-1921": {"repo": "psf/requests", "repo_dir": "psf__requests", "py": ["."], "conftest": CONFTEST_REQUESTS, "domain": "HTTP / Networking"},
    "psf__requests-2317": {"repo": "psf/requests", "repo_dir": "psf__requests", "py": ["."], "conftest": CONFTEST_REQUESTS, "domain": "HTTP / Networking"},
    "psf__requests-6028": {"repo": "psf/requests", "repo_dir": "psf__requests", "py": ["."], "conftest": CONFTEST_REQUESTS, "domain": "HTTP / Networking"},
    "pallets__flask-5014": {"repo": "pallets/flask", "repo_dir": "pallets__flask", "py": ["src"], "conftest": None, "domain": "Web Framework"},
    "sympy__sympy-15809": {"repo": "sympy/sympy", "repo_dir": "sympy__sympy", "py": ["."], "conftest": None, "domain": "Symbolic Mathematics"},
    "sympy__sympy-17630": {"repo": "sympy/sympy", "repo_dir": "sympy__sympy", "py": ["."], "conftest": None, "domain": "Symbolic Mathematics"},
    "sympy__sympy-21930": {"repo": "sympy/sympy", "repo_dir": "sympy__sympy", "py": ["."], "conftest": None, "domain": "Symbolic Mathematics"},
    "pydata__xarray-4075": {"repo": "pydata/xarray", "repo_dir": "pydata__xarray", "py": ["."], "conftest": CONFTEST_XARRAY, "domain": "Scientific Computing"},
    "pydata__xarray-4356": {"repo": "pydata/xarray", "repo_dir": "pydata__xarray", "py": ["."], "conftest": CONFTEST_XARRAY, "domain": "Scientific Computing"},
    "pydata__xarray-4966": {"repo": "pydata/xarray", "repo_dir": "pydata__xarray", "py": ["."], "conftest": CONFTEST_XARRAY, "domain": "Scientific Computing"},
    "pydata__xarray-6744": {"repo": "pydata/xarray", "repo_dir": "pydata__xarray", "py": ["."], "conftest": CONFTEST_XARRAY, "domain": "Scientific Computing"},
    # Additional 4 instances evaluated in Qwen3-8B study_gate3:
    "sympy__sympy-17139": {"repo": "sympy/sympy", "repo_dir": "sympy__sympy", "py": ["."], "conftest": None, "domain": "Symbolic Mathematics"},
    "sympy__sympy-22080": {"repo": "sympy/sympy", "repo_dir": "sympy__sympy", "py": ["."], "conftest": None, "domain": "Symbolic Mathematics"},
    "pydata__xarray-6992": {"repo": "pydata/xarray", "repo_dir": "pydata__xarray", "py": ["."], "conftest": CONFTEST_XARRAY, "domain": "Scientific Computing"},
    "pytest-dev__pytest-7521": {"repo": "pytest-dev/pytest", "repo_dir": "pytest-dev__pytest", "py": ["src"], "conftest": None, "domain": "Testing Tools"},
}

CORE_13 = [
    "psf__requests-1724", "psf__requests-1766", "psf__requests-1921",
    "psf__requests-2317", "psf__requests-6028", "pallets__flask-5014",
    "sympy__sympy-15809", "sympy__sympy-17630", "sympy__sympy-21930",
    "pydata__xarray-4075", "pydata__xarray-4356", "pydata__xarray-4966",
    "pydata__xarray-6744",
]
ALL_17 = CORE_13 + [
    "sympy__sympy-17139", "sympy__sympy-22080", "pydata__xarray-6992", "pytest-dev__pytest-7521"
]

MODELS = {
    "qwen3_8b": (PROJECT_ROOT / "data" / "study_gate3", ALL_17),
    "qwen25_7b": (PROJECT_ROOT / "data" / "cross_model_qwen25", CORE_13),
    "deepseek_coder_67b": (PROJECT_ROOT / "data" / "cross_model_deepseek", CORE_13),
    "codellama_7b": (PROJECT_ROOT / "data" / "cross_model_codellama", CORE_13),
}

def is_network_violation(test_result: dict) -> bool:
    err_type = str(test_result.get("error_type", ""))
    err_msg = str(test_result.get("error_message", ""))
    indicators = [
        "Hermetic CI Violation",
        "ConnectionError",
        "NewConnectionError",
        "Max retries exceeded with url",
        "Connection refused",
        "connection blocked",
    ]
    if "OSError" in err_type and ("Hermetic CI" in err_msg or "connectionpool" in err_msg or "urlopen" in err_msg):
        return True
    return any(ind in err_msg or ind in err_type for ind in indicators)

def classify_ast_file(tf: Path):
    txt = tf.read_text(encoding="utf-8", errors="replace")
    res = {
        "file": tf.name,
        "lines": len(txt.splitlines()),
        "syntax_ok": True,
        "syntax_err": None,
        "ast_funcs": [],
        "func_details": {},
        "has_relative_import": False,
        "has_mock_import": False,
        "has_assert_stmt": ("assert " in txt or "assertEqual" in txt or "assertTrue" in txt or "pytest.raises" in txt),
    }
    try:
        tree = ast.parse(txt)
    except SyntaxError as e:
        res["syntax_ok"] = False
        res["syntax_err"] = f"{e.msg} (line {e.lineno})"
        return res

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                res["has_relative_import"] = True
            if node.module and "mock" in node.module:
                res["has_mock_import"] = True
        elif isinstance(node, ast.Import):
            for a in node.names:
                if "mock" in a.name:
                    res["has_mock_import"] = True

    feats = extract_static_features_from_file(tf)
    for tname, f in feats.items():
        res["ast_funcs"].append(tname)
        urls = [c for c in f.fragile_calls if c.startswith("external_url:")]
        non_url = [c for c in f.fragile_calls if not c.startswith("external_url:")]
        res["func_details"][tname] = {
            "num_assertions": f.num_assertions,
            "specificity_score": f.specificity_score,
            "fragility_score": f.fragility_score,
            "urls": urls,
            "non_url_fragile": non_url,
            "assertions_text": f.assertions_text,
        }
    return res

def main():
    t0 = time.time()
    pre = audit_all_repos()
    if not pre.get("all_repos_clean", False):
        raise RuntimeError(f"Repos not clean before start: {pre}")
    print("[+] Pre-run repo audit PASSED.")

    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    try:
        all_swe = load_swebench_instances()
    except Exception:
        os.environ.pop("HF_DATASETS_OFFLINE", None)
        all_swe = load_swebench_instances()
    swe_map = {i.instance_id: i for i in all_swe}

    results = {
        "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "models": {},
    }

    for model_key, (base_dir, inst_list) in MODELS.items():
        print(f"\n==================== RUNNING MODEL: {model_key} ({len(inst_list)} instances) ====================")
        model_res = {"instances": {}}
        for idx, iid in enumerate(inst_list, 1):
            cfg = INSTANCE_CONFIGS[iid]
            inst = swe_map[iid]
            repo_dir = PROJECT_ROOT / "data" / "repos" / cfg["repo_dir"]
            test_dir = base_dir / iid / "generated_tests"
            tfs = sorted(test_dir.glob("test_gen_*.py")) if test_dir.exists() else []

            file_records = {}
            for tf in tfs:
                file_records[tf.name] = classify_ast_file(tf)

            # Skip execution if pytest-7521? No, run discovery so we capture exact collection error cleanly!
            collected_by_file = {}
            collection_errors_by_file = {}
            all_collected = []

            with isolated_instance_environment(repo_dir, inst, version="fixed") as wt:
                if cfg["conftest"]:
                    (wt / "conftest.py").write_text(cfg["conftest"], encoding="utf-8")
                py_paths = [str(wt / p) for p in cfg["py"]]
                for tf in tfs:
                    local_tf = wt / tf.name
                    shutil.copy(tf, local_tf)
                    nids, errs = discover_test_nodeids(local_tf, cwd=wt, python_paths=py_paths, timeout=30)
                    collected_by_file[tf.name] = nids
                    collection_errors_by_file[tf.name] = errs
                    all_collected.extend(nids)

                # Fixed Open Network execution
                fixed_open = {}
                fixed_open_exit = None
                if all_collected:
                    rep_f = wt / f"_rep_fixed_open_{model_key}.json"
                    fixed_open_exit, rep_data, _, _ = _run_pytest_with_plugin(
                        all_collected, cwd=wt, report_file=rep_f, python_paths=py_paths, timeout=30
                    )
                    fixed_open = rep_data.get("tests", {})

                # Fixed Hermetic CI execution
                fixed_hermetic = {}
                fixed_hermetic_exit = None
                if all_collected:
                    rep_h = wt / f"_rep_fixed_herm_{model_key}.json"
                    fixed_hermetic_exit, rep_data_h, _, _ = _run_pytest_with_plugin(
                        all_collected, cwd=wt, report_file=rep_h, python_paths=py_paths, timeout=30,
                        extra_env={"HERMETIC_CI": "1"}
                    )
                    fixed_hermetic = rep_data_h.get("tests", {})

            # Buggy Open Network execution (only if any tests passed on fixed_open, or run all collected for complete symmetry)
            buggy_open = {}
            buggy_open_exit = None
            if all_collected:
                with isolated_instance_environment(repo_dir, inst, version="buggy") as bwt:
                    if cfg["conftest"]:
                        (bwt / "conftest.py").write_text(cfg["conftest"], encoding="utf-8")
                    py_paths_b = [str(bwt / p) for p in cfg["py"]]
                    for tf in tfs:
                        shutil.copy(tf, bwt / tf.name)
                    rep_b = bwt / f"_rep_buggy_open_{model_key}.json"
                    buggy_open_exit, rep_data_b, _, _ = _run_pytest_with_plugin(
                        all_collected, cwd=bwt, report_file=rep_b, python_paths=py_paths_b, timeout=30
                    )
                    buggy_open = rep_data_b.get("tests", {})

            # Summarize instance
            n_ast = sum(len(v["ast_funcs"]) for v in file_records.values())
            n_coll = len(all_collected)
            n_pass_open = sum(1 for v in fixed_open.values() if v.get("outcome") == "PASSED")
            n_pass_herm = sum(1 for v in fixed_hermetic.values() if v.get("outcome") == "PASSED")
            n_net_viol = sum(1 for v in fixed_hermetic.values() if is_network_violation(v))
            n_bug_det = sum(
                1 for nid in all_collected
                if fixed_open.get(nid, {}).get("outcome") == "PASSED"
                and buggy_open.get(nid, {}).get("outcome") in ("ASSERTION_FAILED", "EXCEPTION")
            )

            print(f"  [{idx:02d}/{len(inst_list):02d}] {iid:24s} | ast={n_ast:2d} coll={n_coll:2d} | pass_open={n_pass_open:2d} pass_herm={n_pass_herm:2d} net_viol={n_net_viol:2d} | bug_det={n_bug_det:2d}", flush=True)

            model_res["instances"][iid] = {
                "repo": cfg["repo"],
                "domain": cfg["domain"],
                "files": file_records,
                "collected_by_file": collected_by_file,
                "collection_errors_by_file": collection_errors_by_file,
                "collected_count": n_coll,
                "fixed_open_exit": fixed_open_exit,
                "fixed_open_tests": fixed_open,
                "fixed_hermetic_exit": fixed_hermetic_exit,
                "fixed_hermetic_tests": fixed_hermetic,
                "buggy_open_exit": buggy_open_exit,
                "buggy_open_tests": buggy_open,
            }
            results["models"][model_key] = model_res
            OUT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        results["models"][model_key] = model_res

    post = audit_all_repos()
    if not post.get("all_repos_clean", False):
        raise RuntimeError(f"Repos dirty post-run: {post}")
    print("\n[+] Post-run repo audit PASSED: All 5 repos 100% clean.")
    results["duration_seconds"] = round(time.time() - t0, 2)
    OUT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Wrote {OUT_JSON} in {results['duration_seconds']}s")

if __name__ == "__main__":
    main()
