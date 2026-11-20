import json
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results" / "empirical_study_20261118"
METRICS = json.loads((RESULTS_DIR / "empirical_master_metrics.json").read_text(encoding="utf-8"))
OUT_DIR = Path(os.environ.get("EMPIRICAL_FIGURES_OUT", str(RESULTS_DIR / "figures")))
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial"],
    "font.size": 8.5,
    "axes.titlesize": 9.8,
    "axes.titleweight": "bold",
    "axes.labelsize": 8.5,
    "xtick.labelsize": 8.0,
    "ytick.labelsize": 8.0,
    "legend.fontsize": 7.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})

MODEL_ORDER = ["qwen3_8b", "qwen25_7b", "deepseek_coder_67b", "codellama_7b"]
MODEL_LABELS = {
    "qwen3_8b": "Qwen3-8B",
    "qwen25_7b": "Qwen2.5-7B",
    "deepseek_coder_67b": "DeepSeek-Coder-6.7B",
    "codellama_7b": "CodeLlama-7B",
}
MODEL_SHORT = {
    "qwen3_8b": "Qwen3-8B",
    "qwen25_7b": "Qwen2.5-7B",
    "deepseek_coder_67b": "DeepSeek-6.7B",
    "codellama_7b": "CodeLlama-7B",
}
MODEL_COLORS = {
    "qwen3_8b": "#0072B2",
    "qwen25_7b": "#009E73",
    "deepseek_coder_67b": "#E69F00",
    "codellama_7b": "#CC79A7",
}

def save_fig(fig, stem):
    for ext in ("pdf", "png"):
        p = OUT_DIR / f"{stem}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[+] Saved {stem}.pdf / .png")

# ==============================================================================
# FIGURE 1: Multi-Stage Empirical Study Pipeline & Gate Overview
# ==============================================================================
def make_fig1():
    fig, ax = plt.subplots(figsize=(11.2, 4.8))
    ax.set_xlim(0, 114)
    ax.set_ylim(0, 56)
    ax.axis("off")

    def box(x, y, w, h, title, body, fc="#F8FAFC", ec="#334155", title_fc="#0F172A", lw=1.3):
        rect = patches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.5,rounding_size=1.0",
            facecolor=fc, edgecolor=ec, linewidth=lw
        )
        ax.add_patch(rect)
        # Header divider band
        hdr_h = 4.2
        hdr = patches.FancyBboxPatch(
            (x, y + h - hdr_h), w, hdr_h, boxstyle="round,pad=0.5,rounding_size=1.0",
            facecolor=ec, edgecolor=ec, linewidth=0.5
        )
        ax.add_patch(hdr)
        ax.text(x + w/2, y + h - hdr_h/2 + 0.1, title, ha="center", va="center",
                fontsize=8.2, fontweight="bold", color="white")
        ax.text(x + w/2, y + (h - hdr_h)/2, body, ha="center", va="center",
                fontsize=7.3, color="#0F172A", linespacing=1.35)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>,head_width=0.35,head_length=0.55", color="#475569", lw=1.4))

    ax.text(57, 54.4, "Zero-Leakage Multi-Stage CI Admission Audit on SWE-bench Verified (Core-13 Across 4 LLMs; +4 Extended on Qwen3-8B)",
            ha="center", va="top", fontsize=9.8, fontweight="bold", color="#0F172A")

    # Input Stage
    box(1.0, 20.5, 16.5, 29.0, "Zero-Leakage Input",
        "base_commit context\n(no gold patch/tests)\n\nExplicit prompt rule:\n'Do NOT use external\nservices or network'\n\n4 Open-Weight LLMs\nCore-13 (39 files/model)\n+4 Qwen3 (50 files)",
        fc="#EFF6FF", ec="#0072B2")

    # 5 Sequential Gates
    gates = [
        (20.5, 16.0, "Gate 1: Parse", "AST Syntax &\nFile Structure\n\nLoss modes:\n- SyntaxError (9 files)\n- Zero-test files (24)\n- Shadowing (60 defs)\n\nCore-13:\n1,140 -> 982", "#ECFDF5", "#009E73"),
        (39.5, 16.0, "Gate 2: Collect", "pytest --collect-only\nin Git Worktree\n\nLoss modes:\n- Hallucinated imports\n- Placeholder modules\n- Top-level crashes\n\nCore-13:\n982 -> 775", "#FFFBEB", "#D97706"),
        (58.5, 16.0, "Gate 3: Open Fix", "Patched Commit\nOpen Network\n\nLoss modes:\n- Wrong oracle / assert\n- NameError / API err\n- SSL / Proxy timeout\n\nCore-13:\n775 -> 292", "#FEF3C7", "#C27803"),
        (77.5, 16.0, "Gate 4: Hermetic", "HERMETIC_CI=1 +\nN=20 Shuffle Runs\n\nFindings:\n- 76 socket violators\n- 42 illusory passes\n- 0/775 flaky (N=20)\n\nCore-13:\n292 -> 250", "#FEF2F2", "#D55E00"),
        (96.5, 16.5, "Gate 5: Bug & Mock", "Buggy Commit &\nHTTP Mock Patch\n\nFindings:\n- 14/250 bugs (Qwen3)\n- 0 bugs in 3 models\n- 54/76 mock pass\n  (0 new bug det)", "#F5F3FF", "#6D28D9"),
    ]
    arrow(18.1, 35.0, 20.0, 35.0)
    for idx, (gx, gw, gt, gb, gfc, gec) in enumerate(gates):
        box(gx, 20.5, gw, 29.0, gt, gb, fc=gfc, ec=gec)
        if idx < len(gates) - 1:
            nxt_x = gates[idx + 1][0]
            arrow(gx + gw + 0.6, 35.0, nxt_x - 0.5, 35.0)

    # Non-overlapping clean RQ span bars at bottom
    rqs = [
        (20.5, 92.5, 14.0, "RQ1: End-to-End CI Admission Attrition & Real Defect Yield Across Four Models (Section 4.1)", "#E2E8F0", "#334155"),
        (20.5, 53.0, 8.2, "RQ2: Syntax, Collection & Oracle Failure Taxonomy (Sec. 4.2)", "#ECFDF5", "#047857"),
        (56.5, 38.0, 2.4, "RQ3: Network Divergence & AST Limits (Sec. 4.3)", "#FFF7ED", "#C2410C"),
        (76.0, 37.0, 8.2, "RQ4: Shuffle Flakiness & Mock Repair (Sec. 4.4)", "#F3E8FF", "#6D28D9"),
    ]
    for rx, rw, ry, rtxt, rfc, rec in rqs:
        rp = patches.FancyBboxPatch((rx, ry), rw, 4.0, boxstyle="round,pad=0.25,rounding_size=0.7",
                                    facecolor=rfc, edgecolor=rec, linewidth=1.0)
        ax.add_patch(rp)
        ax.text(rx + rw/2, ry + 2.0, rtxt, ha="center", va="center", fontsize=7.0, fontweight="bold", color="#0F172A")

    save_fig(fig, "fig_1_study_pipeline")

