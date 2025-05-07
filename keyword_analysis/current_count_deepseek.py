"""
Analyze only common examples between DeepSeek V3 Base and DeepSeek R1,
aggregate majority-vote correctness and theory alignment (RCT/PMT/NONE),
and plot slope graphs comparing them.
"""

import json
import re
from pathlib import Path
from collections import Counter

import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import binom

# ─── CONFIGURATION ─────────────────────────────────────────────────────────
JSONL_PATHS = {
    "base": Path("outputs_1.4k_deepseek-v3-base.jsonl"),
    "r1":   Path("outputs_1.4k.jsonl"),
}
MODEL_LABELS = {
    "base": "DeepSeek V3 Base",
    "r1":   "DeepSeek R1",
}
MODELS = [(mk, MODEL_LABELS[mk]) for mk in JSONL_PATHS]

THEORIES       = ["RCT", "PMT", "NONE"]
THEORIES_TOTAL = THEORIES + ["TOTAL"]
CMAP           = plt.get_cmap("tab10")

plt.rcParams.update({
    "font.family": "serif",
    "font.size":  12,
    "text.usetex": False,
})


# ─── HELPERS ────────────────────────────────────────────────────────────────
def majority_vote(items):
    c = Counter(items)
    if not c:
        return None
    (item, cnt), *rest = c.most_common(2)
    if rest and rest[0][1] == cnt:
        return None
    return item

def proportion_ci(k, n, conf=0.90):
    if n == 0:
        return 0.0, 0.0
    alpha = 1 - conf
    lo = 0.0 if k == 0 else binom.ppf(alpha/2,   n, k/n) / n
    hi = 1.0 if k == n else binom.ppf(1-alpha/2, n, k/n) / n
    return 100*lo, 100*hi

# strip control chars so JSON.loads won’t break
CONTROL_RE = re.compile(r'[\x00-\x1F\x7F]')
def strip_control_chars(s):
    return CONTROL_RE.sub('', s or '')

def canonical_theory(lbl):
    if not isinstance(lbl, str):
        return "NONE"
    u = lbl.upper()
    if "RCT" in u:
        return "RCT"
    if "PMT" in u:
        return "PMT"
    return "NONE"


# ─── LOAD & MERGE ──────────────────────────────────────────────────────────
def load_all_models(paths):
    # 1) gather all raw‐problem strings per model
    keys_by_model = {}
    for mk, path in paths.items():
        seen = set()
        with path.open(encoding="utf-8", errors="ignore") as f:
            for raw in f:
                try:
                    rec = json.loads(strip_control_chars(raw))
                except:
                    continue
                prob = rec.get("problem")
                if isinstance(prob, str):
                    seen.add(prob.strip())
        keys_by_model[mk] = seen

    # diagnostic
    print("per-model problem counts:", {mk: len(s) for mk,s in keys_by_model.items()})
    common = set.intersection(*keys_by_model.values())
    print("common problem count:", len(common))
    if not common:
        raise RuntimeError("No overlap on raw problem strings! Check file paths & JSONL format.")

    # 2) re-parse only those commons, aggregate votes
    results = {}
    for mk, path in paths.items():
        with path.open(encoding="utf-8", errors="ignore") as f:
            for raw in f:
                try:
                    rec = json.loads(strip_control_chars(raw))
                except:
                    continue
                prob = rec.get("problem")
                if not isinstance(prob, str):
                    continue
                key = prob.strip()
                if key not in common:
                    continue

                row = results.setdefault(key, {"problem": key})
                parsed = []
                for e in rec.get("analysis_responses", []):
                    try:
                        if isinstance(e, str):
                            # drop ```json fences
                            j = re.sub(r"^```(?:json)?\s*|\s*```$", "", e.strip())
                            e = json.loads(j)
                        if isinstance(e, dict):
                            parsed.append(e)
                    except:
                        continue

                if parsed:
                    corr_votes = [bool(p.get("correct")) for p in parsed]
                    row[f"{mk}_correct"] = (majority_vote(corr_votes) is True)
                    th_votes = [canonical_theory(p.get("aligned_theory","NONE")) for p in parsed]
                    row[f"{mk}_theory"]   = majority_vote(th_votes) or "NONE"
                else:
                    row[f"{mk}_correct"] = False
                    row[f"{mk}_theory"]  = "NONE"

    # 3) build DataFrame
    df = pd.DataFrame(results.values())
    for mk,_ in MODELS:
        cc, tt = f"{mk}_correct", f"{mk}_theory"
        if cc not in df.columns:
            df[cc] = False
        df[cc] = df[cc].astype(bool)
        if tt not in df.columns:
            df[tt] = "NONE"

    return df


