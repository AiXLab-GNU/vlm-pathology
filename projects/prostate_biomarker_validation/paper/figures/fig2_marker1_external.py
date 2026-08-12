"""Figure 2: marker 1 (H&E -> Gleason) external validation. Two panels: (a) predicted vs real
Gleason score scatter on PRECISE (n=17 images, the strongest single external-validation number
in the whole project, rho=+0.865) -- real data points, recomputed from cached results, not
hand-plotted; (b) QWK across all five evaluated cohorts + two literature reference points, to
show where zero-shot transfer sits relative to fully-supervised SOTA.
"""
import os
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = str(Path(__file__).resolve().parents[4])
sys.path.insert(0, os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace"))

BLUE = "#2a78d6"
ORANGE = "#eb6834"
MUTED = "#898781"
GRID = "#e1e0d9"

# ---- Panel (a): PRECISE scatter, real data recomputed from cached results ----
precise_df = pd.read_csv(os.path.join(ROOT, "resources/data/shared/opendataset/PRECISE/spatial_facevalidity_results_150um.csv"))
participants = pd.read_csv(os.path.join(ROOT, "resources/data/shared/opendataset/PRECISE/participants.csv")).set_index("IMAGE_NAME")
tumor_df = precise_df[precise_df["label_class"] == 1]
per_image = tumor_df.groupby("image_id")["marker1_gleason"].mean()
rows = []
for image_id, pred in per_image.items():
    if image_id not in participants.index:
        continue
    m = re.match(r"(\d)\+(\d)=(\d+)", str(participants.loc[image_id, "Gleason_score"]))
    if not m:
        continue
    rows.append((pred, int(m.group(3))))
comp = pd.DataFrame(rows, columns=["pred", "true"])
rho, p = stats.spearmanr(comp["pred"], comp["true"])

# ---- Panel (b): QWK bar chart (values already computed and reported in report.tex §QWK) ----
qwk_data = [
    ("NADT\n(own cohort)", 0.261, False),
    ("PANDA\n(zero-shot)", 0.391, False),
    ("PANDA K→R\n(refit)", 0.597, False),
    ("PANDA R→K\n(refit)", 0.567, False),
    ("TCGA-PRAD\n(zero-shot)", 0.260, False),
    ("PRECISE\n(zero-shot, real Gleason)", 0.788, False),
    ("DeepGleason*\n(literature, F1 not QWK)", None, True),
    ("PANDA winners\n(literature, supervised)", 0.865, True),
]

fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.3), dpi=200,
                          gridspec_kw={"width_ratios": [1, 1.35]})
fig.patch.set_facecolor("#fcfcfb")

# --- Panel a ---
ax = axes[0]
ax.set_facecolor("#fcfcfb")
jitter = np.random.default_rng(0).normal(0, 0.06, size=len(comp))
ax.scatter(comp["true"] + jitter, comp["pred"], s=70, color=BLUE, alpha=0.85,
           edgecolors="white", linewidths=0.8, zorder=3)
z = np.polyfit(comp["true"], comp["pred"], 1)
xs = np.linspace(comp["true"].min() - 0.3, comp["true"].max() + 0.3, 50)
ax.plot(xs, np.polyval(z, xs), color=ORANGE, linewidth=2, zorder=2, alpha=0.9)
ax.set_xlabel("Real pathologist Gleason score (PRECISE)", fontsize=9, color="#52514e")
ax.set_ylabel("Marker 1 predicted score (zero-shot, NADT-fitted)", fontsize=9, color="#52514e")
ax.set_title(f"(a) PRECISE: predicted vs. real Gleason\nSpearman ρ=+{rho:.3f}, p={p:.1g}, n={len(comp)}",
             fontsize=10, color="#0b0b0b", loc="left", fontweight="bold")
ax.grid(axis="both", color=GRID, linewidth=0.8, zorder=0)
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
for spine in ["left", "bottom"]:
    ax.spines[spine].set_color("#c3c2b7")
ax.tick_params(colors="#52514e", labelsize=8)

# --- Panel b ---
ax2 = axes[1]
ax2.set_facecolor("#fcfcfb")
labels = [d[0] for d in qwk_data]
vals = [d[1] for d in qwk_data]
is_lit = [d[2] for d in qwk_data]
x = np.arange(len(qwk_data))
colors = [MUTED if lit else BLUE for lit in is_lit]
bars = ax2.bar(x, [v if v is not None else 0 for v in vals], color=colors, width=0.62, zorder=3)
for xi, v, lit in zip(x, vals, is_lit):
    if v is None:
        ax2.text(xi, 0.10, "F1=0.806\n(different\nmetric)", ha="center", va="bottom", fontsize=7.6,
                  color="#52514e", rotation=0)
    else:
        ax2.text(xi, v + 0.015, f"{v:.3f}", ha="center", va="bottom", fontsize=8.3, color="#0b0b0b")
ax2.set_xticks(x)
ax2.set_xticklabels(labels, fontsize=7.6, color="#52514e", rotation=22, ha="right",
                     rotation_mode="anchor")
ax2.set_ylabel("Quadratic weighted kappa (QWK)", fontsize=9, color="#52514e")
ax2.set_ylim(0, 1.0)
ax2.set_title("(b) QWK across cohorts vs. literature SOTA\n(gray = literature reference, not recomputed)",
              fontsize=10, color="#0b0b0b", loc="left", fontweight="bold")
ax2.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
ax2.set_axisbelow(True)
for spine in ["top", "right"]:
    ax2.spines[spine].set_visible(False)
for spine in ["left", "bottom"]:
    ax2.spines[spine].set_color("#c3c2b7")
ax2.tick_params(colors="#52514e", labelsize=8)

plt.tight_layout()
out = os.path.join(ROOT, "paper/figures/fig2_marker1_external.pdf")
plt.savefig(out, facecolor=fig.get_facecolor())
plt.savefig(out.replace(".pdf", ".png"), facecolor=fig.get_facecolor())
print(f"saved {out}, n_precise={len(comp)}, rho={rho:.3f}, p={p:.4g}")