# ==============================================================================
# FIGURE 2: Multi-Stage Attrition Funnel + 13-Instance Heatmap
# ==============================================================================
def make_fig2():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.6, 6.2), gridspec_kw={"height_ratios": [1.05, 1.0], "hspace": 0.44})

    stages = [
        ("Attempted\nDefs", "attempted_total_defs"),
        ("Effective\nAST Defs", "effective_ast_defs"),
        ("Pytest\nCollected", "collected"),
        ("Open-Net\nPass", "pass_open"),
        ("Hermetic CI\nPass", "pass_herm"),
        ("Bug-\nDetecting", "bug_det_open"),
    ]
    x = np.arange(len(stages))
    width = 0.195
    offsets = [-1.5 * width, -0.5 * width, 0.5 * width, 1.5 * width]

    for i, mkey in enumerate(MODEL_ORDER):
        d = METRICS["rq1_funnel"][f"{mkey}_core13"]
        vals = [d[k] for _, k in stages]
        bars = ax1.bar(x + offsets[i], vals, width, label=MODEL_LABELS[mkey], color=MODEL_COLORS[mkey], edgecolor="white", linewidth=0.6)
        eff = d["effective_ast_defs"]
        for s_idx, (bar, v) in enumerate(zip(bars, vals)):
            if s_idx in (3, 4):
                lbl = f"{v}\n{v/eff*100:.0f}%"
            else:
                lbl = str(v)
            ax1.text(bar.get_x() + bar.get_width()/2, v + 5, lbl, ha="center", va="bottom",
                     fontsize=6.5, color="#1E293B", linespacing=1.05)

    ax1.set_xticks(x)
    ax1.set_xticklabels([s[0] for s in stages], fontsize=8.3)
    ax1.set_ylabel("Test Function / Nodeid Count (Core-13)")
    ax1.set_ylim(0, 445)
    ax1.grid(axis="y", linestyle="--", alpha=0.25)
    ax1.legend(frameon=False, ncol=4, loc="upper right", fontsize=8.0)
    ax1.set_title("(a) End-to-End CI Admission Funnel Across Four Models on the Paired Core-13 Cohort", loc="left", pad=8)

    CORE_13 = [
        "psf__requests-1724", "psf__requests-1766", "psf__requests-1921",
        "psf__requests-2317", "psf__requests-6028", "pallets__flask-5014",
        "sympy__sympy-15809", "sympy__sympy-17630", "sympy__sympy-21930",
        "pydata__xarray-4075", "pydata__xarray-4356", "pydata__xarray-4966",
        "pydata__xarray-6744",
    ]
    SHORT_INST = [
        "req-1724", "req-1766", "req-1921", "req-2317", "req-6028",
        "flask-5014", "sym-15809", "sym-17630", "sym-21930",
        "xr-4075", "xr-4356", "xr-4966", "xr-6744"
    ]
    mat = np.zeros((4, len(CORE_13)))
    cell_txt = []
    for r_idx, mkey in enumerate(MODEL_ORDER):
        row_t = []
        p_inst = METRICS["rq1_funnel"][f"{mkey}_core13"]["per_instance"]
        for c_idx, iid in enumerate(CORE_13):
            r = p_inst[iid]
            eff, coll, ph, bdo = r["effective_ast"], r["collected"], r["pass_herm"], r["bug_det_open"]
            pct = (ph / eff * 100.0) if eff > 0 else 0.0
            mat[r_idx, c_idx] = pct
            if eff == 0:
                txt = "0/0\n(no AST)"
            elif coll == 0:
                txt = f"0/{eff}\n(coll=0)"
            elif bdo > 0:
                txt = f"{ph}/{eff}*\n({pct:.0f}%)"
            else:
                txt = f"{ph}/{eff}\n({pct:.0f}%)"
            row_t.append(txt)
        cell_txt.append(row_t)

    im = ax2.imshow(mat, cmap="YlGnBu", vmin=0, vmax=80, aspect="auto")
    ax2.set_xticks(np.arange(len(CORE_13)))
    ax2.set_xticklabels(SHORT_INST, rotation=26, ha="right", fontsize=8.0)
    ax2.set_yticks(np.arange(4))
    ax2.set_yticklabels([MODEL_SHORT[m] for m in MODEL_ORDER], fontsize=8.3)

    for r_idx in range(4):
        for c_idx in range(len(CORE_13)):
            val = mat[r_idx, c_idx]
            col = "white" if val >= 42 else "#0F172A"
            ax2.text(c_idx, r_idx, cell_txt[r_idx][c_idx], ha="center", va="center", fontsize=6.7, color=col, linespacing=1.08)

    ax2.set_xticks(np.arange(-0.5, len(CORE_13), 1), minor=True)
    ax2.set_yticks(np.arange(-0.5, 4, 1), minor=True)
    ax2.grid(which="minor", color="white", linestyle="-", linewidth=1.2)
    ax2.tick_params(which="minor", bottom=False, left=False)
    for sp in ("top", "right", "left", "bottom"):
        ax2.spines[sp].set_visible(False)

    for vx in (4.5, 5.5, 8.5):
        ax2.axvline(vx, color="#0F172A", linewidth=1.3, linestyle="--")

    cbar = fig.colorbar(im, ax=ax2, fraction=0.018, pad=0.02)
    cbar.set_label("Hermetic Pass / AST (%)", fontsize=7.8)
    ax2.set_title("(b) Per-Instance Hermetic CI Pass / Effective AST (* marks bug-detecting instances: 4, 4, 6 tests)", loc="left", pad=8)

    save_fig(fig, "fig_2_attrition_funnel")

