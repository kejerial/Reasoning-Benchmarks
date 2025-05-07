"""
analyze_theory_slopegraph.py

This script analyzes and visualizes differences between two models on a shared set of problems,
comparing correctness and theory alignment (RCT/PMT/NONE) via majority vote.
It outputs a slope graph summarizing the shifts in theory prevalence across different correctness scenarios.

For each model:
- Loads JSONL outputs (one JSON object per problem).
- Extracts majority-vote correctness and theory alignment for each shared problem.
- Aggregates results into a DataFrame.
- Plots a slope graph comparing theory prevalence between the models with 90% confidence intervals.

Usage:
    python analyze_theory_slopegraph.py --model1 path_model1.jsonl --model2 path_model2.jsonl --model1-label "Model 1" --model2-label "Model 2" --output-dir analysis_results --verbose

Arguments:
    --model1        Path to JSONL file for model 1.
    --model2        Path to JSONL file for model 2.
    --model1-label  (Optional) Label for model 1 in plots (default: "Model 1").
    --model2-label  (Optional) Label for model 2 in plots (default: "Model 2").
    --output-dir    Directory to save the output slope graph image (default: analysis_results).
    --verbose       (Optional) Print detailed processing information.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import binom

# ─── CONFIG ────────────────────────────────────────────────────────────────
THEORIES       = ["RCT", "PMT", "NONE"]
THEORIES_TOTAL = THEORIES + ["TOTAL"]
CONTROL_RE     = re.compile(r'[\x00-\x1F\x7F]')

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 12,
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

def load_all_models(model1_path, model2_path, verbose=False):
    paths = {'model1': model1_path, 'model2': model2_path}
    keys_by_model = {}
    for mk, path in paths.items():
        seen = set()
        with path.open(encoding="utf-8", errors="ignore") as f:
            for raw in f:
                try:
                    rec = json.loads(strip_control_chars(raw))
                    prob = rec.get("problem")
                    if isinstance(prob, str):
                        seen.add(prob.strip())
                except:
                    continue
        if verbose:
            print(f"[{mk}] Loaded {len(seen)} problems.")
        keys_by_model[mk] = seen

    common = set.intersection(*keys_by_model.values())
    print(f"✅ Common problems: {len(common)}")

    if not common:
        raise RuntimeError("No overlap in problems between models.")

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
                            j = re.sub(r"^```(?:json)?\s*|\s*```$", "", e.strip())
                            e = json.loads(j)
                        if isinstance(e, dict):
                            parsed.append(e)
                    except:
                        continue

                corr_votes = [bool(p.get("correct")) for p in parsed]
                row[f"{mk}_correct"] = (majority_vote(corr_votes) is True)
                th_votes = [canonical_theory(p.get("aligned_theory", "NONE")) for p in parsed]
                row[f"{mk}_theory"] = majority_vote(th_votes) or "NONE"

    df = pd.DataFrame(results.values())
    for mk in ['model1', 'model2']:
        df[f"{mk}_correct"] = df.get(f"{mk}_correct", False).astype(bool)
        df[f"{mk}_theory"]  = df.get(f"{mk}_theory", "NONE")
    return df

def plot_slopegraph(df, model1_key, model2_key, model1_label, model2_label, output_dir):
    MODEL_COLORS = {"model1": "#1f77b4", "model2": "#ff7f0e"}
    color1 = MODEL_COLORS[model1_key]
    color2 = MODEL_COLORS[model2_key]

    scenarios = [
        ("Both correct",        df[f"{model1_key}_correct"] &  df[f"{model2_key}_correct"]),
        ("Both incorrect",     ~df[f"{model1_key}_correct"] & ~df[f"{model2_key}_correct"]),
        ("Only correct model1", df[f"{model1_key}_correct"] & ~df[f"{model2_key}_correct"]),
        ("Only correct model2", ~df[f"{model1_key}_correct"] &  df[f"{model2_key}_correct"]),
    ]

    fig, axes = plt.subplots(1, len(THEORIES_TOTAL), figsize=(14,4), constrained_layout=True)
    total_n = len(df)
    y_idxs = list(range(len(scenarios)))

    for ax, theory in zip(axes, THEORIES_TOTAL):
        for yi, (lbl, mask) in zip(y_idxs, scenarios):
            if theory == "TOTAL":
                pct = 100 * mask.sum() / total_n
                ax.plot(pct, yi, "o", color="gray", zorder=3)
                ax.text(pct + 2.0, yi, f"{pct:.1f}%", va="center", fontsize=9)
                continue
            subset = df[mask]
            n = len(subset)
            k1 = (subset[f"{model1_key}_theory"] == theory).sum()
            k2 = (subset[f"{model2_key}_theory"] == theory).sum()
            p1 = 100 * k1 / n if n else 0
            p2 = 100 * k2 / n if n else 0
            lo1, hi1 = proportion_ci(k1, n)
            lo2, hi2 = proportion_ci(k2, n)

            ax.errorbar(p1, yi, xerr=[[p1-lo1], [hi1-p1]], fmt="o",
                        color=color1, markerfacecolor=color1, capsize=3, zorder=3)
            ax.errorbar(p2, yi, xerr=[[p2-lo2], [hi2-p2]], fmt="s",
                        color=color2, markerfacecolor="white", markeredgecolor=color2,
                        capsize=3, zorder=3)

        ax.set_xlim(0, 100)
        ax.set_xlabel("% of examples")
        ax.set_title(theory)
        if theory == THEORIES_TOTAL[0]:
            ax.set_yticks(y_idxs)
            ax.set_yticklabels([s for s,_ in scenarios])
            ax.invert_yaxis()
        else:
            ax.set_yticks([])

    fig.suptitle(f"Theory Prevalence: {model1_label} vs {model2_label} (90% CI)", fontsize=14)
    handles = [
        plt.Line2D([0], [0], marker="o", linestyle="", color=color1, label=model1_label),
        plt.Line2D([0], [0], marker="s", linestyle="", markerfacecolor="white", markeredgecolor=color2, label=model2_label),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.1), ncol=2)
    output_dir.mkdir(exist_ok=True)
    out_path = output_dir / f"slopegraph_{model1_key}_vs_{model2_key}.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"✅ Plot saved → {out_path}")

def main():
    parser = argparse.ArgumentParser(description="Analyze and plot theory alignment slope graph between two models.")
    parser.add_argument('--model1', type=Path, required=True, help="Path to JSONL file for model 1.")
    parser.add_argument('--model2', type=Path, required=True, help="Path to JSONL file for model 2.")
    parser.add_argument('--model1-label', type=str, default="Model 1", help="Label for model 1 in plots.")
    parser.add_argument('--model2-label', type=str, default="Model 2", help="Label for model 2 in plots.")
    parser.add_argument('--output-dir', type=Path, default=Path("analysis_results"), help="Output directory for plot.")
    parser.add_argument('--verbose', action='store_true', help="Print processing info.")
    args = parser.parse_args()

    df = load_all_models(args.model1, args.model2, verbose=args.verbose)
    total, malformed = len(df), (df[[f"{mk}_theory" for mk in ['model1','model2']]]=="NONE").all(axis=1).sum()
    print(f"Rows loaded: {total}\nMalformed rows: {malformed}")

    ct = pd.DataFrame({
        args.model1_label: df["model1_theory"].value_counts(),
        args.model2_label: df["model2_theory"].value_counts()
    }).fillna(0).astype(int)
    ct.loc["TOTAL"] = ct.sum()
    print("\nTheory counts by model:\n", ct, "\n")

    for mk, label in [('model1', args.model1_label), ('model2', args.model2_label)]:
        c = df[f"{mk}_correct"].sum()
        pct = 100 * c / total if total else 0
        print(f"{label}: {c}/{total} ({pct:.1f}%) correct")
    print()

    plot_slopegraph(df, "model1", "model2", args.model1_label, args.model2_label, args.output_dir)

if __name__ == "__main__":
    main()
