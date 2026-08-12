"""Diagnose what CONCH is actually good/bad at, using SICAPv2's REAL pathologist ground truth
(NC/G3/G4/G5 per-patch labels, G4C cribriform flag) instead of our own dab_ring proxy -- this
is the G-N1 gap our own experiments couldn't close (we never had real ground truth to check
CONCH, or our own pipeline, against). SICAPv2 ships its own slide-disjoint train/test split
(partition/Test/{Train,Test}.xlsx, 124 vs 31 slides, zero slide overlap) which we reuse as-is.

Two tasks, each tested two ways (zero-shot text-image similarity, and a logistic-regression
probe on frozen CONCH raw features trained on the Train split, evaluated on the held-out Test
split):
  A. NC vs Cancer (any Gleason grade) -- the most basic possible discrimination task.
  B. G4C (cribriform) vs non-cribriform, restricted to Gleason-4 patches only -- the harder,
     more specific task closest to what we actually care about.

Run with the CONCH-only venv:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_sicap_diagnostic.py
"""
import os
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from PIL import Image
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from conch.open_clip_custom import create_model_from_pretrained, get_tokenizer, tokenize

SICAP_ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/data/shared/opendataset/SICAPv2/SICAPv2"
IMG_DIR = os.path.join(SICAP_ROOT, "images")
MODEL_CFG = "conch_ViT-B-16"
HF_HUB_ID = "hf_hub:MahmoodLab/conch"
N_PER_CLASS_TRAIN = 150
N_PER_CLASS_TEST = 75
SEED = 0

TEXT_BENIGN = "benign prostate glandular tissue, non-cancerous, normal histology"
TEXT_MALIGNANT = "prostate adenocarcinoma, cancerous glands"
TEXT_NONCRIB = ("Gleason pattern 4 prostate adenocarcinoma, fused or poorly formed glands, "
                "no cribriform pattern")
TEXT_CRIB = ("cribriform pattern Gleason 4 prostate adenocarcinoma, glands fused with "
             "multiple lumina in a sieve-like pattern")


def load_split(name):
    return pd.read_excel(os.path.join(SICAP_ROOT, "partition", "Test", f"{name}.xlsx"))


def sample_balanced(df, pos_mask, neg_mask, n_pos, n_neg, seed):
    pos = df[pos_mask].sample(n=min(n_pos, pos_mask.sum()), random_state=seed)
    neg = df[neg_mask].sample(n=min(n_neg, neg_mask.sum()), random_state=seed)
    return pos, neg


@torch.inference_mode()
def embed_images(model, preprocess, device, image_names, raw=True):
    feats = []
    for name in image_names:
        img = preprocess(Image.open(os.path.join(IMG_DIR, name)).convert("RGB")).unsqueeze(0).to(device)
        f = model.encode_image(img, proj_contrast=not raw, normalize=not raw)
        feats.append(f.squeeze(0).cpu().numpy())
    return np.stack(feats)


def run_task(task_name, model, preprocess, tokenizer, device,
             train_pos, train_neg, test_pos, test_neg, text_pos, text_neg):
    print(f"\n{'='*80}\n{task_name}\n{'='*80}")
    print(f"train: {len(train_pos)} pos / {len(train_neg)} neg   "
          f"test: {len(test_pos)} pos / {len(test_neg)} neg")

    # --- zero-shot on the test set ---
    with torch.inference_mode():
        text_tokens = tokenize(texts=[text_neg, text_pos], tokenizer=tokenizer).to(device)
        text_feat = F.normalize(model.encode_text(text_tokens), dim=-1)

    test_names = list(test_pos) + list(test_neg)
    test_labels = np.array([1] * len(test_pos) + [0] * len(test_neg))
    zs_feats = embed_images(model, preprocess, device, test_names, raw=False)
    zs_sims = zs_feats @ text_feat.cpu().numpy().T  # (n, 2): [sim_neg, sim_pos]
    zs_score = zs_sims[:, 1] - zs_sims[:, 0]
    zs_auc = roc_auc_score(test_labels, zs_score)
    print(f"zero-shot AUC (pos={text_pos[:40]}... vs neg={text_neg[:40]}...): {zs_auc:.3f}")

    # --- linear probe: train on Train split, eval on Test split ---
    train_names = list(train_pos) + list(train_neg)
    train_labels = np.array([1] * len(train_pos) + [0] * len(train_neg))
    train_feats = embed_images(model, preprocess, device, train_names, raw=True)
    test_feats_raw = embed_images(model, preprocess, device, test_names, raw=True)

    probe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
    probe.fit(train_feats, train_labels)
    probe_score = probe.predict_proba(test_feats_raw)[:, 1]
    probe_auc = roc_auc_score(test_labels, probe_score)
    print(f"linear probe AUC (trained on {len(train_names)} Train-split patches, "
          f"held-out on {len(test_names)} Test-split patches): {probe_auc:.3f}")
    return dict(task=task_name, zeroshot_auc=zs_auc, probe_auc=probe_auc)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()
    tokenizer = get_tokenizer()

    train_df, test_df = load_split("Train"), load_split("Test")

    results = []

    # Task A: NC vs Cancer
    tr_pos, tr_neg = sample_balanced(train_df, train_df.NC == 0, train_df.NC == 1,
                                      N_PER_CLASS_TRAIN, N_PER_CLASS_TRAIN, SEED)
    te_pos, te_neg = sample_balanced(test_df, test_df.NC == 0, test_df.NC == 1,
                                      N_PER_CLASS_TEST, N_PER_CLASS_TEST, SEED)
    results.append(run_task(
        "Task A: NC (benign) vs Cancer (any grade)", model, preprocess, tokenizer, device,
        tr_pos.image_name, tr_neg.image_name, te_pos.image_name, te_neg.image_name,
        TEXT_MALIGNANT, TEXT_BENIGN))

    # Task B: G4C (cribriform) vs G4-non-cribriform, restricted to G4==1
    g4_train = train_df[train_df.G4 == 1]
    g4_test = test_df[test_df.G4 == 1]
    tr_pos, tr_neg = sample_balanced(g4_train, g4_train.G4C == 1, g4_train.G4C == 0,
                                      N_PER_CLASS_TRAIN, N_PER_CLASS_TRAIN, SEED)
    te_pos, te_neg = sample_balanced(g4_test, g4_test.G4C == 1, g4_test.G4C == 0,
                                      N_PER_CLASS_TEST, N_PER_CLASS_TEST, SEED)
    results.append(run_task(
        "Task B: Cribriform vs non-cribriform (within Gleason 4 only)", model, preprocess,
        tokenizer, device, tr_pos.image_name, tr_neg.image_name, te_pos.image_name,
        te_neg.image_name, TEXT_CRIB, TEXT_NONCRIB))

    print(f"\n{'='*80}\nSUMMARY\n{'='*80}")
    for r in results:
        print(f"{r['task']:55s} zero-shot AUC={r['zeroshot_auc']:.3f}  probe AUC={r['probe_auc']:.3f}")


if __name__ == "__main__":
    main()
