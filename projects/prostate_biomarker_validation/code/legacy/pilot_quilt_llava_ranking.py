"""Blinded ranking pilot: does Quilt-LLaVA's own concern score (1-10, no numbers shown)
agree with our dab_ring-based ranking of the same 6 gland candidates from GNUH 1034538.svs?

This is the "VLM front-end, our tool as scorer" idea inverted into something we can actually
grade: instead of asking VLM to point at pixel coordinates (which LLaVA-style models aren't
trained to do), we give it one candidate crop at a time -- crops we already extracted via
find_gland_candidates(), so we already know each one's coordinates and dab_ring -- and ask
for an independent 1-10 concern rating. VLM never sees our numbers or labels. Then we check
whether its ranking of the 6 crops matches our dab_ring ranking (Spearman correlation).

This is still a single-slide, n=6 pilot -- a sanity check on the idea, not a validation.

Run with the VLM-only venv:
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-quilt/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_quilt_llava_ranking.py
"""
import os
import re
import sys

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "quilt-llava-code")
MODEL_PATH = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "Quilt-Llava-v1.5-7b")
CROPS_DIR = os.path.join(REPO_ROOT, "song-datasets", "_previews", "gland_candidates")
sys.path.insert(0, CODE_DIR)

import torch
from llava.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN
from llava.conversation import conv_templates
from llava.model.builder import load_pretrained_model
from llava.utils import disable_torch_init
from llava.mm_utils import process_images, tokenizer_image_token, get_model_name_from_path
from PIL import Image
from scipy import stats

QUESTION = (
    "This is a cropped immunohistochemistry image from a prostate biopsy, stained for a "
    "basal cell marker (an intact brown/DAB ring around a gland means the basal cell layer "
    "is present = benign; a lost or faint ring means it may be absent = concerning for "
    "carcinoma). On a scale from 1 (clearly benign, ring fully intact) to 10 (clearly "
    "concerning, ring lost or absent), how would you rate this gland? Answer with the "
    "number first, then one short sentence of justification."
)

# ground truth from v2_gland_lumen_analysis.py's actual run on 1034538.svs (not shown to model)
CANDIDATES = [
    ("suspect_1", 0.0156), ("suspect_2", 0.0161), ("suspect_3", 0.0172),
    ("benign_ref_3", 0.0888), ("benign_ref_2", 0.0890), ("benign_ref_1", 0.0993),
]


def ask(tokenizer, model, conv_mode, image_tensor, question):
    conv = conv_templates[conv_mode].copy()
    conv.append_message(conv.roles[0], DEFAULT_IMAGE_TOKEN + '\n' + question)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()
    input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX,
                                       return_tensors='pt').unsqueeze(0).to(model.device)
    with torch.inference_mode():
        output_ids = model.generate(
            input_ids, images=image_tensor, do_sample=False, temperature=0.0,
            max_new_tokens=150, use_cache=True)
    return tokenizer.decode(output_ids[0, input_ids.shape[1]:], skip_special_tokens=True).strip()


def parse_score(text):
    m = re.search(r"\b([1-9]|10)\b", text)
    return int(m.group(1)) if m else None


def main():
    disable_torch_init()
    model_name = get_model_name_from_path(MODEL_PATH)
    tokenizer, model, image_processor, _ = load_pretrained_model(
        MODEL_PATH, None, model_name, False, False, device="cuda")
    conv_mode = "llava_v1"

    results = []
    for tag, dab_ring in CANDIDATES:
        path = os.path.join(CROPS_DIR, f"1034538_{tag}.png")
        image = Image.open(path).convert("RGB")
        image_tensor = process_images([image], image_processor, model.config)
        image_tensor = image_tensor.to(model.device, dtype=torch.float16)

        response = ask(tokenizer, model, conv_mode, image_tensor, QUESTION)
        score = parse_score(response)
        results.append(dict(tag=tag, dab_ring=dab_ring, score=score, response=response))
        print(f"\n{tag} (dab_ring={dab_ring:.4f}) -> parsed_score={score}")
        print(f"  raw: {response}")

    print(f"\n{'='*80}\nSUMMARY\n{'='*80}")
    for r in sorted(results, key=lambda r: r["dab_ring"]):
        print(f"  {r['tag']:14s} dab_ring={r['dab_ring']:.4f}  vlm_score={r['score']}")

    valid = [r for r in results if r["score"] is not None]
    if len(valid) >= 3:
        rho, p = stats.spearmanr([r["dab_ring"] for r in valid], [r["score"] for r in valid])
        print(f"\nSpearman(dab_ring, vlm_score) = {rho:+.3f}  p={p:.4g}  (n={len(valid)})")
        print("(expect negative rho: higher dab_ring = more benign = lower VLM concern score)")
    else:
        print(f"\nOnly {len(valid)}/{len(results)} scores parsed -- can't compute correlation.")


if __name__ == "__main__":
    main()
