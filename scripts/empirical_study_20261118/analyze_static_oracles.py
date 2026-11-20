import ast
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "results" / "empirical_study_20261118"
AUDIT = json.loads((RESULTS_DIR / "empirical_funnel_audit.json").read_text(encoding="utf-8"))

MODEL_DIRS = {
    "qwen3_8b": ROOT / "data" / "study_gate3",
    "qwen25_7b": ROOT / "data" / "cross_model_qwen25",
    "deepseek_coder_67b": ROOT / "data" / "cross_model_deepseek",
    "codellama_7b": ROOT / "data" / "cross_model_codellama",
}

CORE_13 = {
    "psf__requests-1724", "psf__requests-1766", "psf__requests-1921",
    "psf__requests-2317", "psf__requests-6028", "pallets__flask-5014",
    "sympy__sympy-15809", "sympy__sympy-17630", "sympy__sympy-21930",
    "pydata__xarray-4075", "pydata__xarray-4356", "pydata__xarray-4966",
    "pydata__xarray-6744",
}

URL_RE = re.compile(r"https?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[^\s'\"\)]+", re.I)

def is_network_violation(t):
    et = str(t.get("error_type", ""))
    em = str(t.get("error_message", ""))
    inds = ["Hermetic CI Violation", "ConnectionError", "NewConnectionError", "Max retries exceeded with url", "Connection refused", "connection blocked"]
    if "OSError" in et and ("Hermetic CI" in em or "connectionpool" in em or "urlopen" in em):
        return True
    return any(i in em or i in et for i in inds)

