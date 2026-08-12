"""Figure 1 (new, major-revision restructuring): qualification protocol schematic. Shows the
six prespecified candidate markers passing through the frozen 4-gate protocol
(docs/10_protocol_freeze.md \\S6-\\S8) into the 5-tier reliability map, with marker 7 shown as a
separate, explicitly post-hoc branch that reuses the same audit machinery without having been
prospectively frozen. Purely diagrammatic -- no new data, only visualizes the already-fixed
protocol structure.

Palette matches this project's documented convention (categorical blue/orange; ordinal blue
ramp for the 5 tiers, reused from fig1_reliability_map.py / now fig2_reliability_map.py).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D

BLUE = "#2a78d6"
ORANGE = "#eb6834"
DARK = "#0b0b0b"
GREY_TEXT = "#52514e"
GREY_LINE = "#c3c2b7"
BG = "#fcfcfb"
TIER_COLORS = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]

fig, ax = plt.subplots(figsize=(11.5, 7.2), dpi=200)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")


def box(x, y, w, h, text, facecolor="white", edgecolor=BLUE, textcolor=DARK,
        fontsize=9.5, fontweight="normal", linestyle="-", linewidth=1.6, zorder=3):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
                                 facecolor=facecolor, edgecolor=edgecolor, linewidth=linewidth,
                                 linestyle=linestyle, zorder=zorder))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize,
            color=textcolor, fontweight=fontweight, zorder=zorder + 1, linespacing=1.3)


def arrow(x0, y0, x1, y1, color=GREY_TEXT, linestyle="-", linewidth=1.6):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=14,
                                  color=color, linewidth=linewidth, linestyle=linestyle,
                                  zorder=2))


# Main flow occupies x in [19, 100]; x in [0, 17] is reserved for the marker-7 side branch.
FLOW_LEFT, FLOW_RIGHT = 19.0, 99.0
FLOW_W = FLOW_RIGHT - FLOW_LEFT
FLOW_MID = (FLOW_LEFT + FLOW_RIGHT) / 2

# --- Row 1: six prespecified candidates ---
markers = ["① Grade", "② Phenotype", "③ ERG→Grade",
           "④ PTEN loss", "⑤ SPOP mut.", "⑥ AR activity"]
mw, gap = 11.7, 1.3
total_w = 6 * mw + 5 * gap
mx0 = FLOW_LEFT + (FLOW_W - total_w) / 2
for i, m in enumerate(markers):
    box(mx0 + i * (mw + gap), 86, mw, 8, m, facecolor="white", edgecolor=BLUE, fontsize=8.2)
ax.text(FLOW_MID, 97, "6 candidate markers, pool and evaluation criteria fixed before results\n"
                       "(\\texttt{docs/10\\_protocol\\_freeze.md})", ha="center", va="center",
        fontsize=9.5, color=GREY_TEXT, fontweight="bold")

arrow(FLOW_MID, 86, FLOW_MID, 80.5, color=BLUE)

# --- Frozen protocol container with 4 gates ---
box(FLOW_LEFT, 46, FLOW_W, 34, "", facecolor="#f2f6fc", edgecolor=BLUE, linewidth=2, zorder=2)
ax.text(FLOW_MID, 77.5, "Frozen qualification protocol", ha="center", va="center",
        fontsize=11, color=DARK, fontweight="bold")

gates = [
    ("Gate 1", "BH-FDR $q<0.05$", "17-test family"),
    ("Gate 2", "Minimum effect size", "$|\\rho|\\geq0.15$ or AUROC$\\geq0.55$"),
    ("Gate 3", "Cross-encoder replication", "Virchow: direction matches,\nmagnitude $\\geq$50% of CONCH"),
    ("Gate 4", "Confounder audit", "nested held-out increment +\ngrade-stratified refit permutation"),
]
gw, ggap = 16.3, 1.3
gx0 = FLOW_LEFT + (FLOW_W - (4 * gw + 3 * ggap)) / 2
for i, (label, title, sub) in enumerate(gates):
    gx = gx0 + i * (gw + ggap)
    box(gx, 50, gw, 22, "", facecolor="white", edgecolor=GREY_LINE, linewidth=1.2, zorder=3)
    ax.text(gx + gw / 2, 68.5, label, ha="center", va="center", fontsize=8.5,
            color=ORANGE, fontweight="bold", zorder=4)
    ax.text(gx + gw / 2, 63.5, title, ha="center", va="center", fontsize=7.9,
            color=DARK, fontweight="bold", zorder=4, wrap=True)
    ax.text(gx + gw / 2, 56, sub, ha="center", va="center", fontsize=6.9,
            color=GREY_TEXT, zorder=4, linespacing=1.35)
    if i < 3:
        arrow(gx + gw + 0.1, 61, gx + gw + ggap - 0.1, 61, color=GREY_LINE, linewidth=1.3)

arrow(FLOW_MID, 46, FLOW_MID, 40.5, color=BLUE)

# --- 5-tier reliability map output ---
box(FLOW_LEFT, 8, FLOW_W, 30, "", facecolor="#fbfaf7", edgecolor=BLUE, linewidth=2, zorder=2)
ax.text(FLOW_MID, 35.5, "Five-tier reliability map", ha="center", va="center",
        fontsize=11, color=DARK, fontweight="bold")
tier_names = ["1. Unsupported/\nnull", "2. Context-\nsensitive",
              "3. Internally supported,\nexternally untested", "4. Cross-cohort\nreplicable",
              "5. Externally\ntransportable"]
tw, tgap = 12.9, 0.85
tx0 = FLOW_LEFT + (FLOW_W - (5 * tw + 4 * tgap)) / 2
tier2_center_x = None
for i, (name, color) in enumerate(zip(tier_names, TIER_COLORS)):
    tx = tx0 + i * (tw + tgap)
    if i == 1:
        tier2_center_x = tx + tw / 2
    ax.add_patch(FancyBboxPatch((tx, 13), tw, 15, boxstyle="round,pad=0.3,rounding_size=1.0",
                                 facecolor=color, edgecolor="none", zorder=3))
    text_color = "white" if i >= 2 else DARK
    ax.text(tx + tw / 2, 20.5, name, ha="center", va="center", fontsize=7.3,
            color=text_color, fontweight="bold", zorder=4, linespacing=1.3)

# --- Marker 7: separate post-hoc branch (reserved left margin, x in [0, 17]) ---
box(0.5, 58, 16, 16, "⑦ Recurrence\n(discovered\npost hoc,\nafter LEOPARD)",
    facecolor="#fdf1ea", edgecolor=ORANGE, textcolor=DARK, fontsize=7.6, linewidth=1.6, zorder=5)
ax.annotate("", xy=(tier2_center_x, 28.2), xytext=(8.5, 58),
            arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=1.6, linestyle="--",
                             connectionstyle="arc3,rad=-0.25"))
ax.text(1.5, 40, "same audit tools,\napplied retrospectively\n(never prospectively frozen)",
        ha="left", va="center", fontsize=7.0, color=ORANGE, style="italic", linespacing=1.3)

legend_elements = [
    Line2D([0], [0], color=BLUE, lw=1.6, label="Prespecified path (6 candidates)"),
    Line2D([0], [0], color=ORANGE, lw=1.6, linestyle="--", label="Post-hoc path (marker 7)"),
]
fig.legend(handles=legend_elements, loc="lower center", bbox_to_anchor=(0.5, 0.005), ncol=2,
           frameon=False, fontsize=8.5, labelcolor=GREY_TEXT)

fig.suptitle("Qualification protocol: from candidate markers to reliability tiers",
             fontsize=13, color=DARK, fontweight="bold", y=0.995)

out = str(Path(__file__).resolve().with_suffix(".pdf"))
plt.tight_layout(rect=[0, 0.03, 1, 0.97])
plt.savefig(out, facecolor=fig.get_facecolor())
plt.savefig(out.replace(".pdf", ".png"), facecolor=fig.get_facecolor())
print(f"saved {out}")
