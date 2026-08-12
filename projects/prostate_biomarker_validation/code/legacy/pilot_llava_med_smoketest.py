"""Smoke test: does LLaVA-Med load and produce a coherent text response to ONE image + ONE
question? This is purely a pipeline-works check (image in, text out) for the 4-model VLM
hallucination benchmark (docs/05_vlm_benchmark_task_prompt.md) -- not a medical-accuracy
check, not a hallucination measurement. Modeled on resources/projects/prostate_biomarker_validation/model_workspace/pilot_quilt_llava_test.py's
loading pattern.

Model:  microsoft/llava-med-v1.5-mistral-7b, downloaded via resources/projects/prostate_biomarker_validation/model_workspace/download_llava_med.sh
        to resources/projects/prostate_biomarker_validation/model_workspace/llava-med-v1.5-mistral-7b (full weights, no delta merge needed).
Code:   resources/projects/prostate_biomarker_validation/model_workspace/llava-med-code (cloned from https://github.com/microsoft/LLaVA-Med.git)
Image:  one existing SICAPv2 H&E patch (already in this repo, no new download).

Run with the dedicated LLaVA-Med venv (separate from .venv-quilt -- LLaVA-Med v1.5 pins
transformers==4.36.2 / tokenizers>=0.15.0, which conflicts with quilt-llava-code's
transformers==4.31.0 / tokenizers==0.13.3):
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-llavamed/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_llava_med_smoketest.py

Note: on first run, the CLIP vision tower (openai/clip-vit-large-patch14-336) is pulled
from the HF hub automatically (~1.7GB) -- requires internet access at load time.
"""
import os
import sys

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")  # GPU 1 was free at setup time -- re-check with nvidia-smi

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "llava-med-code")
MODEL_PATH = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "llava-med-v1.5-mistral-7b")
IMAGE_PATH = os.path.join(
    REPO_ROOT, "opendataset", "SICAPv2", "SICAPv2", "images",
    "16B0001851_Block_Region_1_0_0_xini_6803_yini_59786.jpg",
)
sys.path.insert(0, CODE_DIR)

import torch
from llava.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN
from llava.conversation import conv_templates
from llava.model.builder import load_pretrained_model
from llava.utils import disable_torch_init
from llava.mm_utils import process_images, tokenizer_image_token, get_model_name_from_path
from PIL import Image

QUESTION = "What tissue structures do you see in this histopathology image?"


def main():
    assert os.path.isfile(IMAGE_PATH), f"missing test image: {IMAGE_PATH}"

    disable_torch_init()
    model_name = get_model_name_from_path(MODEL_PATH)
    print(f"model_name resolved from path: {model_name!r}")
    tokenizer, model, image_processor, context_len = load_pretrained_model(
        MODEL_PATH, None, model_name, False, False, device="cuda")

    conv_mode = "mistral_instruct"  # LLaVA-Med v1.5-mistral's conv template
    conv = conv_templates[conv_mode].copy()
    inp = DEFAULT_IMAGE_TOKEN + '\n' + QUESTION
    conv.append_message(conv.roles[0], inp)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()

    image = Image.open(IMAGE_PATH).convert("RGB")
    image_tensor = process_images([image], image_processor, model.config)
    image_tensor = image_tensor.to(model.device, dtype=torch.float16)

    input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX,
                                       return_tensors='pt').unsqueeze(0).to(model.device)
    with torch.inference_mode():
        output_ids = model.generate(
            input_ids, images=image_tensor, do_sample=False, temperature=0.0,
            max_new_tokens=200, use_cache=True)
    response = tokenizer.decode(output_ids[0, input_ids.shape[1]:], skip_special_tokens=True).strip()

    print(f"\nImage: {IMAGE_PATH}")
    print(f"Question: {QUESTION}")
    print(f"\n--- LLaVA-Med response ---\n{response}\n")
    assert len(response) > 0, "empty response -- pipeline did not produce text"
    print("SMOKE TEST PASSED: model loaded and produced a non-empty response.")


if __name__ == "__main__":
    main()