# ==============================================================================
# FIGURE 3: Pre-Collection and Fixed-Commit Runtime Failure Taxonomy
# ==============================================================================
def make_fig3():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.8, 4.4), gridspec_kw={"wspace": 0.28})

    y = np.arange(len(MODEL_ORDER))
    pre_cats = [
        ("Syntax Error File", "#D55E00"),
        ("Zero-Test: Source Echo", "#CC79A7"),
        ("Zero-Test: Script/Prose/Empty", "#E69F00"),
        ("Coll Err: Hallucinated Import", "#0072B2"),
        ("Coll Err: Placeholder Module", "#56B4E9"),
        ("Coll Err: Rel. Imp/NumPy/Top", "#009E73"),
    ]
    pre_data = {c[0]: [] for c in pre_cats}
    for mkey in MODEL_ORDER:
        d = METRICS["rq1_funnel"][f"{mkey}_core13"]
        tx = METRICS["rq2_taxonomy"][f"{mkey}_core13"]
        ce = tx["collection_error_files_by_cat"]
        zsub = d["zero_fn_subcats"]
        pre_data["Syntax Error File"].append(d["syn_err_files"])
        pre_data["Zero-Test: Source Echo"].append(zsub.get("Source Code Paraphrase/Helper", 0))
        pre_data["Zero-Test: Script/Prose/Empty"].append(
            zsub.get("Top-Level Script (no def test_)", 0) + zsub.get("Markdown/Prose Dump", 0) + zsub.get("Empty/Definitions Only", 0)
        )
        pre_data["Coll Err: Hallucinated Import"].append(ce.get("Hallucinated / Nonexistent Symbol or Module", 0))
        pre_data["Coll Err: Placeholder Module"].append(ce.get("Placeholder Module Reference", 0))
        pre_data["Coll Err: Rel. Imp/NumPy/Top"].append(
            ce.get("Relative Import Outside Package", 0) + ce.get("NumPy API Compatibility Error", 0) + ce.get("Top-Level Execution Error", 0)
        )

    left = np.zeros(len(MODEL_ORDER))
    for cat_name, col in pre_cats:
        vals = np.array(pre_data[cat_name])
        ax1.barh(y, vals, left=left, height=0.52, label=cat_name, color=col, edgecolor="white", linewidth=0.6)
        for idx, v in enumerate(vals):
            if v >= 2:
                ax1.text(left[idx] + v/2, y[idx], str(v), ha="center", va="center", fontsize=7.2, color="white", fontweight="bold")
        left += vals

    for idx in range(len(MODEL_ORDER)):
        tot_bad = int(left[idx])
        ax1.text(tot_bad + 0.5, y[idx], f"{tot_bad}/39", va="center", ha="left", fontsize=7.6, color="#0F172A")

    ax1.set_yticks(y)
    ax1.set_yticklabels([MODEL_SHORT[m] for m in MODEL_ORDER], fontsize=8.3)
    ax1.invert_yaxis()
    ax1.set_xlim(0, 26)
    ax1.set_xlabel("Non-Clean Candidate Files (out of 39 in Core-13)")
    ax1.grid(axis="x", linestyle="--", alpha=0.25)
    ax1.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.20), ncol=2, fontsize=6.9)
    ax1.set_title("(a) Pre-Execution File Failures (Core-13)", loc="left", pad=8)

    rt_cats = [
        ("Wrong Oracle (AssertionError)", "#0072B2"),
        ("Undefined Symbol (NameError)", "#D55E00"),
        ("API/State Err (Type/Val/Attr/Key)", "#E69F00"),
        ("Unmet pytest.raises", "#009E73"),
        ("Lazy Runtime ImportError", "#CC79A7"),
        ("Network/TLS/Proxy/Wire/Other", "#64748B"),
    ]
    rt_counts = {c[0]: [] for c in rt_cats}
    rt_totals = []
    for mkey in MODEL_ORDER:
        fc = METRICS["rq2_taxonomy"][f"{mkey}_core13"]["fixed_open_failure_cats"]
        tot = sum(fc.values())
        rt_totals.append(tot)
        c_assert = fc.get("Wrong Oracle (AssertionError)", 0)
        c_name = fc.get("Undefined Symbol (NameError)", 0)
        c_api = sum(v for k, v in fc.items() if k.startswith("API/State Runtime Error"))
        c_raises = fc.get("Unmet Exception Expectation (pytest.raises)", 0)
        c_imp = fc.get("Lazy Runtime ImportError", 0)
        c_other = tot - (c_assert + c_name + c_api + c_raises + c_imp)
        rt_counts["Wrong Oracle (AssertionError)"].append(c_assert)
        rt_counts["Undefined Symbol (NameError)"].append(c_name)
        rt_counts["API/State Err (Type/Val/Attr/Key)"].append(c_api)
        rt_counts["Unmet pytest.raises"].append(c_raises)
        rt_counts["Lazy Runtime ImportError"].append(c_imp)
        rt_counts["Network/TLS/Proxy/Wire/Other"].append(c_other)

    left_pct = np.zeros(len(MODEL_ORDER))
    for cat_name, col in rt_cats:
        raw_vals = np.array(rt_counts[cat_name], dtype=float)
        pct_vals = raw_vals / np.array(rt_totals, dtype=float) * 100.0
        ax2.barh(y, pct_vals, left=left_pct, height=0.52, label=cat_name, color=col, edgecolor="white", linewidth=0.6)
        for idx, (pv, rv) in enumerate(zip(pct_vals, raw_vals)):
            if pv >= 9.0:
                ax2.text(left_pct[idx] + pv/2, y[idx], f"{int(rv)}\n({pv:.0f}%)", ha="center", va="center",
                         fontsize=6.6, color="white", fontweight="bold", linespacing=1.0)
        left_pct += pct_vals

    for idx, tot in enumerate(rt_totals):
        ax2.text(101.5, y[idx], f"n={tot}", va="center", ha="left", fontsize=7.6, color="#0F172A")

    ax2.set_yticks(y)
    ax2.set_yticklabels(["" for _ in MODEL_ORDER])
    ax2.invert_yaxis()
    ax2.set_xlim(0, 115)
    ax2.set_xlabel("Share of Fixed-Commit Failing Tests (%)")
    ax2.grid(axis="x", linestyle="--", alpha=0.25)
    ax2.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.48, -0.20), ncol=2, fontsize=6.9)
    ax2.set_title("(b) Fixed-Commit Open Runtime Failures", loc="left", pad=8)

    save_fig(fig, "fig_3_failure_taxonomy")

