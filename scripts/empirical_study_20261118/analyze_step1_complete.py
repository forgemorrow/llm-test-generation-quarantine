import ast
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "results" / "empirical_study_20261118"
AUDIT = json.loads((RESULTS_DIR / "empirical_funnel_audit.json").read_text(encoding="utf-8"))
GAP = json.loads((RESULTS_DIR / "step1_gap_closure.json").read_text(encoding="utf-8"))
OUT_JSON = RESULTS_DIR / "empirical_master_metrics.json"

MODEL_DIRS = {
    "qwen3_8b": ROOT / "data" / "study_gate3",
    "qwen25_7b": ROOT / "data" / "cross_model_qwen25",
    "deepseek_coder_67b": ROOT / "data" / "cross_model_deepseek",
    "codellama_7b": ROOT / "data" / "cross_model_codellama",
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

URL_RE = re.compile(r"https?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[^\s'\"\)]+", re.I)

def wilson_ci(k, n, z=1.959963984540054):
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = (z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)) / denom
    return [round(max(0.0, center - half) * 100, 2), round(min(1.0, center + half) * 100, 2)]

def is_network_violation(t):
    et = str(t.get("error_type", ""))
    em = str(t.get("error_message", ""))
    inds = ["Hermetic CI Violation", "ConnectionError", "NewConnectionError", "Max retries exceeded with url", "Connection refused", "connection blocked"]
    if "OSError" in et and ("Hermetic CI" in em or "connectionpool" in em or "urlopen" in em):
        return True
    return any(i in em or i in et for i in inds)

def get_complete_fixed_open(mkey, iid, idata):
    if mkey == "deepseek_coder_67b" and iid in GAP.get("deepseek_timeout_resolution", {}):
        return GAP["deepseek_timeout_resolution"][iid]["fixed_open"]
    return idata["fixed_open_tests"]

def get_complete_buggy_open(mkey, iid, idata):
    if mkey == "deepseek_coder_67b" and iid in GAP.get("deepseek_timeout_resolution", {}):
        return GAP["deepseek_timeout_resolution"][iid]["buggy_open"]
    return idata["buggy_open_tests"]

def classify_collection_err(mkey, iid, fn):
    full_info = GAP["collection_error_full"].get(mkey, {}).get(iid, {}).get(fn, {})
    e_lines = full_info.get("e_lines", [])
    full_out = full_info.get("full_output", "")
    joined = "\n".join(e_lines) if e_lines else full_out
    if "_pytest._version" in full_out or "_pytest._version" in joined:
        return "Build-Metadata / Infra Failure"
    if "attempted relative import" in joined:
        return "Relative Import Outside Package"
    if "your_module" in joined or "your_blueprint_file" in joined or "my_module" in joined:
        return "Placeholder Module Reference"
    if "ImportError" in joined or "ModuleNotFoundError" in joined:
        return "Hallucinated / Nonexistent Symbol or Module"
    if "np.object" in joined or "numpy" in joined and "AttributeError" in joined:
        return "NumPy API Compatibility Error"
    if "AssertionError" in joined or "NameError" in joined or "ValueError" in joined or "TypeError" in joined or "KeyError" in joined:
        return "Top-Level Execution Error"
    return "Other Collection Error"

def classify_runtime_fail(t):
    et = str(t.get("error_type") or "")
    em = str(t.get("error_message") or "")
    oc = t.get("outcome", "")
    if oc == "TIMEOUT":
        return "Execution Timeout"
    if is_network_violation(t) or et in ("SSLCertVerificationError", "ProxyError", "MaxRetryError", "ConnectionError", "ConnectTimeout"):
        return f"Network/TLS/Proxy Error ({et})"
    if oc == "IMPORT_ERROR" or et in ("ImportError", "ModuleNotFoundError"):
        return "Lazy Runtime ImportError"
    if "DID NOT RAISE" in em or "Failed" == et and "DID NOT RAISE" in em:
        return "Unmet Exception Expectation (pytest.raises)"
    if oc == "ASSERTION_FAILED" or et == "AssertionError":
        return "Wrong Oracle (AssertionError)"
    if et == "NameError":
        return "Undefined Symbol (NameError)"
    if et in ("TypeError", "ValueError", "AttributeError", "KeyError", "IndexError"):
        return f"API/State Runtime Error ({et})"
    return f"Other Runtime Error ({et})"

