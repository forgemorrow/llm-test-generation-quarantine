import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results" / "empirical_study_20261118"
METRICS = json.loads((RESULTS_DIR / "empirical_master_metrics.json").read_text(encoding="utf-8"))
OUT_DIR = Path(os.environ.get("EMPIRICAL_TABLES_OUT", str(RESULTS_DIR / "tables")))
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_ORDER = ["qwen3_8b", "qwen25_7b", "deepseek_coder_67b", "codellama_7b"]
MODEL_NAMES = {
    "qwen3_8b": "Qwen3-8B",
    "qwen25_7b": "Qwen2.5-7B",
    "deepseek_coder_67b": "DeepSeek-Coder-6.7B",
    "codellama_7b": "CodeLlama-7B",
}

def tex_esc(s: str) -> str:
    return s.replace("_", r"\_")

# ------------------------------------------------------------------------------
# Table 1: SWE-bench Verified Evaluation Cohort (13 Core + 4 Extended)
# ------------------------------------------------------------------------------
BENCH_ROWS = [
    ("psf__requests-1724", "psf/requests", "HTTP / Networking", "1ba83c47", "requests/sessions.py", 6, "Core-13 (4 LLMs)"),
    ("psf__requests-1766", "psf/requests", "HTTP / Networking", "84773555", "requests/auth.py", 6, "Core-13 (4 LLMs)"),
    ("psf__requests-1921", "psf/requests", "HTTP / Networking", "3c88e520", "requests/sessions.py", 6, "Core-13 (4 LLMs)"),
    ("psf__requests-2317", "psf/requests", "HTTP / Networking", "091991be", "requests/sessions.py", 8, "Core-13 (4 LLMs)"),
    ("psf__requests-6028", "psf/requests", "HTTP / Networking", "0192aac2", "requests/utils.py", 2, "Core-13 (4 LLMs)"),
    ("pallets__flask-5014", "pallets/flask", "Web Framework", "7ee9ceb7", "src/flask/blueprints.py", 1, "Core-13 (4 LLMs)"),
    ("sympy__sympy-15809", "sympy/sympy", "Symbolic Math", "28d913d3", "sympy/functions/elementary/miscellaneous.py", 2, "Core-13 (4 LLMs)"),
    ("sympy__sympy-17630", "sympy/sympy", "Symbolic Math", "58e78209", "sympy/matrices/expressions/matexpr.py", 2, "Core-13 (4 LLMs)"),
    ("sympy__sympy-21930", "sympy/sympy", "Symbolic Math", "de446c6d", "sympy/physics/secondquant.py", 6, "Core-13 (4 LLMs)"),
    ("pydata__xarray-4075", "pydata/xarray", "Scientific Computing", "19b08863", "xarray/core/weighted.py", 2, "Core-13 (4 LLMs)"),
    ("pydata__xarray-4356", "pydata/xarray", "Scientific Computing", "e05fddea", "xarray/core/nanops.py", 8, "Core-13 (4 LLMs)"),
    ("pydata__xarray-4966", "pydata/xarray", "Scientific Computing", "37522e99", "xarray/coding/variables.py", 4, "Core-13 (4 LLMs)"),
    ("pydata__xarray-6744", "pydata/xarray", "Scientific Computing", "7cc6cc99", "xarray/core/rolling.py", 3, "Core-13 (4 LLMs)"),
    ("sympy__sympy-17139", "sympy/sympy", "Symbolic Math", "1d3327b8", "sympy/simplify/fu.py", 2, "Extended (Qwen3-8B; 0 coll.)"),
    ("sympy__sympy-22080", "sympy/sympy", "Symbolic Math", "3f8c8c23", "sympy/printing/codeprinter.py, precedence.py", 3, "Extended (Qwen3-8B; 0 AST)"),
    ("pydata__xarray-6992", "pydata/xarray", "Scientific Computing", "45c0a114", "xarray/core/dataset.py, indexes.py", 12, "Extended (Qwen3-8B; 0 coll.)"),
    ("pytest-dev__pytest-7521", "pytest-dev/pytest", "Testing Tools", "41d211c2", "src/_pytest/capture.py", 2, "Extended (Qwen3-8B; build fail)"),
]

