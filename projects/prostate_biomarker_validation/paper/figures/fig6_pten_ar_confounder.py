"""Figure 6 (major-revision restructuring): PTEN nested confounder audit + AR per-site forest
plot, combined into one 2-panel figure -- matches MajorRevision-v1.md's explicit "Figure 4:
PTEN confounder audit and AR site forest plot" spec. Panel (a) reuses
fig7_nested_confounder.py's data source, filtered to the PTEN/AR rows only (marker 7 moves to
its own combo figure, fig7_marker7_transfer.py). Panel (b) reuses fig6_ar_site_forest.py's
logic unchanged.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BLUE = "#2a78d6"
ORANGE = "#eb6834"
GRID = "#e1e0d9"

fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(14.0, 5.1), dpi=200,
                                  gridspec_kw={"width_ratios": [1, 1.35]})
fig.patch.set_facecolor("#fcfcfb")

# --- Panel (a): PTEN + AR nested held-out increment ---
nested = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_summary.csv")
nested = nested[(nested["scope"] == "patient") & (nested["analysis"] == "grade_only") &
                 (nested["marker"].isin(["marker4_pten", "marker6_ar"]))].copy()
nested["label"] = ["PTEN loss\nΔAUROC", "AR activity\nΔR²"]
ax_a.set_facecolor("#fcfcfb")
positions = list(range(len(nested)))[::-1]
for pos, (_, row) in zip(positions, nested.iterrows()):
    low, high = row["delta"] - row["ci_low"], row["ci_high"] - row["delta"]
    ax_a.errorbar(row["delta"], pos, xerr=[[low], [high]], fmt="o", color=BLUE,
                  ecolor=BLUE, capsize=4, markersize=8, linewidth=1.8)
ax_a.axvline(0, color="#333333", linewidth=1, linestyle="--")
ax_a.set_yticks(positions)
ax_a.set_yticklabels(nested["label"], fontsize=10)
ax_a.set_ylim(-0.8, len(nested) - 0.2)
ax_a.set_xlabel("Nested held-out increment (combined − clinical)", fontsize=9)
ax_a.set_title("(a) Confounder audit: nested held-out increment over grade",
                loc="left", fontsize=10.8, fontweight="bold")
ax_a.spines[["top", "right", "left"]].set_visible(False)
ax_a.tick_params(axis="y", length=0)
ax_a.grid(axis="x", color=GRID, linewidth=0.8)
ax_a.set_axisbelow(True)

# --- Panel (b): AR per-site forest plot ---
df = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/ar_site_forest_summary.csv")
site_labels = {"CH": "CH", "EJ": "EJ", "G9": "G9", "HC": "HC", "KK": "KK", "YL": "YL"}
df["label"] = df.apply(
    lambda r: f"Site {site_labels.get(r['site'], r['site'])} (n={r['n_patients']})"
    if r["kind"] == "leave-one-site-out" else f"Pooled, all sites (n={r['n_patients']})",
    axis=1)
sites_df = df[df["kind"] == "leave-one-site-out"].sort_values("rho").reset_index(drop=True)
pooled_df = df[df["kind"] == "pooled"].reset_index(drop=True)
plot_df = pd.concat([pooled_df, sites_df], ignore_index=True).iloc[::-1].reset_index(drop=True)

ax_b.set_facecolor("#fcfcfb")
y = np.arange(len(plot_df))
colors = [ORANGE if k == "pooled" else BLUE for k in plot_df["kind"]]
ax_b.hlines(y, plot_df["ci_lo"], plot_df["ci_hi"], color=colors, linewidth=2.2, zorder=2)
ax_b.scatter(plot_df["rho"], y, s=85, color=colors, zorder=3, edgecolors="white", linewidths=1)
ax_b.axvline(0, color="#898781", linewidth=1.2, linestyle=":", zorder=1)
for yi, (rho, lo, hi) in enumerate(zip(plot_df["rho"], plot_df["ci_lo"], plot_df["ci_hi"])):
    ax_b.text(hi + 0.06, yi, f"{rho:+.2f} [{lo:+.2f}, {hi:+.2f}]",
              va="center", fontsize=7.8, color="#52514e")
ax_b.set_yticks(y)
ax_b.set_yticklabels(plot_df["label"], fontsize=9)
ax_b.set_xlabel("Spearman ρ (H&E → AR-activity score), patient-cluster bootstrap 95% CI",
                fontsize=8.6)
ax_b.set_xlim(-0.9, 1.15)
ax_b.set_title("(b) AR activity: per-site leave-one-site-out effect size",
                loc="left", fontsize=10.8, fontweight="bold")
ax_b.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
ax_b.set_axisbelow(True)
for spine in ["top", "right", "left"]:
    ax_b.spines[spine].set_visible(False)
ax_b.spines["bottom"].set_color("#c3c2b7")
ax_b.tick_params(colors="#52514e", labelsize=8.3)
handles = [plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=ORANGE, markersize=8,
                       label="Pooled (all sites, internal CV)"),
           plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=BLUE, markersize=8,
                       label="Held-out site")]
ax_b.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2,
            frameon=False, fontsize=7.8, labelcolor="#0b0b0b")

fig.suptitle("PTEN confounder audit and AR-activity site-level stability",
             fontsize=12.5, color="#0b0b0b", fontweight="bold", y=1.03)
plt.tight_layout(rect=[0, 0.05, 1, 1])
out = str(HERE / "fig6_pten_ar_confounder.pdf")
plt.savefig(out, facecolor=fig.get_facecolor(), bbox_inches="tight")
plt.savefig(out.replace(".pdf", ".png"), facecolor=fig.get_facecolor(), bbox_inches="tight", dpi=220)
print(f"saved {out}")
