"""Nested held-out incremental-value forest plot from generated analysis CSV."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
data = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_summary.csv")
data = data[data["scope"] == "patient"].copy()
data["label"] = [
    "PTEN loss\nΔAUROC",
    "AR activity\nΔR²",
    "Marker 7: grade-only\nΔC-index",
    "Marker 7: fully adjusted\nΔC-index",
]

fig, ax = plt.subplots(figsize=(7.6, 4.0), dpi=200)
colors = ["#75879a", "#75879a", "#2468a2", "#75879a"]
positions = list(range(len(data)))[::-1]
for position, (_, row), color in zip(positions, data.iterrows(), colors):
    low = row["delta"] - row["ci_low"]
    high = row["ci_high"] - row["delta"]
    ax.errorbar(row["delta"], position, xerr=[[low], [high]], fmt="o", color=color,
                ecolor=color, capsize=3, markersize=6, linewidth=1.7)
ax.axvline(0, color="#333333", linewidth=1, linestyle="--")
ax.set_yticks(positions, data["label"])
ax.set_xlabel("Nested held-out increment (combined − clinical)")
ax.set_title("Image-score incremental value after clinical adjustment", loc="left",
             fontsize=11, fontweight="bold")
ax.spines[["top", "right", "left"]].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.grid(axis="x", color="#e5e5e5", linewidth=0.7)
fig.tight_layout()
out = HERE / "fig7_nested_confounder"
fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
fig.savefig(out.with_suffix(".png"), dpi=220, bbox_inches="tight")
print(f"saved {out}.pdf/.png")
