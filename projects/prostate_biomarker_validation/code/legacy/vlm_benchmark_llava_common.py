"""Shared LLaVA-architecture inference helpers for the local open-source models in the
formal VLM benchmark (Quilt-LLaVA, LLaVA-Med). Both are LLaVA v1.5-family forks, so the
same loading/prompting pattern applies (see resources/projects/prostate_biomarker_validation/model_workspace/pilot_quilt_llava_test.py for the
original single-image pattern this generalizes).

Key finding (verified by reading llava/model/llava_arch.py's
prepare_inputs_labels_for_multimodal): multiple `<image>` placeholder tokens ARE natively
supported in a single prompt, matched in order against a stacked image tensor -- so
multi-image in-context prompts (task 4) and pairwise prompts (task 3) don't need composite
images; each image gets its own <image> token in the text prompt.
"""
import os

import torch
from llava.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN
from llava.conversation import conv_templates
from llava.mm_utils import process_images, tokenizer_image_token
from PIL import Image


def load_images_tensor(paths, image_processor, model):
    images = [Image.open(p).convert("RGB") for p in paths]
    tensor = process_images(images, image_processor, model.config)
    return tensor.to(model.device, dtype=torch.float16)


def ask_multi_image(tokenizer, model, image_processor, conv_mode, prompt_text_with_image_tokens,
                     image_paths, max_new_tokens=200):
    """prompt_text_with_image_tokens must contain exactly len(image_paths) occurrences of
    DEFAULT_IMAGE_TOKEN ('<image>'), in the order the images should be consumed."""
    n_tokens = prompt_text_with_image_tokens.count(DEFAULT_IMAGE_TOKEN)
    assert n_tokens == len(image_paths), f"{n_tokens} image tokens vs {len(image_paths)} paths"

    image_tensor = load_images_tensor(image_paths, image_processor, model)

    conv = conv_templates[conv_mode].copy()
    conv.append_message(conv.roles[0], prompt_text_with_image_tokens)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()
    input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX,
                                       return_tensors='pt').unsqueeze(0).to(model.device)
    with torch.inference_mode():
        output_ids = model.generate(
            input_ids, images=image_tensor, do_sample=False, temperature=0.0,
            max_new_tokens=max_new_tokens, use_cache=True)
    # Different LLaVA-family forks disagree on whether generate() prepends the input prompt
    # to its output (Quilt-LLaVA's older transformers pin does; llava-med-code's newer one
    # returns ONLY the new tokens -- confirmed by comparing against llava-med-code's own
    # eval/model_vqa.py, which decodes output_ids directly with no slicing). Detect which
    # convention applies instead of hardcoding one, so this helper works for both models.
    prefix_len = input_ids.shape[1]
    if output_ids.shape[1] > prefix_len and torch.equal(output_ids[0, :prefix_len], input_ids[0]):
        new_tokens = output_ids[0, prefix_len:]
    else:
        new_tokens = output_ids[0]
    text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    return text