def write_tab1():
    lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\caption{Evaluated SWE-bench Verified Instance Cohort Across Five Repositories (13 Core Paired Instances and 4 Extended Qwen3-8B Instances).}",
        r"\label{tab:benchmark_cohort}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3.5pt}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{llllcl}",
        r"\toprule",
        r"\textbf{Instance ID} & \textbf{Domain} & \textbf{Base SHA} & \textbf{Patched Target File(s)} & \textbf{F2P} & \textbf{Cohort Status} \\",
        r"\midrule",
    ]
    for i, (iid, repo, dom, sha, fpath, f2p, status) in enumerate(BENCH_ROWS):
        if i == 13:
            lines.append(r"\midrule")
        lines.append(
            f"\\texttt{{{tex_esc(iid)}}} & {dom} & \\texttt{{{sha}}} & \\texttt{{{tex_esc(fpath)}}} & {f2p} & {status} \\\\"
        )
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}%",
        r"}",
        r"\vspace{3pt}",
        r"\begin{flushleft}\footnotesize \textit{Note:} F2P denotes the number of ground-truth \texttt{FAIL\_TO\_PASS} reference tests in SWE-bench Verified. Under zero-leakage prompting, only \texttt{base\_commit} source context was supplied without developer patches or gold test files. \texttt{pytest-dev\_\_pytest-7521} is included in the Qwen3-8B 17-instance audit and fails collection due to missing uninstalled build metadata (\texttt{\_pytest.\_version}).\end{flushleft}",
        r"\end{table*}",
    ])
    (OUT_DIR / "tab_benchmark_cohort.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ------------------------------------------------------------------------------
# Table 2: Multi-Stage CI Admission Attrition Funnel (RQ1)
# ------------------------------------------------------------------------------
def write_tab2():
    cohorts = [
        ("Qwen3-8B (All-17)", "qwen3_8b_all17"),
        ("Qwen3-8B (Core-13)", "qwen3_8b_core13"),
        ("Qwen2.5-7B (Core-13)", "qwen25_7b_core13"),
        ("DeepSeek-Coder-6.7B (Core-13)", "deepseek_coder_67b_core13"),
        ("CodeLlama-7B (Core-13)", "codellama_7b_core13"),
    ]
    lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\caption{End-to-End CI Admission Funnel Across Foundation Models: From Generated Files to Bug Revelation.}",
        r"\label{tab:attrition_funnel}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{lrrrrrrrr}",
        r"\toprule",
        r"\textbf{Model (Cohort)} & \textbf{Coll./Tot. Files} & \textbf{Attempted} & \textbf{Eff. AST} & \textbf{Collected (\% AST)} & \textbf{Open Pass (95\% CI)} & \textbf{Herm. Pass (95\% CI)} & \textbf{Sock. Viol.} & \textbf{Bugs (Inst.)} \\",
        r"\midrule",
    ]
    core_keys = ["qwen3_8b_core13", "qwen25_7b_core13", "deepseek_coder_67b_core13", "codellama_7b_core13"]
    for idx, (label, key) in enumerate(cohorts):
        r = METRICS["rq1_funnel"][key]
        clean_coll_files = r["clean_parse_files_with_tests"] - r["coll_error_files_with_ast"]
        tot_files = r["files_total"]
        coll_pct_ast = r["collected"] / r["effective_ast_defs"] * 100.0
        o_ci = f"[{r['pass_open_ci_coll'][0]:.1f}, {r['pass_open_ci_coll'][1]:.1f}]"
        h_ci = f"[{r['pass_herm_ci_coll'][0]:.1f}, {r['pass_herm_ci_coll'][1]:.1f}]"
        bugs_str = f"{r['bug_det_open']} ({len(r['bug_insts_open'])})"
        lines.append(
            f"{label} & {clean_coll_files}/{tot_files} & {r['attempted_total_defs']} & {r['effective_ast_defs']} & "
            f"{r['collected']} ({coll_pct_ast:.1f}\\%) & "
            f"{r['pass_open']} ({r['pass_open_pct_coll']:.1f}\\%, {o_ci}) & "
            f"{r['pass_herm']} ({r['pass_herm_pct_coll']:.1f}\\%, {h_ci}) & "
            f"{r['net_viol']} & {bugs_str} \\\\"
        )
        if idx == 0:
            lines.append(r"\midrule")

    # Core-13 Pooled Row
    p_clean = sum(METRICS["rq1_funnel"][k]["clean_parse_files_with_tests"] - METRICS["rq1_funnel"][k]["coll_error_files_with_ast"] for k in core_keys)
    p_files = sum(METRICS["rq1_funnel"][k]["files_total"] for k in core_keys)
    p_att = sum(METRICS["rq1_funnel"][k]["attempted_total_defs"] for k in core_keys)
    p_eff = sum(METRICS["rq1_funnel"][k]["effective_ast_defs"] for k in core_keys)
    p_coll = sum(METRICS["rq1_funnel"][k]["collected"] for k in core_keys)
    p_open = sum(METRICS["rq1_funnel"][k]["pass_open"] for k in core_keys)
    p_herm = sum(METRICS["rq1_funnel"][k]["pass_herm"] for k in core_keys)
    p_nv = sum(METRICS["rq1_funnel"][k]["net_viol"] for k in core_keys)
    p_bugs = sum(METRICS["rq1_funnel"][k]["bug_det_open"] for k in core_keys)

    from math import sqrt
    def wci(k, n):
        z = 1.959963984540054
        p = k / n
        den = 1 + z**2 / n
        c = (p + z**2 / (2 * n)) / den
        h = z * sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / den
        return f"[{max(0, c-h)*100:.1f}, {min(1, c+h)*100:.1f}]"

    lines.append(r"\midrule")
    lines.append(
        f"\\textbf{{Core-13 Pooled (4 Models)}} & \\textbf{{{p_clean}/{p_files}}} & \\textbf{{{p_att}}} & \\textbf{{{p_eff}}} & "
        f"\\textbf{{{p_coll} ({p_coll/p_eff*100:.1f}\\%)}} & "
        f"\\textbf{{{p_open} ({p_open/p_coll*100:.1f}\\%, {wci(p_open, p_coll)})}} & "
        f"\\textbf{{{p_herm} ({p_herm/p_coll*100:.1f}\\%, {wci(p_herm, p_coll)})}} & "
        f"\\textbf{{{p_nv}}} & \\textbf{{{p_bugs} (3)}} \\\\"
    )

    st_coll = METRICS["rq1_stats"]["collected_count"]
    st_open = METRICS["rq1_stats"]["pass_open_count"]
    st_herm = METRICS["rq1_stats"]["pass_herm_count"]
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}%",
        r"}",
        r"\vspace{3pt}",
        f"\\begin{{flushleft}}\\footnotesize \\textit{{Note:}} Attempted includes regex-matched \\texttt{{def test\\_}} definitions inside \\texttt{{SyntaxError}} files (73 in DeepSeek, 25 in CodeLlama) plus shadowed duplicate definitions (58 in DeepSeek, 2 in Qwen3). Collected exceeds effective AST on \\texttt{{xarray-4356}} due to \\texttt{{@pytest.mark.parametrize}} case expansion (+6 in Qwen2.5, +1 in DeepSeek). Paired Friedman tests across the 13 core instances confirm significant model differences in collected counts ($\\chi^2={st_coll['friedman_chi2']:.2f}, p={st_coll['friedman_p']:.4f}$), open passes ($\\chi^2={st_open['friedman_chi2']:.2f}, p={st_open['friedman_p']:.4f}$), and hermetic passes ($\\chi^2={st_herm['friedman_chi2']:.2f}, p={st_herm['friedman_p']:.4f}$). Post-hoc Holm-adjusted Wilcoxon tests show significantly fewer collected tests for CodeLlama-7B than Qwen3-8B ($p_{{\\mathrm{{Holm}}}}=0.0088$) and DeepSeek-Coder-6.7B ($p_{{\\mathrm{{Holm}}}}=0.0293$).\\end{{flushleft}}",
        r"\end{table*}",
    ])
    (OUT_DIR / "tab_attrition_funnel.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ------------------------------------------------------------------------------
# Table 3: Per-Instance Quantitative Breakdown Across Core-13
# ------------------------------------------------------------------------------
def write_tab3():
    CORE_13 = [r[0] for r in BENCH_ROWS[:13]]
    lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\caption{Per-Instance Test Attrition and Defect Revelation on Core-13 Across All Four Models (Format: Eff.\ AST / Coll.\ / Open Pass / Herm.\ Pass / Viol.).}",
        r"\label{tab:per_instance_yield}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"\textbf{Instance ID} & \textbf{Qwen3-8B} & \textbf{Qwen2.5-7B} & \textbf{DeepSeek-Coder-6.7B} & \textbf{CodeLlama-7B} \\",
        r"\midrule",
    ]
    for iid in CORE_13:
        cells = []
        for m in MODEL_ORDER:
            r = METRICS["rq1_funnel"][f"{m}_core13"]["per_instance"][iid]
            b = f" (\\textbf{{{r['bug_det_open']}*}})" if r["bug_det_open"] > 0 else ""
            cells.append(f"{r['effective_ast']} / {r['collected']} / {r['pass_open']} / {r['pass_herm']} / {r['net_viol']}{b}")
        lines.append(f"\\texttt{{{tex_esc(iid)}}} & " + " & ".join(cells) + r" \\")
    lines.append(r"\midrule")
    tot_cells = []
    for m in MODEL_ORDER:
        d = METRICS["rq1_funnel"][f"{m}_core13"]
        b = f" (\\textbf{{{d['bug_det_open']}*}})" if d["bug_det_open"] > 0 else ""
        tot_cells.append(f"{d['effective_ast_defs']} / {d['collected']} / {d['pass_open']} / {d['pass_herm']} / {d['net_viol']}{b}")
    lines.append(r"\textbf{Core-13 Total} & " + " & ".join(f"\\textbf{{{c}}}" for c in tot_cells) + r" \\")
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}%",
        r"}",
        r"\vspace{3pt}",
        r"\begin{flushleft}\footnotesize \textit{Note:} Entries marked with \textbf{*} indicate real SWE-bench bug-detecting tests passing on the fixed commit and failing on the buggy commit (exclusively in Qwen3-8B: 4 on \texttt{requests-1921}, 4 on \texttt{flask-5014}, and 6 on \texttt{sympy-15809}; 0 across all other models).\end{flushleft}",
        r"\end{table*}",
    ])
    (OUT_DIR / "tab_per_instance_yield.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ------------------------------------------------------------------------------
# Table 4: RQ2 Failure Root-Cause Taxonomy
# ------------------------------------------------------------------------------
def write_tab4():
    cols = [
        ("Qwen3 (All-17)", "qwen3_8b_all17", "qwen3_8b", "ALL_17"),
        ("Qwen3 (Core-13)", "qwen3_8b_core13", "qwen3_8b", "CORE_13"),
        ("Qwen2.5 (Core-13)", "qwen25_7b_core13", "qwen25_7b", "CORE_13"),
        ("DeepSeek (Core-13)", "deepseek_coder_67b_core13", "deepseek_coder_67b", "CORE_13"),
        ("CodeLlama (Core-13)", "codellama_7b_core13", "codellama_7b", "CORE_13"),
    ]
    def g(ck, mkey, skey):
        return METRICS["rq1_funnel"][ck], METRICS["rq2_taxonomy"][ck], METRICS["static_oracles"][mkey][skey]

    lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\caption{Root-Cause Failure Taxonomy Across Pre-Execution Collection, Fixed-Commit Open Runtime, and Static Oracle Quality.}",
        r"\label{tab:failure_taxonomy}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"\textbf{Failure / Pathology Category} & \textbf{Qwen3 (All-17)} & \textbf{Qwen3 (Core-13)} & \textbf{Qwen2.5 (Core-13)} & \textbf{DeepSeek (Core-13)} & \textbf{CodeLlama (Core-13)} \\",
        r"\midrule",
        r"\multicolumn{6}{l}{\textit{Panel A: Pre-Collection Attrition (Files; Parentheses Denote Candidate/AST Functions Lost)}} \\",
    ]

    def row(name, fn):
        vals = [fn(*g(ck, mk, sk)) for _, ck, mk, sk in cols]
        return f"{name} & " + " & ".join(str(v) for v in vals) + r" \\"

    lines.append(row("SyntaxError files (regex \\texttt{def test\\_})", lambda f, t, s: f"{f['syn_err_files']} ({f['syn_err_regex_defs']})"))
    lines.append(row("Zero-test: Source code paraphrase", lambda f, t, s: f"{f['zero_fn_subcats'].get('Source Code Paraphrase/Helper', 0)}"))
    lines.append(row("Zero-test: Top-level script (no \\texttt{def test\\_})", lambda f, t, s: f"{f['zero_fn_subcats'].get('Top-Level Script (no def test_)', 0)}"))
    lines.append(row("Zero-test: Markdown dump / empty", lambda f, t, s: f"{f['zero_fn_subcats'].get('Markdown/Prose Dump', 0) + f['zero_fn_subcats'].get('Empty/Definitions Only', 0)}"))
    lines.append(row("Namespace shadowing (overwritten defs)", lambda f, t, s: f"{f['shadowed_defs']} defs"))
    lines.append(row("Collection: Hallucinated module/symbol", lambda f, t, s: f"{t['collection_error_files_by_cat'].get('Hallucinated / Nonexistent Symbol or Module', 0)} ({t['collection_error_ast_lost_by_cat'].get('Hallucinated / Nonexistent Symbol or Module', 0)})"))
    lines.append(row("Collection: Placeholder module (e.g., \\texttt{your\\_module})", lambda f, t, s: f"{t['collection_error_files_by_cat'].get('Placeholder Module Reference', 0)} ({t['collection_error_ast_lost_by_cat'].get('Placeholder Module Reference', 0)})"))
    lines.append(row("Collection: Relative import leak", lambda f, t, s: f"{t['collection_error_files_by_cat'].get('Relative Import Outside Package', 0)} ({t['collection_error_ast_lost_by_cat'].get('Relative Import Outside Package', 0)})"))
    lines.append(row("Collection: Top-level crash / NumPy 2.0", lambda f, t, s: f"{t['collection_error_files_by_cat'].get('Top-Level Execution Error', 0) + t['collection_error_files_by_cat'].get('NumPy API Compatibility Error', 0)} ({t['collection_error_ast_lost_by_cat'].get('Top-Level Execution Error', 0) + t['collection_error_ast_lost_by_cat'].get('NumPy API Compatibility Error', 0)})"))
    lines.append(row("Collection: Build metadata (\\texttt{\\_pytest.\\_version})", lambda f, t, s: f"{t['collection_error_files_by_cat'].get('Build-Metadata / Infra Failure', 0)} ({t['collection_error_ast_lost_by_cat'].get('Build-Metadata / Infra Failure', 0)})"))

    lines.extend([
        r"\midrule",
        r"\multicolumn{6}{l}{\textit{Panel B: Fixed-Commit Open-Network Runtime Failures (Counts Over Collected Failing Tests)}} \\",
    ])
    lines.append(row("Wrong oracle (\\texttt{AssertionError})", lambda f, t, s: t["fixed_open_failure_cats"].get("Wrong Oracle (AssertionError)", 0)))
    lines.append(row("Undefined symbol (\\texttt{NameError})", lambda f, t, s: t["fixed_open_failure_cats"].get("Undefined Symbol (NameError)", 0)))
    lines.append(row("API/State error (\\texttt{Type/Value/Attr/KeyError})", lambda f, t, s: sum(v for k, v in t["fixed_open_failure_cats"].items() if k.startswith("API/State Runtime Error"))))
    lines.append(row("Unmet \\texttt{pytest.raises} expectation", lambda f, t, s: t["fixed_open_failure_cats"].get("Unmet Exception Expectation (pytest.raises)", 0)))
    lines.append(row("Lazy runtime \\texttt{ImportError}", lambda f, t, s: t["fixed_open_failure_cats"].get("Lazy Runtime ImportError", 0)))
    lines.append(row("Network/TLS/Proxy error (open net)", lambda f, t, s: sum(v for k, v in t["fixed_open_failure_cats"].items() if k.startswith("Network/TLS/Proxy"))))
    lines.append(row("Unicode/File/MissingDim/Other runtime error", lambda f, t, s: sum(v for k, v in t["fixed_open_failure_cats"].items() if k.startswith("Other Runtime Error"))))
    lines.append(row("\\textbf{Total Open-Network Runtime Failures}", lambda f, t, s: f"\\textbf{{{sum(t['fixed_open_failure_cats'].values())}}}"))

    lines.extend([
        r"\midrule",
        r"\multicolumn{6}{l}{\textit{Panel C: Static Oracle Quality \& Mock Usage (Across AST-Parsed Files/Functions)}} \\",
    ])
    lines.append(row("Zero-oracle AST functions (no assert/raises)", lambda f, t, s: s["zero_oracle_ast"]))
    lines.append(row("Tautological assertions (\\texttt{assert True})", lambda f, t, s: s["tautological_ast"]))
    lines.append(row("Files importing or invoking mock utilities", lambda f, t, s: f"{s['files_using_mock']}/{f['files_total']}"))

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}%",
        r"}",
        r"\vspace{3pt}",
        r"\begin{flushleft}\footnotesize \textit{Note:} Panel~B covers all collected tests failing on the ground-truth fixed commit under open network access (after per-test resolution of DeepSeek-Coder-6.7B's two timeout-truncated suites). Note that under \texttt{HERMETIC\_CI=1}, 42 additional tests that passed open network instead fail with socket-violation \texttt{OSError}s (see Table~\ref{tab:network_divergence_ast}).\end{flushleft}",
        r"\end{table*}",
    ])
    (OUT_DIR / "tab_failure_taxonomy.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ------------------------------------------------------------------------------
# Table 5: RQ3 Open vs Hermetic Divergence & Static AST Accuracy
# ------------------------------------------------------------------------------
def write_tab5():
    lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\caption{Open-vs-Hermetic CI Environment Divergence and Static URL-Literal AST Detection Accuracy (Core-13).}",
        r"\label{tab:network_divergence_ast}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{lrrrrrcccc}",
        r"\toprule",
        r"\textbf{Model} & \textbf{Coll.} & \textbf{Pass Both} & \textbf{Illusory*} & \textbf{Fail+Viol} & \textbf{Non-Net Fail} & \textbf{Func TP/FP/FN} & \textbf{Func P/R (\%)} & \textbf{Scope TP/FP/FN} & \textbf{Scope P/R (\%)} \\",
        r"\midrule",
    ]
    tot_c = tot_pb = tot_il = tot_fv = tot_nn = 0
    ftp = ffp = ffn = stp = sfp = sfn = 0
    for m in MODEL_ORDER:
        r = METRICS["rq1_funnel"][f"{m}_core13"]
        n = METRICS["rq3_network"][f"{m}_core13"]
        so = METRICS["static_oracles"][m]["CORE_13"]
        f = so["func_url_cm"]
        s = so["scope_url_cm"]
        ftp += f["tp"]; ffp += f["fp"]; ffn += f["fn"]
        stp += s["tp"]; sfp += s["fp"]; sfn += s["fn"]
        pb = n.get("PASS_OPEN -> PASS_HERM", 0)
        il = n.get("PASS_OPEN -> NET_VIOL_HERM", 0)
        fv = n.get("FAIL_OPEN -> NET_VIOL_HERM", 0)
        nn = n.get("FAIL_OPEN -> NON_NET_FAIL_HERM", 0)
        tot_c += r["collected"]; tot_pb += pb; tot_il += il; tot_fv += fv; tot_nn += nn
        fp_r = f["tp"] / max(f["tp"] + f["fp"], 1) * 100.0
        fr_r = f["tp"] / max(f["tp"] + f["fn"], 1) * 100.0
        sp_r = s["tp"] / max(s["tp"] + s["fp"], 1) * 100.0
        sr_r = s["tp"] / max(s["tp"] + s["fn"], 1) * 100.0
        lines.append(
            f"{MODEL_NAMES[m]} & {r['collected']} & {pb} & {il} & {fv} & {nn} & "
            f"{f['tp']}/{f['fp']}/{f['fn']} & {fp_r:.1f} / {fr_r:.1f} & "
            f"{s['tp']}/{s['fp']}/{s['fn']} & {sp_r:.1f} / {sr_r:.1f} \\\\"
        )
    lines.append(r"\midrule")
    tfp_r = ftp / max(ftp + ffp, 1) * 100.0
    tfr_r = ftp / max(ftp + ffn, 1) * 100.0
    tsp_r = stp / max(stp + sfp, 1) * 100.0
    tsr_r = stp / max(stp + sfn, 1) * 100.0
    lines.append(
        f"\\textbf{{Core-13 Pooled}} & \\textbf{{{tot_c}}} & \\textbf{{{tot_pb}}} & \\textbf{{{tot_il}}} & \\textbf{{{tot_fv}}} & \\textbf{{{tot_nn}}} & "
        f"\\textbf{{{ftp}/{ffp}/{ffn}}} & \\textbf{{{tfp_r:.1f} / {tfr_r:.1f}}} & \\textbf{{{stp}/{sfp}/{sfn}}} & \\textbf{{{tsp_r:.1f} / {tsr_r:.1f}}} \\\\"
    )
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}%",
        r"}",
        r"\vspace{3pt}",
        r"\begin{flushleft}\footnotesize \textit{Note:} *Illusory denotes tests that passed on the open-network workstation yet crashed with an unmocked socket violation under \texttt{HERMETIC\_CI=1} ($42/292 = 14.4\%$ of all open-network passes; $29/90 = 32.2\%$ for DeepSeek-Coder-6.7B). Static URL detection evaluates whether external \texttt{http(s)://} AST string literals predict runtime socket violations across all 775 collected tests at function-local scope (Func) or expanded class/module \texttt{setUp} scope (Scope).\end{flushleft}",
        r"\end{table*}",
    ])
    (OUT_DIR / "tab_network_divergence_ast.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ------------------------------------------------------------------------------
# Table 6: RQ4 Runtime Repeatability & Mock Remediation
# ------------------------------------------------------------------------------
def write_tab6():
    lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\caption{Runtime Order-Dependent Flakiness Profiling ($N=20$ Hermetic / $N=10$ Open) and Automated HTTP Transport Mock Remediation ($N=76$ Socket Violators).}",
        r"\label{tab:flakiness_and_mock}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{lrrrrrrrr}",
        r"\toprule",
        r"\textbf{Model} & \textbf{Herm. $N{=}20$} & \textbf{Herm. Flaky} & \textbf{Open $N{=}10$} & \textbf{Open Flaky} & \textbf{Sock. Viol.} & \textbf{Rescued (95\% CI)} & \textbf{Collat. (+/-)} & \textbf{New Bugs} \\",
        r"\midrule",
    ]
    h_tot = h_exec = o_tot = o_exec = sv_tot = mr_tot = 0
    for m in MODEL_ORDER:
        hr = METRICS["rq4_flakiness_and_mock"]["hermetic_n20"][m]
        op = METRICS["rq4_flakiness_and_mock"]["open_n10"][m]
        mr = METRICS["rq4_flakiness_and_mock"]["mock_remediation"][m]["http_echo"]
        h_tot += hr["collected_tests"]; h_exec += hr["total_test_executions"]
        o_tot += op["tested_count"]; o_exec += op["tested_count"] * 10
        sv_tot += mr["total_viol"]; mr_tot += mr["rescued"]
        ci = f"[{mr['rescue_ci'][0]:.1f}, {mr['rescue_ci'][1]:.1f}]"
        collat = f"+{len(mr['non_viol_gained'])} / -{len(mr['non_viol_broken'])}"
        lines.append(
            f"{MODEL_NAMES[m]} & {hr['collected_tests']} ({hr['total_test_executions']:,}) & {hr['flaky_tests']} & "
            f"{op['tested_count']} ({op['tested_count']*10:,}) & {op['flaky_tests']} & "
            f"{mr['total_viol']} & {mr['rescued']} ({mr['rescue_rate_pct']:.1f}\\%, {ci}) & "
            f"{collat} & {mr['bug_det']} \\\\"
        )
    from math import sqrt
    z = 1.959963984540054
    p = mr_tot / max(sv_tot, 1)
    den = 1 + z**2 / max(sv_tot, 1)
    c = (p + z**2 / (2 * max(sv_tot, 1))) / den
    h = z * sqrt((p * (1 - p) + z**2 / (4 * max(sv_tot, 1))) / max(sv_tot, 1)) / den
    pooled_ci = f"[{max(0, c-h)*100:.1f}, {min(1, c+h)*100:.1f}]"
    lines.append(r"\midrule")
    lines.append(
        f"\\textbf{{All Models Pooled}} & \\textbf{{{h_tot} ({h_exec:,})}} & \\textbf{{0}} & "
        f"\\textbf{{{o_tot} ({o_exec:,})}} & \\textbf{{0*}} & "
        f"\\textbf{{{sv_tot}}} & \\textbf{{{mr_tot} ({p*100:.1f}\\%, {pooled_ci})}} & "
        f"\\textbf{{+4 / -2}} & \\textbf{{0}} \\\\"
    )
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}%",
        r"}",
        r"\vspace{3pt}",
        r"\begin{flushleft}\footnotesize \textit{Note:} Hermetic $N=20$ runs cover all 39 active model-instance pairs; Open $N=10$ runs cover all 7 \texttt{psf/requests} model-instance suites triggering socket violations. *Although short-window $N=10$ open runs on 2026-11-18 were deterministic, comparing 2026-09-26 vs.\ 2026-11-18 runs exposed longitudinal drift on \texttt{requests-2317::test\_request\_with\_utf8\_encoding} against live \texttt{example.com}. Mock rescue rates were identical across both \texttt{Minimal-200} and \texttt{HTTP-Echo} transport fixtures; remaining 22 unrescued violators fail due to unmet error/exception expectations (11), third-party REST service/redirect/cookie contracts (8), and broken mock/header logic (3).\end{flushleft}",
        r"\end{table*}",
    ])
    (OUT_DIR / "tab_flakiness_and_mock.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

if __name__ == "__main__":
    write_tab1()
    write_tab2()
    write_tab3()
    write_tab4()
    write_tab5()
    write_tab6()
    print("[+] Generated all 6 verified LaTeX tables in", OUT_DIR)
