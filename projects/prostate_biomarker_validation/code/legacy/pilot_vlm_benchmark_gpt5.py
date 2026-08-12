"""Formal VLM hallucination benchmark -- GPT-5.5 (OpenAI API).
One of 4 models tested identically (see vlm_benchmark_common.py for shared task
definitions/rubric); see docs/05_vlm_benchmark_task_prompt.md for full context.
Originally targeted GPT-4o; switched to GPT-5.5 per user instruction (2026-07-29) since
GPT-5+ is now current. Pinned to the dated snapshot (not the "-chat-latest" alias) so the
benchmark stays reproducible even if OpenAI updates the alias later.

Runs all 4 task-battery items against SICAPv2's Test-split-only eval set:
  1. absolute 1-10 severity scoring (score-collapse check)
  2. open-ended diagnostic query -> hallucination rubric
  3. forced pairwise comparison, both orders -> position-bias rate + accuracy
  4. in-context variants of 1 and 3 (2-3 labeled exemplars prepended)

Usage:
    .venv/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_vlm_benchmark_gpt5.py --set pilot
    .venv/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_vlm_benchmark_gpt5.py --set full

Requires OPENAI_API_KEY in the environment (source ~/.bashrc's relevant lines if running
non-interactively; see project memory for why the guard at the top of .bashrc suppresses
env vars in non-interactive shells). Also requires the OpenAI account to have active
billing/credits -- a 2026-07-29 pilot run failed 100% with HTTP 429 insufficient_quota,
which is a billing issue unrelated to model choice; must be resolved before this script's
output means anything.
"""
import argparse
import base64
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vlm_benchmark_common import (
    CACHE_DIR, load_set, TASK1_PROMPT, parse_score_1_10, TASK2_PROMPT, score_hallucination,
    TASK3_PROMPT_TEMPLATE, parse_left_right, build_pairwise_cases, pairwise_ground_truth,
    build_incontext_prefix_task1, build_incontext_prefix_task3,
)

from openai import OpenAI

MODEL = "gpt-5.5-2026-04-23"
OUT_DIR = os.path.join(CACHE_DIR, "gpt5")


def b64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def image_content(path):
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image(path)}"}}


def ask(client, content_parts, max_tokens=200, retries=3):
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": content_parts}],
                max_completion_tokens=max_tokens,
                reasoning_effort="none",
            )
            return resp.choices[0].message.content
        except Exception as e:
            if attempt == retries - 1:
                return f"__ERROR__: {e}"
            time.sleep(2 ** attempt)


def run_task1(client, df, log):
    print("== Task 1: absolute 1-10 severity scoring ==")
    rows = []
    for _, r in df.iterrows():
        text = ask(client, [{"type": "text", "text": TASK1_PROMPT}, image_content(r["path"])])
        score = parse_score_1_10(text)
        rows.append(dict(image_name=r["image_name"], stratum=r["stratum"], response=text, score=score))
        log["task1"].append(rows[-1])
        print(f"  {r['image_name']} [{r['stratum']}] -> score={score} raw={text!r}")
    return rows


def run_task2(client, df, log):
    print("== Task 2: open-ended diagnostic query -> hallucination ==")
    rows = []
    for _, r in df.iterrows():
        text = ask(client, [{"type": "text", "text": TASK2_PROMPT}, image_content(r["path"])], max_tokens=300)
        halluc, hits = score_hallucination(text)
        rows.append(dict(image_name=r["image_name"], stratum=r["stratum"], response=text,
                          hallucinated=halluc, matched_terms=hits))
        log["task2"].append(rows[-1])
        print(f"  {r['image_name']} [{r['stratum']}] -> hallucinated={halluc} hits={hits}")
    return rows


def run_task3(client, df, log, max_pairs=15):
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
            content = [{"type": "text", "text": TASK3_PROMPT_TEMPLATE},
                       {"type": "text", "text": "LEFT image:"}, image_content(left_path),
                       {"type": "text", "text": "RIGHT image:"}, image_content(right_path)]
            text = ask(client, content, max_tokens=20)
            choice = parse_left_right(text)
            gt = "LEFT" if left_rank > right_rank else "RIGHT"
            rows.append(dict(pair_id=c["pair_id"], order=order, choice=choice, ground_truth=gt,
                              correct=(choice == gt) if choice else None, raw=text))
            log["task3"].append(rows[-1])
            print(f"  pair {c['pair_id']} order={order} -> choice={choice} gt={gt} raw={text!r}")
    return rows


def run_task4(client, df, exemplars, log, max_pairs=8):
    print("== Task 4: in-context variants of Task 1 and Task 3 ==")
    ex1 = build_incontext_prefix_task1(exemplars, n=3)
    prefix_content = [{"type": "text", "text":
                       "Here are labeled examples of prostate biopsy severity scores (1=benign, 10=most severe):"}]
    for e in ex1:
        prefix_content.append(image_content(e["path"]))
        prefix_content.append({"type": "text", "text": f"Severity score for the above image: {e['anchor_score']}"})
    rows1 = []
    for _, r in df.iterrows():
        content = prefix_content + [{"type": "text", "text": TASK1_PROMPT}, image_content(r["path"])]
        text = ask(client, content)
        score = parse_score_1_10(text)
        rows1.append(dict(image_name=r["image_name"], stratum=r["stratum"], response=text, score=score))
        log["task4_score"].append(rows1[-1])
        print(f"  [in-context T1] {r['image_name']} [{r['stratum']}] -> score={score} raw={text!r}")

    ex3 = build_incontext_prefix_task3(exemplars, n=2)
    prefix3 = [{"type": "text", "text": "Here are labeled examples of forced pairwise comparisons:"}]
    for e in ex3:
        prefix3 += [{"type": "text", "text": "LEFT image:"}, image_content(e["left_path"]),
                    {"type": "text", "text": "RIGHT image:"}, image_content(e["right_path"]),
                    {"type": "text", "text": f"Correct answer: {e['correct']}"}]
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
            content = prefix3 + [{"type": "text", "text": TASK3_PROMPT_TEMPLATE},
                                  {"type": "text", "text": "LEFT image:"}, image_content(left_path),
                                  {"type": "text", "text": "RIGHT image:"}, image_content(right_path)]
            text = ask(client, content, max_tokens=20)
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
    client = OpenAI()  # reads OPENAI_API_KEY from env

    df = load_set(args.set)
    n_pairs_t3, n_pairs_t4 = (40, 20) if args.set == "full" else (15, 8)
    exemplars = load_set("incontext")
    print(f"Running GPT-5.5 benchmark on '{args.set}' set: {len(df)} images")

    log = {"task1": [], "task2": [], "task3": [], "task4_score": [], "task4_pairwise": []}
    run_task1(client, df, log)
    run_task2(client, df, log)
    run_task3(client, df, log, max_pairs=n_pairs_t3)
    run_task4(client, df, exemplars, log, max_pairs=n_pairs_t4)

    out_path = os.path.join(OUT_DIR, f"results_{args.set}.json")
    with open(out_path, "w") as f:
        json.dump(log, f, indent=2)
    print(f"\nSaved raw results -> {out_path}")


if __name__ == "__main__":
    main()
