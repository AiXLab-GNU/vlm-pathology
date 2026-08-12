"""Figure 1: the reliability map -- 7 candidate markers x 5-tier qualification outcome. This is
the paper's new central claim (docs/04 item 5 flagged this as highest priority), so it leads
the figure set. Data hand-transcribed from docs/03_experimental_results.md's final tier
assignments (§1, §6b-§6g) -- not re-derived here, this script only visualizes already-reported
numbers.

Palette: validated ordinal blue ramp from the dataviz skill's reference palette (steps
250/350/450/550/650), light->dark = weak->strong evidence, clears the 2:1 ordinal-ramp floor
on the light chart surface.
"""
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Ordinal blue ramp, tier 1 (weakest) -> tier 5 (strongest)
TIER_COLORS = {
    1: "#86b6ef",  # step 250 - Unsupported/null
    2: "#5598e7",  # step 350 - Context-sensitive
    3: "#2a78d6",  # step 450 - Internally supported, externally untested
    4: "#1c5cab",  # step 550 - Cross-cohort replicable
    5: "#104281",  # step 650 - Externally transportable
}
TIER_LABELS = {
    1: "Unsupported / null",
    2: "Context-sensitive",
    3: "Internally supported, externally untested",
    4: "Cross-cohort replicable",
    5: "Externally transportable",
}

# marker: (tier, one-line evidence annotation)
MARKERS = [
    ("① H&E → Gleason grade", 5, "PANDA zero-shot ρ=+0.40; PRECISE vs real Gleason ρ=+0.87"),
    ("② H&E → Phenotype (tumor/benign)", 5, "PANDA zero-shot AUROC=0.82; PRECISE ordinal direction correct"),
    ("④ H&E → PTEN loss", 3, "Multisite-stable within TCGA-PRAD; nested ΔAUROC=+0.019, 95% CI crosses zero"),
    ("⑦ H&E → Recurrence (post-hoc)", 2, "Exploratory: CONCH transfers, Virchow fails; no increment beyond clinical+site model"),
    ("③ ERG stain → Gleason grade", 3, "Cross-encoder reproducible (Virchow ρ=+0.66); no independent cohort exists"),
    ("⑥ H&E → AR activity", 2, "Site-unstable; nested grade-adjusted ΔR²=+0.004, 95% CI crosses zero"),
    ("⑤ H&E → SPOP mutation", 1, "Null in CONCH and Virchow alike; site-split does not overturn"),
]

fig, ax = plt.subplots(figsize=(11.5, 6.3), dpi=200)
fig.patch.set_facecolor("#fcfcfb")
ax.set_facecolor("#fcfcfb")

y_pos = list(range(len(MARKERS)))[::-1]
for y, (name, tier, note) in zip(y_pos, MARKERS):
    ax.hlines(y, 0.5, tier, color="#e1e0d9", linewidth=2, zorder=1)
    ax.scatter([tier], [y], s=280, color=TIER_COLORS[tier], zorder=3,
               edgecolors="#fcfcfb", linewidths=1.5)
    wrapped = "\n".join(textwrap.wrap(note, width=54))
    ax.text(5.55, y, wrapped, va="center", ha="left", fontsize=8.3, color="#52514e",
            linespacing=1.35)

ax.set_yticks(y_pos)
ax.set_yticklabels([m[0] for m in MARKERS], fontsize=10, color="#0b0b0b")
ax.set_xlim(0.5, 5.5)
ax.set_ylim(-0.7, len(MARKERS) - 0.3)
ax.set_xticks([1, 2, 3, 4, 5])
ax.set_xticklabels(["1", "2", "3", "4", "5"], fontsize=8.5, color="#898781")
ax.tick_params(axis="both", length=0)
for spine in ["top", "right", "left"]:
    ax.spines[spine].set_visible(False)
ax.spines["bottom"].set_color("#c3c2b7")
ax.set_axisbelow(True)
ax.set_xlabel("Qualification tier (weak → strong evidence)", fontsize=9,
              color="#52514e", labelpad=8)

# annotation text needs room on the right -- reserve axes width for it, and headroom above
# for the title + legend (placed in figure-fraction coords, not axes-relative, to avoid
# overlap regardless of axes position)
fig.subplots_adjust(right=0.42, left=0.30, top=0.68, bottom=0.14)

legend_handles = [Patch(facecolor=TIER_COLORS[i], edgecolor="none", label=f"{i}. {TIER_LABELS[i]}")
                   for i in [1, 2, 3, 4, 5]]
fig.legend(handles=legend_handles, loc="upper left", bbox_to_anchor=(0.30, 0.86),
           ncol=3, frameon=False, fontsize=7.8, labelcolor="#52514e",
           handlelength=1.0, handleheight=1.0, columnspacing=1.2)

fig.suptitle("Reliability map: qualification tier by candidate marker",
             fontsize=12.5, color="#0b0b0b", x=0.30, ha="left", fontweight="bold", y=0.97)

out = str(Path(__file__).resolve().with_suffix(".pdf"))
plt.savefig(out, facecolor=fig.get_facecolor())
plt.savefig(out.replace(".pdf", ".png"), facecolor=fig.get_facecolor())
print(f"saved {out}")