# ==============================================================================
# FIGURE 4: Network Divergence, Static AST Limits & Mock Remediation
# ==============================================================================
def make_fig4():
    fig = plt.figure(figsize=(9.2, 6.6))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.0], hspace=0.65, wspace=0.35)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, :])

    y = np.arange(len(MODEL_ORDER))

    # Panel (a): Open vs Hermetic transitions
    trans_cats = [
        ("PASS_OPEN -> PASS_HERM", "Pass Both (Offline OK)", "#009E73"),
        ("PASS_OPEN -> NET_VIOL_HERM", "Pass Open -> Socket Viol (Illusory)", "#E69F00"),
        ("FAIL_OPEN -> NET_VIOL_HERM", "Fail Open -> Socket Viol", "#D55E00"),
        ("FAIL_OPEN -> NON_NET_FAIL_HERM", "Fail Both (Non-Network)", "#94A3B8"),
    ]
    tots = [METRICS["rq1_funnel"][f"{m}_core13"]["collected"] for m in MODEL_ORDER]
    left_p = np.zeros(len(MODEL_ORDER))
    for k, lbl, col in trans_cats:
        raw = np.array([METRICS["rq3_network"][f"{m}_core13"].get(k, 0) for m in MODEL_ORDER], dtype=float)
        pct = raw / np.array(tots, dtype=float) * 100.0
        ax_a.barh(y, pct, left=left_p, height=0.52, label=lbl, color=col, edgecolor="white", linewidth=0.6)
        for idx, (pv, rv) in enumerate(zip(pct, raw)):
            if pv >= 8.0:
                tcol = "#0F172A" if col == "#94A3B8" else "white"
                ax_a.text(left_p[idx] + pv/2, y[idx], f"{int(rv)}", ha="center", va="center", fontsize=7.2, color=tcol, fontweight="bold")
        left_p += pct
    ax_a.set_yticks(y)
    ax_a.set_yticklabels([MODEL_SHORT[m] for m in MODEL_ORDER], fontsize=8.0)
    ax_a.invert_yaxis()
    ax_a.set_xlim(0, 102)
    ax_a.set_xlabel("Share of Collected Tests (%)")
    ax_a.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.48, -0.25), ncol=2, fontsize=6.9)
    ax_a.set_title("(a) Open-Net vs. Hermetic CI Divergence", loc="left", pad=8)

    # Panel (b): Static AST URL Precision & Recall
    x = np.arange(len(MODEL_ORDER))
    w = 0.20
    func_prec, func_rec, scope_prec, scope_rec = [], [], [], []
    for m in MODEL_ORDER:
        so = METRICS["static_oracles"][m]["CORE_13"]
        f = so["func_url_cm"]
        s = so["scope_url_cm"]
        func_prec.append(f["tp"] / max(f["tp"] + f["fp"], 1) * 100.0)
        func_rec.append(f["tp"] / max(f["tp"] + f["fn"], 1) * 100.0)
        scope_prec.append(s["tp"] / max(s["tp"] + s["fp"], 1) * 100.0)
        scope_rec.append(s["tp"] / max(s["tp"] + s["fn"], 1) * 100.0)

    b1 = ax_b.bar(x - 1.5*w, func_prec, w, label="Func AST Precision", color="#0072B2")
    b2 = ax_b.bar(x - 0.5*w, scope_prec, w, label="Scope AST Precision", color="#56B4E9")
    b3 = ax_b.bar(x + 0.5*w, func_rec, w, label="Func AST Recall", color="#D55E00")
    b4 = ax_b.bar(x + 1.5*w, scope_rec, w, label="Scope AST Recall", color="#E69F00")
    for bars in (b1, b2, b3, b4):
        for bar in bars:
            h = bar.get_height()
            ax_b.text(bar.get_x() + bar.get_width()/2, h + 1.8, f"{h:.0f}", ha="center", va="bottom", fontsize=5.3)

    ax_b.set_xticks(x)
    ax_b.set_xticklabels([MODEL_SHORT[m] for m in MODEL_ORDER], rotation=12, ha="right", fontsize=7.8)
    ax_b.set_ylabel("Percentage (%)")
    ax_b.set_ylim(0, 118)
    ax_b.grid(axis="y", linestyle="--", alpha=0.25)
    ax_b.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.50, -0.25), ncol=2, fontsize=6.9)
    ax_b.set_title("(b) Static URL-Literal AST Detection Accuracy", loc="left", pad=8)

    # Panel (c): Mock-Injection Remediation outcomes
    resc_list, fail_assert_exc, fail_key = [], [], []
    for m in MODEL_ORDER:
        mr = METRICS["rq4_flakiness_and_mock"]["mock_remediation"][m]["http_echo"]
        resc_list.append(mr["rescued"])
        sf = mr["still_fail_reasons"]
        kerr = sf.get("EXCEPTION:KeyError", 0)
        rem_other = (mr["total_viol"] - mr["rescued"]) - kerr
        fail_assert_exc.append(rem_other)
        fail_key.append(kerr)

    ym = np.arange(len(MODEL_ORDER))
    vals_a = np.array(resc_list)
    vals_b = np.array(fail_assert_exc)
    vals_c = np.array(fail_key)
    ax_c.barh(ym, vals_a, height=0.52, label="Rescued to Pass under HERMETIC_CI=1 (0 New Bug Detections)", color="#009E73", edgecolor="white")
    ax_c.barh(ym, vals_b, left=vals_a, height=0.52, label="Unrescued: Broken Assertions / 3rd-Party Contracts / Mock Misuse", color="#D55E00", edgecolor="white")
    ax_c.barh(ym, vals_c, left=vals_a + vals_b, height=0.52, label="Unrescued: Missing 3rd-Party JSON Key (KeyError)", color="#E69F00", edgecolor="white")

    for idx, (va, vb, vc) in enumerate(zip(vals_a, vals_b, vals_c)):
        tot = va + vb + vc
        if va > 0:
            ax_c.text(va/2, ym[idx], f"{va}", ha="center", va="center", color="white", fontweight="bold", fontsize=7.4)
        if vb >= 2:
            ax_c.text(va + vb/2, ym[idx], f"{vb}", ha="center", va="center", color="white", fontweight="bold", fontsize=7.4)
        extra = "  |  Collateral on non-violators: +4 pass (Unicode), -2 broke (negative)" if idx == 0 else ""
        ax_c.text(tot + 0.6, ym[idx], f"{va}/{tot} rescued ({va/tot*100:.1f}%){extra}", va="center", ha="left", fontsize=7.4, color="#0F172A")

    ax_c.set_yticks(ym)
    ax_c.set_yticklabels([MODEL_SHORT[m] for m in MODEL_ORDER], fontsize=8.0)
    ax_c.invert_yaxis()
    ax_c.set_xlim(0, 65)
    ax_c.set_xlabel("Socket-Violating Collected Tests (N=76 Across 4 Models; Identical Results for Minimal-200 & HTTP-Echo)")
    ax_c.grid(axis="x", linestyle="--", alpha=0.25)
    ax_c.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.48, -0.25), ncol=2, fontsize=7.2)
    ax_c.set_title("(c) Automated HTTP Transport Mock Remediation Outcomes on Socket-Violating Tests", loc="left", pad=8)

    save_fig(fig, "fig_4_network_mock")

if __name__ == "__main__":
    make_fig1()
    make_fig2()
    make_fig3()
    make_fig4()
    print("[+] Regenerated all 4 figures cleanly.")