def main():
    master = {"rq1_funnel": {}, "rq1_stats": {}, "rq2_taxonomy": {}, "rq3_network": {}, "rq4_flakiness_and_mock": {}}

    # 1. RQ1 Funnel + Per-instance metrics
    cohorts = [
        ("qwen3_8b_all17", "qwen3_8b", ALL_17),
        ("qwen3_8b_core13", "qwen3_8b", CORE_13),
        ("qwen25_7b_core13", "qwen25_7b", CORE_13),
        ("deepseek_coder_67b_core13", "deepseek_coder_67b", CORE_13),
        ("codellama_7b_core13", "codellama_7b", CORE_13),
    ]
    core_per_inst_pass_open = defaultdict(list)
    core_per_inst_pass_herm = defaultdict(list)
    core_per_inst_coll = defaultdict(list)

    print("=== RQ1: MULTI-STAGE CI ATTRITION FUNNEL ===")
    for cname, mkey, inst_ids in cohorts:
        files_tot = 0
        syn_err_files = 0
        syn_err_regex_defs = 0
        zero_fn_files = 0
        zero_fn_subcats = Counter()
        clean_parse_files = 0
        raw_ast_defs = 0
        effective_ast_defs = 0
        shadowed_defs = 0
        coll_tot = 0
        pass_open = 0
        pass_herm = 0
        net_viol_herm = 0
        bug_det_open = 0
        bug_det_herm = 0
        bug_insts_open = set()
        coll_error_files_cnt = 0
        coll_loss_raw = 0
        param_expansion_extra = 0

        inst_rows = {}
        for iid in inst_ids:
            idata = AUDIT["models"][mkey]["instances"][iid]
            fixed_open = get_complete_fixed_open(mkey, iid, idata)
            buggy_open = get_complete_buggy_open(mkey, iid, idata)
            fixed_herm = idata["fixed_hermetic_tests"]

            i_ast_eff = 0
            i_raw_ast = 0
            for fn, finfo in idata["files"].items():
                files_tot += 1
                p = MODEL_DIRS[mkey] / iid / "generated_tests" / fn
                txt = p.read_text(encoding="utf-8", errors="replace")
                if not finfo["syntax_ok"]:
                    syn_err_files += 1
                    cands = re.findall(r"^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(", txt, flags=re.M)
                    syn_err_regex_defs += len(cands)
                    continue
                tree = ast.parse(txt)
                raw_defs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
                eff_cnt = len(finfo["ast_funcs"])
                raw_ast_defs += len(raw_defs)
                effective_ast_defs += eff_cnt
                shadowed_defs += (len(raw_defs) - eff_cnt)
                i_raw_ast += len(raw_defs)
                i_ast_eff += eff_cnt
                if eff_cnt == 0:
                    zero_fn_files += 1
                    fn_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                    if txt.lstrip().startswith("###") or "Comprehensive Test Suite" in txt[:120]:
                        zero_fn_subcats["Markdown/Prose Dump"] += 1
                    elif any(not nm.startswith("test_") for nm in fn_names):
                        zero_fn_subcats["Source Code Paraphrase/Helper"] += 1
                    elif "print(" in txt or "assert " in txt:
                        zero_fn_subcats["Top-Level Script (no def test_)"] += 1
                    else:
                        zero_fn_subcats["Empty/Definitions Only"] += 1
                    continue
                clean_parse_files += 1
                c_fn = len(idata["collected_by_file"].get(fn, []))
                if c_fn == 0:
                    coll_error_files_cnt += 1
                    coll_loss_raw += eff_cnt
                elif c_fn > eff_cnt:
                    param_expansion_extra += (c_fn - eff_cnt)
                elif c_fn < eff_cnt:
                    # Partial discrepancy inside collected file (e.g. non-unittest classes or parametrize skip)
                    pass

            n_coll = idata["collected_count"]
            assert len(fixed_open) == n_coll, f"Missing fixed_open tests in {mkey} {iid}: {len(fixed_open)} vs {n_coll}"
            assert len(fixed_herm) == n_coll, f"Missing fixed_herm tests in {mkey} {iid}: {len(fixed_herm)} vs {n_coll}"
            n_po = sum(1 for t in fixed_open.values() if t.get("outcome") == "PASSED")
            n_ph = sum(1 for t in fixed_herm.values() if t.get("outcome") == "PASSED")
            n_nv = sum(1 for t in fixed_herm.values() if is_network_violation(t))
            n_bd_o = sum(1 for nid in fixed_open if fixed_open[nid].get("outcome") == "PASSED" and buggy_open.get(nid, {}).get("outcome") in ("ASSERTION_FAILED", "EXCEPTION"))
            n_bd_h = sum(1 for nid in fixed_herm if fixed_herm[nid].get("outcome") == "PASSED" and buggy_open.get(nid, {}).get("outcome") in ("ASSERTION_FAILED", "EXCEPTION"))
            if n_bd_o > 0:
                bug_insts_open.add(iid)

            coll_tot += n_coll
            pass_open += n_po
            pass_herm += n_ph
            net_viol_herm += n_nv
            bug_det_open += n_bd_o
            bug_det_herm += n_bd_h

            inst_rows[iid] = {
                "effective_ast": i_ast_eff,
                "collected": n_coll,
                "pass_open": n_po,
                "pass_herm": n_ph,
                "net_viol": n_nv,
                "bug_det_open": n_bd_o,
                "bug_det_herm": n_bd_h,
            }
            if cname.endswith("core13"):
                core_per_inst_coll[mkey].append(n_coll)
                core_per_inst_pass_open[mkey].append(n_po)
                core_per_inst_pass_herm[mkey].append(n_ph)

        attempted_total = raw_ast_defs + syn_err_regex_defs
        master["rq1_funnel"][cname] = {
            "instances": len(inst_ids),
            "files_total": files_tot,
            "syn_err_files": syn_err_files,
            "syn_err_regex_defs": syn_err_regex_defs,
            "zero_fn_files": zero_fn_files,
            "zero_fn_subcats": dict(zero_fn_subcats),
            "clean_parse_files_with_tests": clean_parse_files,
            "coll_error_files_with_ast": coll_error_files_cnt,
            "attempted_total_defs": attempted_total,
            "raw_ast_defs": raw_ast_defs,
            "shadowed_defs": shadowed_defs,
            "effective_ast_defs": effective_ast_defs,
            "coll_loss_in_failed_files": coll_loss_raw,
            "param_expansion_extra": param_expansion_extra,
            "collected": coll_tot,
            "pass_open": pass_open,
            "pass_open_pct_coll": round(pass_open / max(coll_tot, 1) * 100, 2),
            "pass_open_ci_coll": wilson_ci(pass_open, coll_tot),
            "pass_open_pct_eff_ast": round(pass_open / max(effective_ast_defs, 1) * 100, 2),
            "pass_open_ci_eff_ast": wilson_ci(pass_open, effective_ast_defs),
            "pass_herm": pass_herm,
            "pass_herm_pct_coll": round(pass_herm / max(coll_tot, 1) * 100, 2),
            "pass_herm_ci_coll": wilson_ci(pass_herm, coll_tot),
            "pass_herm_pct_eff_ast": round(pass_herm / max(effective_ast_defs, 1) * 100, 2),
            "pass_herm_ci_eff_ast": wilson_ci(pass_herm, effective_ast_defs),
            "net_viol": net_viol_herm,
            "net_viol_pct_coll": round(net_viol_herm / max(coll_tot, 1) * 100, 2),
            "bug_det_open": bug_det_open,
            "bug_det_herm": bug_det_herm,
            "bug_insts_open": sorted(bug_insts_open),
            "per_instance": inst_rows,
        }
        r = master["rq1_funnel"][cname]
        print(f"  {cname:26s} | files={files_tot} (syn={syn_err_files},zero={zero_fn_files}) | attempted={attempted_total} raw_ast={raw_ast_defs} eff_ast={effective_ast_defs} | coll={coll_tot} | pass_open={pass_open} ({r['pass_open_pct_coll']}% coll, {r['pass_open_pct_eff_ast']}% ast) | pass_herm={pass_herm} ({r['pass_herm_pct_coll']}% coll, {r['pass_herm_pct_eff_ast']}% ast) | net_viol={net_viol_herm} | bug_det={bug_det_open}/{len(bug_insts_open)} insts")

    # Statistical tests across CORE_13 models (paired by instance, n=13)
    models_order = ["qwen3_8b", "qwen25_7b", "deepseek_coder_67b", "codellama_7b"]
    for metric_name, dict_src in [
        ("collected_count", core_per_inst_coll),
        ("pass_open_count", core_per_inst_pass_open),
        ("pass_herm_count", core_per_inst_pass_herm),
    ]:
        arrays = [dict_src[m] for m in models_order]
        stat, p_val = stats.friedmanchisquare(*arrays)
        pair_pvals = []
        for i in range(len(models_order)):
            for j in range(i + 1, len(models_order)):
                m1, m2 = models_order[i], models_order[j]
                diffs = [a - b for a, b in zip(dict_src[m1], dict_src[m2])]
                if any(d != 0 for d in diffs):
                    w, pw = stats.wilcoxon(dict_src[m1], dict_src[m2])
                else:
                    w, pw = 0.0, 1.0
                pair_pvals.append({"pair": f"{m1}_vs_{m2}", "W": float(w), "raw_p": float(pw)})
        # Holm correction
        pair_pvals_sorted = sorted(enumerate(pair_pvals), key=lambda x: x[1]["raw_p"])
        m_tests = len(pair_pvals)
        prev_p = 0.0
        for rank, (orig_idx, item) in enumerate(pair_pvals_sorted):
            adj = min(1.0, max(prev_p, item["raw_p"] * (m_tests - rank)))
            prev_p = adj
            pair_pvals[orig_idx]["holm_p"] = round(adj, 6)
            pair_pvals[orig_idx]["raw_p"] = round(item["raw_p"], 6)
        master["rq1_stats"][metric_name] = {
            "friedman_chi2": round(float(stat), 4),
            "friedman_p": round(float(p_val), 6),
            "pairwise_wilcoxon": pair_pvals,
        }
        print(f"  [STATS {metric_name}] Friedman chi2={stat:.3f}, p={p_val:.6f}")

    # 2. RQ2 Failure Taxonomy (Collection & Execution)
    print("\n=== RQ2: FAILURE TAXONOMY ===")
    for cname, mkey, inst_ids in cohorts:
        coll_err_cats = Counter()
        coll_err_ast_lost = Counter()
        exec_fail_open_cats = Counter()
        exec_fail_herm_cats = Counter()
        for iid in inst_ids:
            idata = AUDIT["models"][mkey]["instances"][iid]
            for fn, finfo in idata["files"].items():
                if not finfo["syntax_ok"] or len(finfo["ast_funcs"]) == 0:
                    continue
                if len(idata["collected_by_file"].get(fn, [])) == 0:
                    cat = classify_collection_err(mkey, iid, fn)
                    coll_err_cats[cat] += 1
                    coll_err_ast_lost[cat] += len(finfo["ast_funcs"])
            fixed_open = get_complete_fixed_open(mkey, iid, idata)
            fixed_herm = idata["fixed_hermetic_tests"]
            for nid, t in fixed_open.items():
                if t.get("outcome") != "PASSED":
                    exec_fail_open_cats[classify_runtime_fail(t)] += 1
            for nid, t in fixed_herm.items():
                if t.get("outcome") != "PASSED":
                    exec_fail_herm_cats[classify_runtime_fail(t)] += 1
        master["rq2_taxonomy"][cname] = {
            "collection_error_files_by_cat": dict(coll_err_cats),
            "collection_error_ast_lost_by_cat": dict(coll_err_ast_lost),
            "fixed_open_failure_cats": dict(exec_fail_open_cats),
            "fixed_hermetic_failure_cats": dict(exec_fail_herm_cats),
        }
        print(f"  [{cname}] coll_ast_lost={dict(coll_err_ast_lost)}")
        print(f"  [{cname}] open_fails({sum(exec_fail_open_cats.values())})={dict(exec_fail_open_cats.most_common(7))}")

    # 3. RQ3 Open vs Hermetic Confusion & Static URL Precision/Recall (using resolved fixed_open!)
    print("\n=== RQ3: OPEN vs HERMETIC DIVERGENCE ===")
    for cname, mkey, inst_ids in cohorts:
        if cname == "qwen3_8b_all17":
            pass
        trans = Counter()
        for iid in inst_ids:
            idata = AUDIT["models"][mkey]["instances"][iid]
            fixed_open = get_complete_fixed_open(mkey, iid, idata)
            fixed_herm = idata["fixed_hermetic_tests"]
            for nid in fixed_herm:
                oo = fixed_open[nid].get("outcome")
                ho = fixed_herm[nid].get("outcome")
                viol = is_network_violation(fixed_herm[nid])
                o_simple = "PASS" if oo == "PASSED" else "FAIL"
                h_simple = "PASS" if ho == "PASSED" else ("NET_VIOL" if viol else "NON_NET_FAIL")
                trans[f"{o_simple}_OPEN -> {h_simple}_HERM"] += 1
        master["rq3_network"][cname] = dict(trans)
        print(f"  [{cname}] {dict(trans)}")

    # 4. RQ4 Repeatability & Mock Remediation
    print("\n=== RQ4: REPEATABILITY & MOCK REMEDIATION ===")
    herm_rep_sum = {}
    for mkey in models_order:
        inst_map = GAP.get("hermetic_repeatability_n20", {}).get(mkey, {})
        tot_tests = sum(v["collected"] for v in inst_map.values())
        tot_runs_obs = sum(v["collected"] * v["n_runs"] for v in inst_map.values())
        tot_flaky = sum(v["flaky_count"] for v in inst_map.values())
        flaky_list = [ft for v in inst_map.values() for ft in v.get("flaky_tests", [])]
        herm_rep_sum[mkey] = {"instances": len(inst_map), "collected_tests": tot_tests, "total_test_executions": tot_runs_obs, "flaky_tests": tot_flaky, "flaky_details": flaky_list}
        print(f"  [HERM N=20] {mkey:20s}: insts={len(inst_map):2d} tests={tot_tests:3d} total_execs={tot_runs_obs:5d} flaky={tot_flaky} {flaky_list}")

    open_rep_sum = {}
    for mkey, inst_map in GAP.get("open_network_repeatability", {}).items():
        tot_tests = sum(v["tested_count"] for v in inst_map.values())
        tot_flaky = sum(v["flaky_count"] for v in inst_map.values())
        flaky_list = [(iid, ft) for iid, v in inst_map.items() for ft in v.get("flaky_tests", [])]
        open_rep_sum[mkey] = {"instances": len(inst_map), "tested_count": tot_tests, "flaky_tests": tot_flaky, "flaky_details": flaky_list}
        print(f"  [OPEN N=10] {mkey:20s}: insts={len(inst_map):2d} tested={tot_tests:3d} flaky={tot_flaky} {flaky_list}")

    mock_sum = {}
    for mkey, inst_map in GAP.get("mock_remediation", {}).items():
        for lvl in ("minimal_200", "http_echo"):
            tot_v = sum(v["levels"][lvl]["total_viol"] for v in inst_map.values())
            resc = sum(v["levels"][lvl]["rescued_viol_count"] for v in inst_map.values())
            bdet = sum(len(v["levels"][lvl]["bug_detected_nodeids"]) for v in inst_map.values())
            fail_cats = Counter()
            non_viol_gained = []
            non_viol_broken = []
            for iid, v in inst_map.items():
                vset = set(v["violating_nodeids"])
                orig_h = AUDIT["models"][mkey]["instances"][iid]["fixed_hermetic_tests"]
                fmap = v["levels"][lvl]["fixed_tests"]
                for nid, (oc, et) in v["levels"][lvl]["still_fail_viol"].items():
                    fail_cats[f"{oc}:{et}"] += 1
                for nid, ft in fmap.items():
                    if nid in vset:
                        continue
                    oo = orig_h.get(nid, {}).get("outcome")
                    mo = ft.get("outcome")
                    if oo != "PASSED" and mo == "PASSED":
                        non_viol_gained.append((iid, nid, oo, orig_h.get(nid, {}).get("error_type")))
                    elif oo == "PASSED" and mo != "PASSED":
                        non_viol_broken.append((iid, nid, mo, ft.get("error_type")))
            mock_sum.setdefault(mkey, {})[lvl] = {
                "total_viol": tot_v,
                "rescued": resc,
                "rescue_rate_pct": round(resc / max(tot_v, 1) * 100, 2),
                "rescue_ci": wilson_ci(resc, tot_v),
                "bug_det": bdet,
                "still_fail_reasons": dict(fail_cats),
                "non_viol_gained": non_viol_gained,
                "non_viol_broken": non_viol_broken,
            }
            print(f"  [MOCK {lvl:11s}] {mkey:20s}: rescued={resc:2d}/{tot_v:2d} ({mock_sum[mkey][lvl]['rescue_rate_pct']}%) | nv_gain={len(non_viol_gained)} nv_broke={len(non_viol_broken)} | bug_det={bdet} | remaining={dict(fail_cats)}")

    static_oracle_path = RESULTS_DIR / "static_oracles_summary.json"
    if static_oracle_path.exists():
        master["static_oracles"] = json.loads(static_oracle_path.read_text(encoding="utf-8"))

    master["rq4_flakiness_and_mock"] = {
        "hermetic_n20": herm_rep_sum,
        "open_n10": open_rep_sum,
        "mock_remediation": mock_sum,
    }

    OUT_JSON.write_text(json.dumps(master, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved complete empirical metrics to {OUT_JSON}")

if __name__ == "__main__":
    main()