# ─── PLOTTING ──────────────────────────────────────────────────────────────
def plot_slopegraph(df: pd.DataFrame, before: str, after: str):
    label_b = dict(MODELS)[before]
    label_a = dict(MODELS)[after]

    # explicit blue & orange only
    MODEL_COLORS = {
        "base": "#1f77b4",  # matplotlib default blue
        "r1":   "#ff7f0e",  # matplotlib default orange
    }
    before_col = MODEL_COLORS[before]
    after_col  = MODEL_COLORS[after]

    scenarios = [
        ("Both correct",        df[f"{before}_correct"] &  df[f"{after}_correct"]),
        ("Both incorrect",     ~df[f"{before}_correct"] & ~df[f"{after}_correct"]),
        ("Only correct before", df[f"{before}_correct"] & ~df[f"{after}_correct"]),
        ("Only correct after", ~df[f"{before}_correct"] &  df[f"{after}_correct"]),
    ]
    y_idxs  = list(range(len(scenarios)))
    total_n = len(df)

    fig = plt.figure(figsize=(14, 4))
    gs  = fig.add_gridspec(1, len(THEORIES_TOTAL),
                           left=0.12, right=0.97, top=0.82, bottom=0.24, wspace=0.30)
    axes = [fig.add_subplot(gs[i]) for i in range(len(THEORIES_TOTAL))]

    for ax, theory in zip(axes, THEORIES_TOTAL):
        for yi, (lbl, mask) in zip(y_idxs, scenarios):
            if theory == "TOTAL":
                pct = 100 * mask.sum() / total_n
                # both markers coincide
                ax.plot(pct, yi, "o", color="gray", zorder=3)
                ax.text(pct + 2.0, yi, f"{pct:.1f}%", va="center", fontsize=9)
                continue

            subset = df[mask]
            n = len(subset)
            k_b = (subset[f"{before}_theory"] == theory).sum()
            k_a = (subset[f"{after}_theory"]  == theory).sum()
            p_b = 100 * k_b / n if n else 0
            p_a = 100 * k_a / n if n else 0
            lo_b, hi_b = proportion_ci(k_b, n)
            lo_a, hi_a = proportion_ci(k_a, n)

            # base = filled circle in base color
            ax.errorbar(
                p_b, yi,
                xerr=[[p_b-lo_b], [hi_b-p_b]],
                fmt="o",
                color=before_col,               
                markerfacecolor=before_col,
                markeredgecolor=before_col,
                capsize=3,
                zorder=3
            )
            # r1 = open square in r1 color
            ax.errorbar(
                p_a, yi,
                xerr=[[p_a-lo_a], [hi_a-p_a]],
                fmt="s",
                color=after_col,
                markerfacecolor="white",
                markeredgecolor=after_col,
                capsize=3,
                zorder=3
            )

        ax.set_xlim(0, 100)
        ax.set_xlabel("% of examples", fontsize=11)
        ax.set_title(theory if theory != "TOTAL" else "Total", fontsize=13)
        if theory == THEORIES_TOTAL[0]:
            ax.set_yticks(y_idxs)
            ax.set_yticklabels([s for s,_ in scenarios], fontsize=11)
            ax.invert_yaxis()
        else:
            ax.set_yticks([])

    fig.suptitle(f"Theory Prevalence: {label_b} vs {label_a} (90% CI)",
                 fontsize=15, y=0.93)

    # Legend
    handles = [
        plt.Line2D([0],[0],
                   marker="o", linestyle="",
                   markerfacecolor=before_col,
                   markeredgecolor=before_col,
                   label=label_b, markersize=8),
        plt.Line2D([0],[0],
                   marker="s", linestyle="",
                   markerfacecolor="white",
                   markeredgecolor=after_col,
                   label=label_a, markersize=8),
    ]
    fig.legend(handles=handles, title="Model",
               loc="lower center", bbox_to_anchor=(0.5, -0.10),
               ncol=2, frameon=True,
               edgecolor="black", facecolor="white", framealpha=1.0)

    out = Path("analysis_results") / f"slopegraph_{before}_vs_{after}.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"✅ Plot saved → {out}")


# ─── MAIN ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    df = load_all_models(JSONL_PATHS)
    total = len(df)
    malformed = ((df[[f"{mk}_theory" for mk,_ in MODELS]]=="NONE")
                  .all(axis=1)).sum()

    print(f"Rows loaded:    {total}")
    print(f"Malformed rows: {malformed}\n")

    ct = pd.DataFrame({
        MODEL_LABELS[mk]: df[f"{mk}_theory"].value_counts()
        for mk,_ in MODELS
    }).fillna(0).astype(int)
    ct.loc["TOTAL"] = ct.sum()
    print("Theory counts by model:\n", ct, "\n")

    print("Correctness counts by model:")
    for mk,label in MODELS:
        c   = df[f"{mk}_correct"].sum()
        pct = 100*c/total if total else 0
        print(f"  {label}: {c}/{total} ({pct:.1f}%)")
    print()

    plot_slopegraph(df, "base", "r1")
