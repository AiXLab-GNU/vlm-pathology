"""Formal VLM hallucination benchmark -- LLaVA-Med v1.5-mistral-7b (Microsoft, local,
newly installed for this benchmark by resources/projects/prostate_biomarker_validation/model_workspace/download_llava_med.sh).
One of 4 models tested identically (see vlm_benchmark_common.py for shared task
definitions/rubric); see docs/05_vlm_benchmark_task_prompt.md for full context.
Mirrors pilot_vlm_benchmark_quilt.py's structure exactly (same LLaVA-family multi-image
<image>-token mechanism, verified against this repo's own llava_arch.py/mm_utils.py before
writing this), differing only in model path, code dir, venv, and conv_mode
("mistral_instruct" instead of "llava_v1").

Run with the dedicated LLaVA-Med venv (separate from .venv-quilt: different
transformers/tokenizers/bitsandbytes pins, see resources/projects/prostate_biomarker_validation/model_workspace/download_llava_med.sh):
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-llavamed/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_vlm_benchmark_llavamed.py --set pilot
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-llavamed/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_vlm_benchmark_llavamed.py --set full
"""
import argparse
import json
import os
import sys

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "llava-med-code")
MODEL_PATH = os.path.join(REPO_ROOT, "resources/projects/prostate_biomarker_validation/model_workspace", "llava-med-v1.5-mistral-7b")
sys.path.insert(0, CODE_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llava.constants import DEFAULT_IMAGE_TOKEN
from llava.model.builder import load_pretrained_model
from llava.utils import disable_torch_init
from llava.mm_utils import get_model_name_from_path

from vlm_benchmark_common import (
    CACHE_DIR, load_set, TASK1_PROMPT, parse_score_1_10, TASK2_PROMPT, score_hallucination,
    TASK3_PROMPT_TEMPLATE, parse_left_right, build_pairwise_cases,
    build_incontext_prefix_task1, build_incontext_prefix_task3,
)
from vlm_benchmark_llava_common import ask_multi_image

CONV_MODE = "mistral_instruct"
OUT_DIR = os.path.join(CACHE_DIR, "llavamed")


def run_task1(tokenizer, model, image_processor, df, log):
    print("== Task 1: absolute 1-10 severity scoring ==")
    rows = []
    for _, r in df.iterrows():
        prompt = DEFAULT_IMAGE_TOKEN + "\n" + TASK1_PROMPT
        text = ask_multi_image(tokenizer, model, image_processor, CONV_MODE, prompt, [r["path"]], max_new_tokens=10)
        score = parse_score_1_10(text)
        rows.append(dict(image_name=r["image_name"], stratum=r["stratum"], response=text, score=score))
        log["task1"].append(rows[-1])
        print(f"  {r['image_name']} [{r['stratum']}] -> score={score} raw={text!r}")
    return rows


def run_task2(tokenizer, model, image_processor, df, log):
    print("== Task 2: open-ended diagnostic query -> hallucination ==")
    rows = []
    for _, r in df.iterrows():
        prompt = DEFAULT_IMAGE_TOKEN + "\n" + TASK2_PROMPT
        text = ask_multi_image(tokenizer, model, image_processor, CONV_MODE, prompt, [r["path"]], max_new_tokens=250)
        halluc, hits = score_hallucination(text)
        rows.append(dict(image_name=r["image_name"], stratum=r["stratum"], response=text,
                          hallucinated=halluc, matched_terms=hits))
        log["task2"].append(rows[-1])
        print(f"  {r['image_name']} [{r['stratum']}] -> hallucinated={halluc} hits={hits}")
    return rows


def run_task3(tokenizer, model, image_processor, df, log, max_pairs=15):
    print("== Task 3: forced pairwise comparison (both orders) ==")
    cases = build_pairwise_cases(df, max_pairs=max_pairs)
    rows = []
    for c in cases:
        for order in ["A_left", "B_left"]:
            if order == "A_left":
                left_path, right_path = c["a_path"], c["b_path"]
                left_rank, right_rank = c["a_rank"], c["b_rank"]
            else:
                left_path, right_path = c["b_path"], c["a_path"]
                left_rank, right_rank = c["b_rank"], c["a_rank"]
            prompt = ("LEFT image: " + DEFAULT_IMAGE_TOKEN + "\nRIGHT image: " + DEFAULT_IMAGE_TOKEN
                      + "\n" + TASK3_PROMPT_TEMPLATE)
            text = ask_multi_image(tokenizer, model, image_processor, CONV_MODE, prompt,
                                    [left_path, right_path], max_new_tokens=10)
            choice = parse_left_right(text)
            gt = "LEFT" if left_rank > right_rank else "RIGHT"
            rows.append(dict(pair_id=c["pair_id"], order=order, choice=choice, ground_truth=gt,
                              correct=(choice == gt) if choice else None, raw=text))
            log["task3"].append(rows[-1])
            print(f"  pair {c['pair_id']} order={order} -> choice={choice} gt={gt} raw={text!r}")
    return rows


def run_task4(tokenizer, model, image_processor, df, exemplars, log, max_pairs=8):
    print("== Task 4: in-context variants of Task 1 and Task 3 ==")
    ex1 = build_incontext_prefix_task1(exemplars, n=3)
    prefix = "Here are labeled examples of prostate biopsy severity scores (1=benign, 10=most severe):\n"
    ex_paths = []
    for e in ex1:
        prefix += DEFAULT_IMAGE_TOKEN + f"\nSeverity score for the above image: {e['anchor_score']}\n"
        ex_paths.append(e["path"])
    rows1 = []
    for _, r in df.iterrows():
        prompt = prefix + DEFAULT_IMAGE_TOKEN + "\n" + TASK1_PROMPT
        text = ask_multi_image(tokenizer, model, image_processor, CONV_MODE, prompt,
                                ex_paths + [r["path"]], max_new_tokens=10)
        score = parse_score_1_10(text)
        rows1.append(dict(image_name=r["image_name"], stratum=r["stratum"], response=text, score=score))
        log["task4_score"].append(rows1[-1])
        print(f"  [in-context T1] {r['image_name']} [{r['stratum']}] -> score={score} raw={text!r}")

    ex3 = build_incontext_prefix_task3(exemplars, n=2)
    prefix3 = "Here are labeled examples of forced pairwise comparisons:\n"
    ex3_paths = []
    for e in ex3:
        prefix3 += ("LEFT image: " + DEFAULT_IMAGE_TOKEN + "\nRIGHT image: " + DEFAULT_IMAGE_TOKEN
                     + f"\nCorrect answer: {e['correct']}\n")
        ex3_paths += [e["left_path"], e["right_path"]]
    cases = build_pairwise_cases(df, max_pairs=max_pairs)
    rows3 = []
    for c in cases:
        for order in ["A_left", "B_left"]:
            if order == "A_left":
                left_path, right_path = c["a_path"], c["b_path"]
                left_rank, right_rank = c["a_rank"], c["b_rank"]
            else:
                left_path, right_path = c["b_path"], c["a_path"]
                left_rank, right_rank = c["b_rank"], c["a_rank"]
            prompt = (prefix3 + "LEFT image: " + DEFAULT_IMAGE_TOKEN + "\nRIGHT image: " + DEFAULT_IMAGE_TOKEN
                      + "\n" + TASK3_PROMPT_TEMPLATE)
            text = ask_multi_image(tokenizer, model, image_processor, CONV_MODE, prompt,
                                    ex3_paths + [left_path, right_path], max_new_tokens=10)
            choice = parse_left_right(text)
            gt = "LEFT" if left_rank > right_rank else "RIGHT"
            rows3.append(dict(pair_id=c["pair_id"], order=order, choice=choice, ground_truth=gt,
                               correct=(choice == gt) if choice else None, raw=text))
            log["task4_pairwise"].append(rows3[-1])
            print(f"  [in-context T3] pair {c['pair_id']} order={order} -> choice={choice} gt={gt} raw={text!r}")
    return rows1, rows3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["pilot", "full"], default="pilot")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    disable_torch_init()
    model_name = get_model_name_from_path(MODEL_PATH)
    tokenizer, model, image_processor, _ = load_pretrained_model(
        MODEL_PATH, None, model_name, False, False, device="cuda")

    df = load_set(args.set)
    n_pairs_t3, n_pairs_t4 = (40, 20) if args.set == "full" else (15, 8)
    exemplars = load_set("incontext")
    print(f"Running LLaVA-Med benchmark on '{args.set}' set: {len(df)} images")

    log = {"task1": [], "task2": [], "task3": [], "task4_score": [], "task4_pairwise": []}
    run_task1(tokenizer, model, image_processor, df, log)
    run_task2(tokenizer, model, image_processor, df, log)
    run_task3(tokenizer, model, image_processor, df, log, max_pairs=n_pairs_t3)
    run_task4(tokenizer, model, image_processor, df, exemplars, log, max_pairs=n_pairs_t4)

    out_path = os.path.join(OUT_DIR, f"results_{args.set}.json")
    with open(out_path, "w") as f:
        json.dump(log, f, indent=2)
    print(f"\nSaved raw results -> {out_path}")


if __name__ == "__main__":
    main()
