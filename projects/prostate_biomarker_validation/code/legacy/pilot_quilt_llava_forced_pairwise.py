"""Fourth pilot: forced-choice pairwise comparison, minimal prompt (no open conversation).

Prior pilots failed two different ways:
  1) pilot_quilt_llava_ranking.py -- absolute 1-10 concern score -> gave "7" to all 6 crops,
     zero discrimination (Spearman undefined, zero variance).
  2) pilot_quilt_llava_conversation.py -- open-ended two-turn chat about a composite image ->
     hallucinated an unrelated diagnosis (neuroendocrine tumor / synaptophysin / chromogranin)
     and confused prostate basal cells with skin basal cell carcinoma.

This pilot controls for two things the earlier ones didn't:
  - Forces a single-word answer (LEFT/RIGHT) instead of open generation, to remove room for
    rambling/hallucinated narrative.
  - Tests every suspect x benign_ref pair (3x3=9) in BOTH left-right orders (18 queries total)
    to separate genuine discrimination from simple position bias (e.g. always answering LEFT).

Still a single-slide (1034538.svs) pilot -- a sanity check, not a validation.

Run with the VLM-only venv:
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-quilt/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_quilt_llava_forced_pairwise.py
"""
import os
import sys
import itertools

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "quilt-llava-code")
MODEL_PATH = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "Quilt-Llava-v1.5-7b")
CROPS_DIR = os.path.join(REPO_ROOT, "song-datasets", "_previews", "gland_candidates")
OUT_DIR = "/tmp/vlm_pairwise_composites"
os.makedirs(OUT_DIR, exist_ok=True)
sys.path.insert(0, CODE_DIR)

import torch
from llava.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN
from llava.conversation import conv_templates
from llava.model.builder import load_pretrained_model
from llava.utils import disable_torch_init
from llava.mm_utils import process_images, tokenizer_image_token, get_model_name_from_path
from PIL import Image, ImageDraw

SUSPECTS = [("suspect_1", 0.0156), ("suspect_2", 0.0161), ("suspect_3", 0.0172)]
BENIGNS = [("benign_ref_1", 0.0993), ("benign_ref_2", 0.0890), ("benign_ref_3", 0.0888)]

PROMPT = (
    "This image shows two cropped immunohistochemistry gland images from a prostate biopsy, "
    "stained for a basal cell marker, placed side by side and separated by a white divider "
    "line. A gland with an intact, continuous brown ring around it means the basal cell layer "
    "is present (benign). A gland where that brown ring is weak, broken, or absent is "
    "concerning for carcinoma. Which side shows the WEAKER or more incomplete brown ring: "
    "the LEFT gland or the RIGHT gland? Answer with exactly one word: LEFT or RIGHT."
)


def make_composite(path_a, path_b, out_path, gap=12):
    a = Image.open(path_a).convert("RGB")
    b = Image.open(path_b).convert("RGB")
    h = min(a.height, b.height)
    a = a.resize((int(a.width * h / a.height), h))
    b = b.resize((int(b.width * h / b.height), h))
    canvas = Image.new("RGB", (a.width + gap + b.width, h), (255, 255, 255))
    canvas.paste(a, (0, 0))
    canvas.paste(b, (a.width + gap, 0))
    ImageDraw.Draw(canvas).rectangle([a.width, 0, a.width + gap, h], fill=(0, 0, 0))
    canvas.save(out_path)
    return out_path


def ask(tokenizer, model, image_processor, conv_mode, image_path):
    image = Image.open(image_path).convert("RGB")
    image_tensor = process_images([image], image_processor, model.config)
    image_tensor = image_tensor.to(model.device, dtype=torch.float16)

    conv = conv_templates[conv_mode].copy()
    conv.append_message(conv.roles[0], DEFAULT_IMAGE_TOKEN + '\n' + PROMPT)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()
    input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX,
                                       return_tensors='pt').unsqueeze(0).to(model.device)
    with torch.inference_mode():
        output_ids = model.generate(
            input_ids, images=image_tensor, do_sample=False, temperature=0.0,
            max_new_tokens=10, use_cache=True)
    text = tokenizer.decode(output_ids[0, input_ids.shape[1]:], skip_special_tokens=True).strip()
    return text


def parse_side(text):
    t = text.upper()
    has_left = "LEFT" in t
    has_right = "RIGHT" in t
    if has_left and not has_right:
        return "LEFT"
    if has_right and not has_left:
        return "RIGHT"
    return None  # ambiguous/unparseable


def main():
    disable_torch_init()
    model_name = get_model_name_from_path(MODEL_PATH)
    tokenizer, model, image_processor, _ = load_pretrained_model(
        MODEL_PATH, None, model_name, False, False, device="cuda")
    conv_mode = "llava_v1"

    results = []
    for (s_tag, s_dab), (b_tag, b_dab) in itertools.product(SUSPECTS, BENIGNS):
        s_path = os.path.join(CROPS_DIR, f"1034538_{s_tag}.png")
        b_path = os.path.join(CROPS_DIR, f"1034538_{b_tag}.png")

        for order, (left_tag, left_dab, left_path, right_tag, right_dab, right_path) in [
            ("suspect_left", (s_tag, s_dab, s_path, b_tag, b_dab, b_path)),
            ("suspect_right", (b_tag, b_dab, b_path, s_tag, s_dab, s_path)),
        ]:
            comp_path = os.path.join(OUT_DIR, f"{left_tag}_vs_{right_tag}_{order}.png")
            make_composite(left_path, right_path, comp_path)
            raw = ask(tokenizer, model, image_processor, conv_mode, comp_path)
            picked_side = parse_side(raw)
            picked_tag = {"LEFT": left_tag, "RIGHT": right_tag}.get(picked_side)
            correct = (picked_tag == s_tag) if picked_tag else None
            results.append(dict(
                left_tag=left_tag, right_tag=right_tag, order=order,
                raw=raw, picked_side=picked_side, picked_tag=picked_tag,
                true_suspect=s_tag, correct=correct,
            ))
            print(f"[{left_tag} | {right_tag}] raw={raw!r} -> picked={picked_side} "
                  f"({picked_tag}) true_suspect={s_tag} correct={correct}")

    print(f"\n{'='*80}\nSUMMARY\n{'='*80}")
    n_valid = sum(1 for r in results if r["correct"] is not None)
    n_correct = sum(1 for r in results if r["correct"] is True)
    n_left_picks = sum(1 for r in results if r["picked_side"] == "LEFT")
    n_right_picks = sum(1 for r in results if r["picked_side"] == "RIGHT")
    print(f"total queries: {len(results)}, parseable: {n_valid}, unparseable: {len(results)-n_valid}")
    print(f"accuracy (picked the true suspect as weaker ring): {n_correct}/{n_valid} "
          f"= {n_correct/n_valid:.1%}" if n_valid else "no valid answers")
    print(f"position bias check: LEFT picked {n_left_picks}x, RIGHT picked {n_right_picks}x "
          f"(50/50 = no position bias; skewed = model just prefers a side)")

    import json
    with open("/tmp/vlm_pairwise_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nsaved to /tmp/vlm_pairwise_results.json")


if __name__ == "__main__":
    main()
