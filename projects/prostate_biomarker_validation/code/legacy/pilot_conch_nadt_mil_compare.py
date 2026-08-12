"""Follow-up to pilot_conch_nadt_mil_seeds.py's instability finding (full attention MIL,
~66k params, 10-seed mean rho=+0.296/+0.324 -- WORSE and far less stable than the safe 64-tile
mean baseline of +0.411/+0.479). Tests two remedies, using the already-cached tile embeddings
(resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/bags_64tile.npy, no re-embedding needed):

  (A) ENSEMBLE the 10 already-tested full-attention seeds: average their out-of-fold
      predictions instead of trusting any single seed. Averaging independent noisy estimators
      is a standard way to cancel out seed-to-seed variance -- cheap to test since it's just
      combining predictions, not a new model.
  (B) SHRINK the attention model: replace the 512->128->1 tanh-MLP attention head (~66k params)
      with a single 512->1 linear attention head (~513 params, no hidden layer, no
      nonlinearity) -- matching model capacity to the ~267-slide/fold training set much more
      conservatively. Evaluated the same way (10 seeds, per-seed stability + its own ensemble).

Run with the CONCH-only venv (fast -- no GPU embedding needed, just retraining small models):
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_nadt_mil_compare.py
"""
import os
import sys

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from scipy import stats
from sklearn.model_selection import GroupKFold

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUT_DIR = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache"
BAGS_PATH = os.path.join(OUT_DIR, "bags_64tile.npy")
META_PATH = os.path.join(OUT_DIR, "meta_64tile_bags.csv")
N_SEEDS = 10
N_SPLITS = 5


class AttentionMILFull(nn.Module):
    """Original: 512->128->1 tanh MLP attention (~66k params total)."""
    def __init__(self, dim=512, hidden=128):
        super().__init__()
        self.attention = nn.Sequential(nn.Linear(dim, hidden), nn.Tanh(), nn.Linear(hidden, 1))
        self.regressor = nn.Linear(dim, 1)

    def forward(self, tiles):
        logits = self.attention(tiles).squeeze(-1)
        weights = torch.softmax(logits, dim=0)
        pooled = (weights.unsqueeze(-1) * tiles).sum(dim=0)
        return self.regressor(pooled).squeeze(-1), weights


class AttentionMILLinear(nn.Module):
    """Shrunk: single linear layer for attention, no hidden layer (~1k params total)."""
    def __init__(self, dim=512):
        super().__init__()
        self.attention = nn.Linear(dim, 1)
        self.regressor = nn.Linear(dim, 1)

    def forward(self, tiles):
        logits = self.attention(tiles).squeeze(-1)
        weights = torch.softmax(logits, dim=0)
        pooled = (weights.unsqueeze(-1) * tiles).sum(dim=0)
        return self.regressor(pooled).squeeze(-1), weights


def train_seeded(model_cls, bags_train, y_train, bags_test, device, seed, epochs=40, lr=1e-3, wd=1e-2):
    torch.manual_seed(seed)
    rs = np.random.RandomState(seed)
    model = model_cls().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=wd)
    bags_train_t = [torch.tensor(b, dtype=torch.float32, device=device) for b in bags_train]
    y_train_t = torch.tensor(y_train, dtype=torch.float32, device=device)
    for epoch in range(epochs):
        perm = rs.permutation(len(bags_train_t))
        model.train()
        for i in perm:
            opt.zero_grad()
            pred, _ = model(bags_train_t[i])
            loss = (pred - y_train_t[i]) ** 2
            loss.backward()
            opt.step()
    model.eval()
    preds = []
    with torch.no_grad():
        for b in bags_test:
            pred, _ = model(torch.tensor(b, dtype=torch.float32, device=device))
            preds.append(pred.item())
    return np.array(preds)


