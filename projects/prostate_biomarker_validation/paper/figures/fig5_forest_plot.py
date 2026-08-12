"""Figure 5: forest plot of the 6 pre-registered pool markers, patient-level effect size with
bootstrap 95% CI (from resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv -- BH-FDR corrected,
2000-resample patient-cluster bootstrap, already computed and reported in report.tex Table 20;
this script only visualizes those numbers). AUROC-based markers (④,⑤ binary tasks) are
rescaled to 2*(AUROC-0.5) so 0 = chance on the SAME axis as Spearman rho (also 0 = null) --
noted explicitly on the axis label, not silently conflated.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BLUE = "#2a78d6"
RED = "#e34948"
GRID = "#e1e0d9"

df = pd.read_csv(f"{ROOT}/resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv").iloc[:6].copy()
df["marker_label"] = ["① Grade", "② Phenotype", "③ ERG→Grade", "④ PTEN loss",
                       "⑤ SPOP mut.", "⑥ AR activity"]

def rescale(row):
    if row["task"] == "binary":
        return 2 * (row["patient_metric"] - 0.5), 2 * (row["patient_ci_lo"] - 0.5), \
               2 * (row["patient_ci_hi"] - 0.5)
    return row["patient_metric"], row["patient_ci_lo"], row["patient_ci_hi"]

vals = df.apply(rescale, axis=1, result_type="expand")
vals.columns = ["est", "lo", "hi"]
df = pd.concat([df, vals], axis=1)
df = df.iloc[::-1].reset_index(drop=True)  # top-to-bottom = ①..⑥

fig, ax = plt.subplots(figsize=(8.5, 4.6), dpi=200)
fig.patch.set_facecolor("#fcfcfb")
ax.set_facecolor("#fcfcfb")

y = np.arange(len(df))
sig = df["patient_q_BH_FDR"] < 0.05
colors = [BLUE if s else RED for s in sig]

ax.hlines(y, df["lo"], df["hi"], color=colors, linewidth=2.2, zorder=2)
ax.scatter(df["est"], y, s=90, color=colors, zorder=3, edgecolors="white", linewidths=1)
ax.axvline(0, color="#898781", linewidth=1.2, linestyle=":", zorder=1)

for yi, (est, lo, hi, q, metric_kind) in enumerate(
        zip(df["est"], df["lo"], df["hi"], df["patient_q_BH_FDR"], df["task"])):
    unit = "AUROC-scale" if metric_kind == "binary" else "ρ"
    ax.text(hi + 0.05, yi, f"{est:+.2f} [{lo:+.2f}, {hi:+.2f}]  q={q:.2g}",
            va="center", fontsize=8.2, color="#52514e")

ax.set_yticks(y)
ax.set_yticklabels(df["marker_label"], fontsize=10, color="#0b0b0b")
ax.set_xlabel("Patient-level effect size: Spearman ρ, or 2×(AUROC−0.5) for binary tasks "
              "(0 = chance/null on both scales)", fontsize=8.3, color="#52514e")
ax.set_xlim(-0.6, 1.55)
ax.set_title("Patient-level effect size ± bootstrap 95% CI, BH-FDR corrected",
              fontsize=12, color="#0b0b0b", loc="left", fontweight="bold", pad=12)
ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
ax.set_axisbelow(True)
for spine in ["top", "right", "left"]:
    ax.spines[spine].set_visible(False)
ax.spines["bottom"].set_color("#c3c2b7")
ax.tick_params(colors="#52514e", labelsize=8.5)

handles = [plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=BLUE, markersize=9,
                       label="q < 0.05"),
           plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=RED, markersize=9,
                       label="not significant (q ≥ 0.05)")]
ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=8.3, labelcolor="#0b0b0b")

plt.tight_layout()
out = f"{ROOT}/paper/figures/fig5_forest_plot.pdf"
plt.savefig(out, facecolor=fig.get_facecolor())
plt.savefig(out.replace(".pdf", ".png"), facecolor=fig.get_facecolor())
print(f"saved {out}")
