"""Figure 4: ROC curves for the three binary markers (② Phenotype, ④ PTEN loss, ⑤ SPOP
mutation, null). Out-of-fold predictions recomputed live from cached CONCH embeddings (same
protocol as pilot_statistical_corrections.py: GroupKFold(5), LogisticRegression(C=1.0,
class_weight="balanced")) -- not hand-plotted, real OOF ROC curves.
"""
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = str(Path(__file__).resolve().parents[4])
sys.path.insert(0, os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace"))
from pilot_confounder_audit import (CBIOPORTAL_SAMPLE_JSON, TCGA_CACHE,  # noqa: E402
                                     load_data as load_tcga_data)

NADT_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache")
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
GRID = "#e1e0d9"


def oof_binary(X, y, groups, seed=0):
    gkf = GroupKFold(n_splits=5)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(X, y, groups):
        probe = make_pipeline(StandardScaler(),
                               LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
        probe.fit(X[tr], y[tr])
        oof[te] = probe.predict_proba(X[te])[:, 1]
    return oof


# Marker 2: Phenotype (NADT, 463 slides)
X2 = np.load(os.path.join(NADT_CACHE, "X_phenotype.npy"))
meta2 = pd.read_csv(os.path.join(NADT_CACHE, "meta_phenotype.csv"))
oof2 = oof_binary(X2, meta2["label"].values, meta2["patient_id"].values)
fpr2, tpr2, _ = roc_curve(meta2["label"].values, oof2)
auc2 = roc_auc_score(meta2["label"].values, oof2)

# Marker 4 + 5: TCGA-PRAD (300 slides)
X_tcga, meta_tcga = load_tcga_data()
mask4 = meta_tcga["pten_loss"].notna()
oof4 = oof_binary(X_tcga[mask4.values], meta_tcga.loc[mask4, "pten_loss"].astype(int).values,
                   meta_tcga.loc[mask4, "case_id"].values)
fpr4, tpr4, _ = roc_curve(meta_tcga.loc[mask4, "pten_loss"].astype(int).values, oof4)
auc4 = roc_auc_score(meta_tcga.loc[mask4, "pten_loss"].astype(int).values, oof4)

data = json.load(open(CBIOPORTAL_SAMPLE_JSON))
by_attr = {}
for d in data:
    by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]
meta_tcga["spop_mut"] = meta_tcga["case_id"].map(by_attr["SPOP_MUTATION"]).astype(float)
mask5 = meta_tcga["spop_mut"].notna()
oof5 = oof_binary(X_tcga[mask5.values], meta_tcga.loc[mask5, "spop_mut"].astype(int).values,
                   meta_tcga.loc[mask5, "case_id"].values)
fpr5, tpr5, _ = roc_curve(meta_tcga.loc[mask5, "spop_mut"].astype(int).values, oof5)
auc5 = roc_auc_score(meta_tcga.loc[mask5, "spop_mut"].astype(int).values, oof5)

fig, ax = plt.subplots(figsize=(6.2, 6.2), dpi=200)
fig.patch.set_facecolor("#fcfcfb")
ax.set_facecolor("#fcfcfb")

ax.plot(fpr2, tpr2, color=BLUE, linewidth=2.4,
        label=f"② Phenotype (NADT, n={len(meta2)}), AUROC={auc2:.3f}")
ax.plot(fpr4, tpr4, color=ORANGE, linewidth=2.4,
        label=f"④ PTEN loss (TCGA-PRAD, n={mask4.sum()}), AUROC={auc4:.3f}")
ax.plot(fpr5, tpr5, color=AQUA, linewidth=2.4, linestyle=(0, (5, 2)),
        label=f"⑤ SPOP mutation (TCGA-PRAD, n={mask5.sum()}), AUROC={auc5:.3f} — null")
ax.plot([0, 1], [0, 1], color="#c3c2b7", linewidth=1.4, linestyle=":", zorder=1)

ax.set_xlabel("False positive rate", fontsize=9.5, color="#52514e")
ax.set_ylabel("True positive rate", fontsize=9.5, color="#52514e")
ax.set_title("Out-of-fold ROC: binary markers", fontsize=12.5, color="#0b0b0b",
              loc="left", fontweight="bold", pad=12)
ax.legend(loc="lower right", frameon=False, fontsize=8.4, labelcolor="#0b0b0b")
ax.set_xlim(-0.02, 1.02)
ax.set_ylim(-0.02, 1.02)
ax.set_aspect("equal")
ax.grid(color=GRID, linewidth=0.8, zorder=0)
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
for spine in ["left", "bottom"]:
    ax.spines[spine].set_color("#c3c2b7")
ax.tick_params(colors="#52514e", labelsize=8.5)

plt.tight_layout()
out = os.path.join(ROOT, "paper/figures/fig4_roc_curves.pdf")
plt.savefig(out, facecolor=fig.get_facecolor())
plt.savefig(out.replace(".pdf", ".png"), facecolor=fig.get_facecolor())
print(f"saved {out}: AUROC2={auc2:.3f} AUROC4={auc4:.3f} AUROC5={auc5:.3f}")