def node_has_url_literal(ast_node):
    for sub in ast.walk(ast_node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            if URL_RE.search(sub.value):
                return True
        elif isinstance(sub, ast.JoinedStr):
            joined = "".join(
                v.value for v in sub.values if isinstance(v, ast.Constant) and isinstance(v.value, str)
            )
            if URL_RE.search(joined):
                return True
    return False

def inspect_func_ast(fn_node, src_lines):
    has_assert_stmt = False
    has_pytest_raises = False
    has_unittest_assert = False
    has_tautological_assert = False
    assert_count = 0
    for n in ast.walk(fn_node):
        if isinstance(n, ast.Assert):
            assert_count += 1
            has_assert_stmt = True
            if isinstance(n.test, ast.Constant) and n.test.value is True:
                has_tautological_assert = True
        elif isinstance(n, ast.Attribute) and n.attr == "raises":
            has_pytest_raises = True
            assert_count += 1
        elif isinstance(n, ast.Call):
            if isinstance(n.func, ast.Attribute) and n.func.attr.startswith("assert"):
                has_unittest_assert = True
                assert_count += 1
                if n.func.attr == "assertTrue" and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value is True:
                    has_tautological_assert = True
    # Check AST string literals strictly (excluding comments)
    has_func_url = node_has_url_literal(fn_node)
    return {
        "assert_count": assert_count,
        "has_any_oracle": has_assert_stmt or has_pytest_raises or has_unittest_assert,
        "has_tautological": has_tautological_assert,
        "has_func_url": has_func_url,
    }

out_summary = {}
for mkey, mdata in AUDIT["models"].items():
    subsets = [("ALL_17", mdata["instances"])] if mkey == "qwen3_8b" else []
    subsets.append(("CORE_13", {k: v for k, v in mdata["instances"].items() if k in CORE_13}))

    m_out = {}
    for sname, insts in subsets:
        syn_err_files = 0
        regex_test_defs_in_syn_err = 0
        zero_fn_files = 0
        zero_fn_cats = Counter()
        files_with_mock_import = 0
        files_using_mock = 0
        ast_total = 0
        zero_oracle_ast = 0
        taut_ast = 0

        # Static file/class/func URL confusion on collected tests
        func_tp = func_fp = func_fn = func_tn = 0
        scope_tp = scope_fp = scope_fn = scope_tn = 0

        for iid, idata in insts.items():
            for fn, finfo in idata["files"].items():
                p = MODEL_DIRS[mkey] / iid / "generated_tests" / fn
                txt = p.read_text(encoding="utf-8", errors="replace")
                lines = txt.splitlines()

                if not finfo["syntax_ok"]:
                    syn_err_files += 1
                    cands = re.findall(r"^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(", txt, flags=re.M)
                    regex_test_defs_in_syn_err += len(cands)
                    continue

                tree = ast.parse(txt)
                # Mock import & usage
                uses_mock = ("unittest.mock" in txt or "from mock" in txt or "monkeypatch" in txt or "@patch" in txt or "Mock(" in txt or "MagicMock" in txt)
                if finfo.get("has_mock_import") or "monkeypatch" in txt:
                    files_with_mock_import += 1
                if uses_mock:
                    files_using_mock += 1

                if len(finfo["ast_funcs"]) == 0:
                    zero_fn_files += 1
                    fn_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                    cls_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                    if txt.lstrip().startswith("###") or "Comprehensive Test Suite" in txt[:120]:
                        zero_fn_cats["Markdown/Prose Dump"] += 1
                    elif any(not nm.startswith("test_") for nm in fn_names):
                        zero_fn_cats["Source Code Paraphrase/Helper"] += 1
                    elif "print(" in txt or "assert " in txt:
                        zero_fn_cats["Top-Level Script (no def test_)"] += 1
                    else:
                        zero_fn_cats["Empty/Definitions Only"] += 1
                    continue

                # Analyze test functions + class setUp/module scope URLs via strict AST literals
                module_level_urls = False
                for node in tree.body:
                    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Expr)) and node_has_url_literal(node):
                        module_level_urls = True

                class_has_setup_url = {}
                func_meta = {}
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        c_url = False
                        for item in node.body:
                            if isinstance(item, (ast.Assign, ast.AnnAssign)) or (isinstance(item, ast.FunctionDef) and item.name in ("setUp", "setUpClass", "setup_method")):
                                if node_has_url_literal(item):
                                    c_url = True
                        class_has_setup_url[node.name] = c_url
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) and item.name.startswith("test"):
                                k = f"{fn}::{node.name}::{item.name}"
                                r = inspect_func_ast(item, lines)
                                r["scope_url"] = r["has_func_url"] or c_url or module_level_urls
                                func_meta[k] = r
                                ast_total += 1
                                if not r["has_any_oracle"]:
                                    zero_oracle_ast += 1
                                if r["has_tautological"]:
                                    taut_ast += 1
                    elif isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
                        k = f"{fn}::{node.name}"
                        r = inspect_func_ast(node, lines)
                        r["scope_url"] = r["has_func_url"] or module_level_urls
                        func_meta[k] = r
                        ast_total += 1
                        if not r["has_any_oracle"]:
                            zero_oracle_ast += 1
                        if r["has_tautological"]:
                            taut_ast += 1

                # Confusion matrices on collected tests in fixed_hermetic_tests
                for nid, ht in idata["fixed_hermetic_tests"].items():
                    if not nid.startswith(fn + "::"):
                        continue
                    base_nid = nid.split("[")[0]
                    fd = idata["files"][fn]["func_details"].get(nid.split("::")[-1].split("[")[0])
                    # Also lookup from func_details matching base test name
                    has_func_u = False
                    if base_nid in func_meta:
                        has_func_u = func_meta[base_nid]["has_func_url"]
                        has_scope_u = func_meta[base_nid]["scope_url"]
                    else:
                        # fallback match test function suffix
                        tshort = base_nid.split("::")[-1]
                        m = [v for k, v in func_meta.items() if k.endswith("::" + tshort)]
                        has_func_u = m[0]["has_func_url"] if m else False
                        has_scope_u = m[0]["scope_url"] if m else False
                    viol = is_network_violation(ht)
                    if has_func_u and viol: func_tp += 1
                    elif has_func_u and not viol: func_fp += 1
                    elif not has_func_u and viol: func_fn += 1
                    else: func_tn += 1

                    if has_scope_u and viol: scope_tp += 1
                    elif has_scope_u and not viol: scope_fp += 1
                    elif not has_scope_u and viol: scope_fn += 1
                    else: scope_tn += 1

        m_out[sname] = {
            "syn_err_files": syn_err_files,
            "regex_test_defs_in_syn_err": regex_test_defs_in_syn_err,
            "zero_fn_files": zero_fn_files,
            "zero_fn_cats": dict(zero_fn_cats),
            "files_with_mock_import": files_with_mock_import,
            "files_using_mock": files_using_mock,
            "ast_total_recounted": ast_total,
            "zero_oracle_ast": zero_oracle_ast,
            "tautological_ast": taut_ast,
            "func_url_cm": {"tp": func_tp, "fp": func_fp, "fn": func_fn, "tn": func_tn},
            "scope_url_cm": {"tp": scope_tp, "fp": scope_fp, "fn": scope_fn, "tn": scope_tn},
        }
    out_summary[mkey] = m_out

print(json.dumps(out_summary, indent=2))
(RESULTS_DIR / "static_oracles_summary.json").write_text(json.dumps(out_summary, indent=2), encoding="utf-8")