def run_model(model_cls, bags_arr, y, groups, fold_splits, device, label):
    print(f"\n{'='*80}\n{label}\n{'='*80}")
    all_oof = np.zeros((N_SEEDS, len(y)))
    slide_rhos, patient_rhos = [], []
    for seed in range(N_SEEDS):
        oof = np.full(len(y), np.nan)
        for tr_idx, te_idx in fold_splits:
            train_concat = bags_arr[tr_idx].reshape(-1, bags_arr.shape[-1])
            mu, sigma = train_concat.mean(axis=0), train_concat.std(axis=0) + 1e-6
            bags_train = [(bags_arr[i] - mu) / sigma for i in tr_idx]
            bags_test = [(bags_arr[i] - mu) / sigma for i in te_idx]
            preds = train_seeded(model_cls, bags_train, y[tr_idx], bags_test, device, seed=seed)
            oof[te_idx] = preds
        all_oof[seed] = oof
        rho_s, _ = stats.spearmanr(oof, y)
        df_eval = pd.DataFrame(dict(patient_id=groups, pred=oof, true=y))
        pp = df_eval.groupby("patient_id").mean()
        rho_p, _ = stats.spearmanr(pp["pred"], pp["true"])
        slide_rhos.append(rho_s)
        patient_rhos.append(rho_p)
        print(f"seed {seed}: slide rho={rho_s:+.3f}  patient rho={rho_p:+.3f}")

    print(f"\nper-seed stability: slide mean={np.mean(slide_rhos):+.3f} std={np.std(slide_rhos):.3f} "
          f"min={min(slide_rhos):+.3f} max={max(slide_rhos):+.3f}")
    print(f"per-seed stability: patient mean={np.mean(patient_rhos):+.3f} std={np.std(patient_rhos):.3f} "
          f"min={min(patient_rhos):+.3f} max={max(patient_rhos):+.3f}")

    ensemble_oof = all_oof.mean(axis=0)
    rho_ens_s, p_ens_s = stats.spearmanr(ensemble_oof, y)
    df_eval = pd.DataFrame(dict(patient_id=groups, pred=ensemble_oof, true=y))
    pp = df_eval.groupby("patient_id").mean()
    rho_ens_p, p_ens_p = stats.spearmanr(pp["pred"], pp["true"])
    print(f"\nENSEMBLE (average of {N_SEEDS} seeds' predictions): "
          f"slide rho={rho_ens_s:+.3f} (p={p_ens_s:.4g})  patient rho={rho_ens_p:+.3f} (p={p_ens_p:.4g})")
    return dict(slide_rhos=slide_rhos, patient_rhos=patient_rhos,
                ensemble_slide=rho_ens_s, ensemble_patient=rho_ens_p)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    bags_arr = np.load(BAGS_PATH)
    meta = pd.read_csv(META_PATH)
    y = meta["gleason_total"].values
    groups = meta["patient_id"].values
    print(f"loaded {bags_arr.shape} cached tile embeddings, {len(y)} slides, "
          f"{len(set(groups))} patients")

    gkf = GroupKFold(n_splits=N_SPLITS)
    fold_splits = list(gkf.split(bags_arr, y, groups))

    results = {}
    results["full"] = run_model(AttentionMILFull, bags_arr, y, groups, fold_splits, device,
                                 "(A) FULL attention model (~66k params) -- ensemble of the 10 seeds")
    results["linear"] = run_model(AttentionMILLinear, bags_arr, y, groups, fold_splits, device,
                                   "(B) LINEAR attention model (~1k params) -- per-seed + ensemble")

    print(f"\n{'='*80}\nFINAL COMPARISON\n{'='*80}")
    print(f"{'method':45s} {'slide rho':>12s} {'patient rho':>12s}")
    print(f"{'16-tile mean (original baseline)':45s} {'+0.312':>12s} {'+0.478':>12s}")
    print(f"{'64-tile mean (coverage only)':45s} {'+0.411':>12s} {'+0.479':>12s}")
    print(f"{'64-tile FULL attention, single seed 0':45s} {results['full']['slide_rhos'][0]:>+12.3f} "
          f"{results['full']['patient_rhos'][0]:>+12.3f}")
    print(f"{'64-tile FULL attention, 10-seed mean':45s} "
          f"{np.mean(results['full']['slide_rhos']):>+12.3f} {np.mean(results['full']['patient_rhos']):>+12.3f}")
    print(f"{'64-tile FULL attention, 10-seed ENSEMBLE':45s} "
          f"{results['full']['ensemble_slide']:>+12.3f} {results['full']['ensemble_patient']:>+12.3f}")
    print(f"{'64-tile LINEAR attention, 10-seed mean':45s} "
          f"{np.mean(results['linear']['slide_rhos']):>+12.3f} {np.mean(results['linear']['patient_rhos']):>+12.3f}")
    print(f"{'64-tile LINEAR attention, 10-seed std':45s} "
          f"{np.std(results['linear']['slide_rhos']):>12.3f} {np.std(results['linear']['patient_rhos']):>12.3f}")
    print(f"{'64-tile LINEAR attention, 10-seed ENSEMBLE':45s} "
          f"{results['linear']['ensemble_slide']:>+12.3f} {results['linear']['ensemble_patient']:>+12.3f}")


if __name__ == "__main__":
    main()
