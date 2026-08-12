"""Figure 6: AR-activity (marker 6) per-site forest plot (Tier-1 review item 1.3). One row per
TCGA-PRAD tissue-source site (leave-one-site-out: trained on the other five sites, tested on
the held-out site), patient-cluster bootstrap 95% CI (2000 resamples, from
resources/projects/prostate_biomarker_validation/model_workspace/ar_site_forest_summary.csv), plus a pooled row (5-fold patient-disjoint internal CV
across all sites, from resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv). Same visual style as
fig5_forest_plot.py.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BLUE = "#2a78d6"
ORANGE = "#eb6834"
GRID = "#e1e0d9"

df = pd.read_csv(f"{ROOT}/resources/projects/prostate_biomarker_validation/model_workspace/ar_site_forest_summary.csv")
site_labels = {"CH": "CH", "EJ": "EJ", "G9": "G9", "HC": "HC", "KK": "KK", "YL": "YL"}
df["label"] = df.apply(
    lambda r: f"Site {site_labels.get(r['site'], r['site'])} (n={r['n_patients']})"
    if r["kind"] == "leave-one-site-out" else f"Pooled, all sites (n={r['n_patients']})",
    axis=1)

# top-to-bottom: pooled at bottom, sites above in ascending rho order for readability
sites_df = df[df["kind"] == "leave-one-site-out"].sort_values("rho").reset_index(drop=True)
pooled_df = df[df["kind"] == "pooled"].reset_index(drop=True)
plot_df = pd.concat([pooled_df, sites_df], ignore_index=True).iloc[::-1].reset_index(drop=True)

fig, ax = plt.subplots(figsize=(8.2, 5.1), dpi=200)
fig.patch.set_facecolor("#fcfcfb")
ax.set_facecolor("#fcfcfb")

y = np.arange(len(plot_df))
colors = [ORANGE if k == "pooled" else BLUE for k in plot_df["kind"]]

ax.hlines(y, plot_df["ci_lo"], plot_df["ci_hi"], color=colors, linewidth=2.2, zorder=2)
ax.scatter(plot_df["rho"], y, s=90, color=colors, zorder=3, edgecolors="white", linewidths=1)
ax.axvline(0, color="#898781", linewidth=1.2, linestyle=":", zorder=1)

for yi, (rho, lo, hi) in enumerate(zip(plot_df["rho"], plot_df["ci_lo"], plot_df["ci_hi"])):
    ax.text(hi + 0.06, yi, f"{rho:+.2f} [{lo:+.2f}, {hi:+.2f}]",
            va="center", fontsize=8.2, color="#52514e")

ax.set_yticks(y)
ax.set_yticklabels(plot_df["label"], fontsize=9.5, color="#0b0b0b")
ax.set_xlabel("Spearman ρ (H&E → AR-activity score), patient-cluster bootstrap 95% CI",
              fontsize=8.8, color="#52514e")
ax.set_xlim(-0.9, 1.15)
ax.set_title("Marker 6 (AR activity): per-site leave-one-site-out effect size vs.\npooled internal-CV estimate",
              fontsize=11.5, color="#0b0b0b", loc="left", fontweight="bold", pad=12)
ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
ax.set_axisbelow(True)
for spine in ["top", "right", "left"]:
    ax.spines[spine].set_visible(False)
ax.spines["bottom"].set_color("#c3c2b7")
ax.tick_params(colors="#52514e", labelsize=8.5)

handles = [plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=ORANGE, markersize=9,
                       label="Pooled (all sites, internal CV)"),
           plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=BLUE, markersize=9,
                       label="Held-out site (leave-one-site-out)")]
ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2,
          frameon=False, fontsize=8.3, labelcolor="#0b0b0b")

plt.tight_layout(rect=[0, 0.04, 1, 1])
out = f"{ROOT}/paper/figures/fig6_ar_site_forest.pdf"
plt.savefig(out, facecolor=fig.get_facecolor())
plt.savefig(out.replace(".pdf", ".png"), facecolor=fig.get_facecolor())
print(f"saved {out}")
