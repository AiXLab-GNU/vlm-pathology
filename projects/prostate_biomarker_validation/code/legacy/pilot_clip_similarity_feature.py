"""Fifth pilot: skip language generation entirely. Use CLIP (the same openai/clip-vit-large-
patch14-336 backbone Quilt-LLaVA's vision tower was frozen at -- config.json says
"unfreeze_mm_vision_tower": false, so it is numerically the stock OpenAI CLIP, not a
pathology-tuned one) to compute a pure zero-shot image-text similarity SCORE per crop.

Three prior pilots asked the LLM to render a verdict in language and all failed differently
(constant "7", hallucinated unrelated diagnosis, constant "LEFT"). This pilot never generates
text -- it only computes cosine similarities in CLIP's embedding space, then compares the
resulting number's distribution between the 3 suspect and 3 benign_ref crops with the same
statistical toolkit used throughout this project (no LLM verdict, no hallucination surface).

Caveat to keep in mind when reading results: this CLIP backbone is GENERIC (trained on
web image-text pairs, not fine-tuned on pathology), so it may simply lack the visual concept
of "basal cell marker ring" -- a null result here would not by itself prove embeddings can
never work, only that this particular off-the-shelf backbone doesn't carry the concept.
A pathology-specific CLIP (e.g. QuiltNet, not currently downloaded) would be the natural
next thing to try if this comes back flat.

Run with the VLM-only venv (already has transformers/torch):
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-quilt/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_clip_similarity_feature.py
"""
import os
import torch
from transformers import CLIPModel, CLIPProcessor
from PIL import Image
from scipy import stats

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CROPS_DIR = os.path.join(REPO_ROOT, "song-datasets", "_previews", "gland_candidates")
MODEL_ID = "openai/clip-vit-large-patch14-336"

CANDIDATES = [
    ("suspect_1", 0.0156, "suspect"), ("suspect_2", 0.0161, "suspect"), ("suspect_3", 0.0172, "suspect"),
    ("benign_ref_3", 0.0888, "benign"), ("benign_ref_2", 0.0890, "benign"), ("benign_ref_1", 0.0993, "benign"),
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
    for tag, dab_ring, label in CANDIDATES:
        path = os.path.join(CROPS_DIR, f"1034538_{tag}.png")
        image = Image.open(path).convert("RGB")
        with torch.no_grad():
            img_inputs = processor(images=image, return_tensors="pt").to(device)
            img_features = model.get_image_features(**img_inputs)
            img_features = img_features / img_features.norm(dim=-1, keepdim=True)
            sims = (img_features @ text_features.T).squeeze(0).cpu().tolist()
        sim_benign, sim_malignant = sims
        score = sim_malignant - sim_benign  # higher = CLIP thinks more "malignant-like"
        results.append(dict(tag=tag, dab_ring=dab_ring, label=label,
                             sim_benign=sim_benign, sim_malignant=sim_malignant, score=score))
        print(f"{tag:14s} label={label:7s} dab_ring={dab_ring:.4f}  "
              f"sim_benign={sim_benign:.4f}  sim_malignant={sim_malignant:.4f}  score={score:+.4f}")

    print(f"\n{'='*80}\nSUMMARY\n{'='*80}")
    suspect_scores = [r["score"] for r in results if r["label"] == "suspect"]
    benign_scores = [r["score"] for r in results if r["label"] == "benign"]
    print(f"suspect scores:     {suspect_scores}")
    print(f"benign_ref scores:  {benign_scores}")
    print(f"suspect mean={sum(suspect_scores)/3:+.4f}  benign_ref mean={sum(benign_scores)/3:+.4f}")

    u, p = stats.mannwhitneyu(suspect_scores, benign_scores, alternative="two-sided")
    rho, rp = stats.spearmanr([r["dab_ring"] for r in results], [r["score"] for r in results])
    print(f"\nMann-Whitney U p={p:.4g} (n=3 vs 3, likely underpowered -- read qualitatively too)")
    print(f"Spearman(dab_ring, clip_score) = {rho:+.3f} p={rp:.4g} "
          f"(expect negative: higher dab_ring=more benign, lower malignant-score)")


if __name__ == "__main__":
    main()
