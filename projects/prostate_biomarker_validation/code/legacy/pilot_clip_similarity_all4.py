"""Extend pilot_clip_similarity_feature.py from 1034538 only (n=6) to all 4 GNUH slides
(n=24: 12 suspect, 12 benign_ref), to get a properly powered Mann-Whitney/AUC test instead
of the n=3-vs-3 pilot's floor-effect p=0.1.

Run with the VLM-only venv:
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-quilt/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_clip_similarity_all4.py
"""
import os
import torch
from transformers import CLIPModel, CLIPProcessor
from PIL import Image
from scipy import stats

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CROPS_DIR = os.path.join(REPO_ROOT, "song-datasets", "_previews", "gland_candidates")
MODEL_ID = "openai/clip-vit-large-patch14-336"

# (slide, tag, dab_ring, label) -- dab_ring values from the actual v2_gland_lumen_analysis.py run
CANDIDATES = [
    ("1034532", "suspect_1", 0.0173, "suspect"), ("1034532", "suspect_2", 0.0231, "suspect"),
    ("1034532", "suspect_3", 0.0639, "suspect"),
    ("1034532", "benign_ref_1", 0.1539, "benign"), ("1034532", "benign_ref_2", 0.1416, "benign"),
    ("1034532", "benign_ref_3", 0.1382, "benign"),
    ("1034536", "suspect_1", 0.0357, "suspect"), ("1034536", "suspect_2", 0.0368, "suspect"),
    ("1034536", "suspect_3", 0.0369, "suspect"),
    ("1034536", "benign_ref_1", 0.0514, "benign"), ("1034536", "benign_ref_2", 0.0500, "benign"),
    ("1034536", "benign_ref_3", 0.0495, "benign"),
    ("1034538", "suspect_1", 0.0156, "suspect"), ("1034538", "suspect_2", 0.0161, "suspect"),
    ("1034538", "suspect_3", 0.0172, "suspect"),
    ("1034538", "benign_ref_1", 0.0993, "benign"), ("1034538", "benign_ref_2", 0.0890, "benign"),
    ("1034538", "benign_ref_3", 0.0888, "benign"),
    ("1034554", "suspect_1", 0.0163, "suspect"), ("1034554", "suspect_2", 0.0181, "suspect"),
    ("1034554", "suspect_3", 0.0233, "suspect"),
    ("1034554", "benign_ref_1", 0.0647, "benign"), ("1034554", "benign_ref_2", 0.0611, "benign"),
    ("1034554", "benign_ref_3", 0.0604, "benign"),
]

TEXT_BENIGN = ("a histopathology image of a prostate gland with an intact, continuous brown "
               "basal cell layer ring, benign")
TEXT_MALIGNANT = ("a histopathology image of a prostate gland with loss of the basal cell "
                  "layer, no ring, suspicious for carcinoma")


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CLIPModel.from_pretrained(MODEL_ID).to(device).eval()
    processor = CLIPProcessor.from_pretrained(MODEL_ID)

    with torch.no_grad():
        text_inputs = processor(text=[TEXT_BENIGN, TEXT_MALIGNANT], return_tensors="pt",
                                 padding=True).to(device)
        text_features = model.get_text_features(**text_inputs)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    results = []
    for slide, tag, dab_ring, label in CANDIDATES:
        path = os.path.join(CROPS_DIR, f"{slide}_{tag}.png")
        image = Image.open(path).convert("RGB")
        with torch.no_grad():
            img_inputs = processor(images=image, return_tensors="pt").to(device)
            img_features = model.get_image_features(**img_inputs)
            img_features = img_features / img_features.norm(dim=-1, keepdim=True)
            sims = (img_features @ text_features.T).squeeze(0).cpu().tolist()
        sim_benign, sim_malignant = sims
        score = sim_malignant - sim_benign
        results.append(dict(slide=slide, tag=tag, dab_ring=dab_ring, label=label, score=score))
        print(f"{slide} {tag:14s} label={label:7s} dab_ring={dab_ring:.4f}  score={score:+.4f}")

    print(f"\n{'='*80}\nSUMMARY (n={len(results)})\n{'='*80}")
    suspect_scores = [r["score"] for r in results if r["label"] == "suspect"]
    benign_scores = [r["score"] for r in results if r["label"] == "benign"]
    print(f"suspect  (n={len(suspect_scores)}): mean={sum(suspect_scores)/len(suspect_scores):+.4f}")
    print(f"benign   (n={len(benign_scores)}): mean={sum(benign_scores)/len(benign_scores):+.4f}")

    u, p = stats.mannwhitneyu(suspect_scores, benign_scores, alternative="two-sided")
    from sklearn.metrics import roc_auc_score
    labels01 = [1 if r["label"] == "suspect" else 0 for r in results]
    scores = [r["score"] for r in results]
    auc = roc_auc_score(labels01, scores)
    print(f"\nMann-Whitney U p={p:.4g}")
    print(f"AUC (suspect vs benign_ref, using clip score directly) = {auc:.3f}")

    rho, rp = stats.spearmanr([r["dab_ring"] for r in results], [r["score"] for r in results])
    print(f"Spearman(dab_ring, clip_score) = {rho:+.3f} p={rp:.4g} "
          f"(expect negative: higher dab_ring=more benign, lower malignant-score)")

    print("\n--- per-slide breakdown (Spearman within each slide) ---")
    import collections
    by_slide = collections.defaultdict(list)
    for r in results:
        by_slide[r["slide"]].append(r)
    for slide, rows in by_slide.items():
        rho_s, p_s = stats.spearmanr([r["dab_ring"] for r in rows], [r["score"] for r in rows])
        print(f"  {slide}: spearman={rho_s:+.3f} p={p_s:.4g}")


if __name__ == "__main__":
    main()
