"""Third pilot: phrase the question in the SAME style QUILT-Instruct actually trained on,
instead of our own ad-hoc formats (which failed twice today -- see quilt-instruct/utils/
prompts.py's sys_conversation example: "User: In which area of the image can the edematous
villi be observed...?" / "GPT: ...central and peripheral areas...").

Single composite image: left half = suspect_1 (solid cell sheet, sparse/discontinuous brown,
no clear lumen), right half = benign_ref_1 (branching glands, thick continuous brown ring) --
both independently verified by eye as genuine glandular tissue (not stroma/ink), same slide
(1034538.svs). Two-turn conversation, matching the training example's shape:
  1) "What are the key characteristics visible in this histopathology image?"
  2) "In which area of the image -- left or right -- can weaker or absent basal cell marker
     staining be observed, and what significance does that hold?"

Run with the VLM-only venv:
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-quilt/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_quilt_llava_conversation.py /path/to/composite.png
"""
import argparse
import os
import sys

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "quilt-llava-code")
MODEL_PATH = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "Quilt-Llava-v1.5-7b")
sys.path.insert(0, CODE_DIR)

import torch
from llava.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN
from llava.conversation import conv_templates
from llava.model.builder import load_pretrained_model
from llava.utils import disable_torch_init
from llava.mm_utils import process_images, tokenizer_image_token, get_model_name_from_path
from PIL import Image

TURN_1 = "What are the key characteristics visible in this histopathology image?"
TURN_2 = ("In which area of the image -- left or right -- can weaker or absent basal cell "
          "marker staining be observed, and what significance does that hold?")


def generate(tokenizer, model, conv, image_tensor):
    prompt = conv.get_prompt()
    input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX,
                                       return_tensors='pt').unsqueeze(0).to(model.device)
    with torch.inference_mode():
        output_ids = model.generate(
            input_ids, images=image_tensor, do_sample=False, temperature=0.0,
            max_new_tokens=400, use_cache=True)
    return tokenizer.decode(output_ids[0, input_ids.shape[1]:], skip_special_tokens=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Composite left-suspect/right-benign image path")
    args = parser.parse_args()
    disable_torch_init()
    model_name = get_model_name_from_path(MODEL_PATH)
    tokenizer, model, image_processor, _ = load_pretrained_model(
        MODEL_PATH, None, model_name, False, False, device="cuda")
    conv_mode = "llava_v1"

    image = Image.open(args.image).convert("RGB")
    image_tensor = process_images([image], image_processor, model.config)
    image_tensor = image_tensor.to(model.device, dtype=torch.float16)

    conv = conv_templates[conv_mode].copy()

    print(f"\nUser: {TURN_1}")
    conv.append_message(conv.roles[0], DEFAULT_IMAGE_TOKEN + '\n' + TURN_1)
    conv.append_message(conv.roles[1], None)
    answer1 = generate(tokenizer, model, conv, image_tensor)
    conv.messages[-1][-1] = answer1
    print(f"GPT: {answer1}")

    print(f"\nUser: {TURN_2}")
    conv.append_message(conv.roles[0], TURN_2)
    conv.append_message(conv.roles[1], None)
    answer2 = generate(tokenizer, model, conv, image_tensor)
    conv.messages[-1][-1] = answer2
    print(f"GPT: {answer2}")

    print(f"\n{'='*80}\nGROUND TRUTH (not shown to model): left=suspect_1 (dab_ring=0.0156, "
          f"weak/absent ring), right=benign_ref_1 (dab_ring=0.0993, strong ring)\n{'='*80}")


if __name__ == "__main__":
    main()
