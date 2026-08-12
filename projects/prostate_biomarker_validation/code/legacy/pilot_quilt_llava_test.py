"""Pilot: does telling Quilt-LLaVA our pipeline's quantitative DAB-ring feature change/help
its read of a gland crop, compared to showing it only the image?

Uses two crops already produced by v2_gland_lumen_analysis.py on GNUH slide 1034538.svs
(these are DAB IHC images, not H&E -- see prostate_pathology_review.md Sec 1):
  - benign_ref_1: dab_ring=0.0993 (strong basal-marker ring -> confirmed benign)
  - suspect_1:    dab_ring=0.0156 (weak basal-marker ring -> cancer-suspect)

For each image, asks the same question twice: once with no numeric context (baseline),
once with our dab_ring value + the slide's low/high reference range appended (feature-
augmented). This is a qualitative pilot (n=2 images), not a statistical validation --
its only purpose is to see whether the feature text visibly changes the model's reasoning
before investing in a larger-scale run.

Run with the VLM-only venv (NOT the pathology-pipeline .venv -- version conflicts, see
resources/projects/prostate_biomarker_validation/model_workspace/download_quilt_llava.sh):
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-quilt/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_quilt_llava_test.py
"""
import os
import sys

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")  # GPU 1 was free at pipeline-setup time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "quilt-llava-code")
MODEL_PATH = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "Quilt-Llava-v1.5-7b")
CROPS_DIR = os.path.join(REPO_ROOT, "song-datasets", "_previews", "gland_candidates")
sys.path.insert(0, CODE_DIR)

import torch
from llava.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN, DEFAULT_IM_START_TOKEN, DEFAULT_IM_END_TOKEN
from llava.conversation import conv_templates
from llava.model.builder import load_pretrained_model
from llava.utils import disable_torch_init
from llava.mm_utils import process_images, tokenizer_image_token, get_model_name_from_path
from PIL import Image

QUESTION = ("This is a cropped immunohistochemistry image from a prostate biopsy, stained "
            "for a basal cell marker (brown/DAB signal marks an intact basal cell layer "
            "around benign glands; loss of this brown ring suggests carcinoma). Describe "
            "the glandular structures you see and assess whether the basal marker ring "
            "looks intact or lost around them.")

CASES = [
    dict(tag="benign_ref_1 (dab_ring=0.0993, strong ring)",
         path=os.path.join(CROPS_DIR, "1034538_benign_ref_1.png"), dab_ring=0.0993),
    dict(tag="suspect_1 (dab_ring=0.0156, weak ring)",
         path=os.path.join(CROPS_DIR, "1034538_suspect_1.png"), dab_ring=0.0156),
]


def ask(tokenizer, model, image_processor, conv_mode, image_tensor, question):
    conv = conv_templates[conv_mode].copy()
    inp = DEFAULT_IMAGE_TOKEN + '\n' + question
    conv.append_message(conv.roles[0], inp)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()
    input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX,
                                       return_tensors='pt').unsqueeze(0).to(model.device)
    with torch.inference_mode():
        output_ids = model.generate(
            input_ids, images=image_tensor, do_sample=False, temperature=0.0,
            max_new_tokens=300, use_cache=True)
    return tokenizer.decode(output_ids[0, input_ids.shape[1]:], skip_special_tokens=True).strip()


def main():
    disable_torch_init()
    model_name = get_model_name_from_path(MODEL_PATH)
    tokenizer, model, image_processor, _ = load_pretrained_model(
        MODEL_PATH, None, model_name, False, False, device="cuda")
    conv_mode = "llava_v1"  # matches cli.py's auto-detect for "v1" in model name

    for case in CASES:
        print(f"\n{'='*80}\n{case['tag']}\n{'='*80}")
        image = Image.open(case["path"]).convert("RGB")
        image_tensor = process_images([image], image_processor, model.config)
        image_tensor = image_tensor.to(model.device, dtype=torch.float16)

        print("\n--- baseline (image only) ---")
        print(ask(tokenizer, model, image_processor, conv_mode, image_tensor, QUESTION))

        augmented_q = (QUESTION + f"\n\nAdditional context: our automated pipeline measured "
                       f"the mean DAB intensity in the ring immediately surrounding this "
                       f"gland's lumen as {case['dab_ring']:.4f}. In this slide, ring values "
                       f"range roughly from 0.016 (weakest, most cancer-suspect) to 0.10 "
                       f"(strongest, confirmed benign).")
        print("\n--- feature-augmented (image + our dab_ring number) ---")
        print(ask(tokenizer, model, image_processor, conv_mode, image_tensor, augmented_q))


if __name__ == "__main__":
    main()
