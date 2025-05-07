"""
analyze_parallel.py

This script analyzes each example in a cleaned JSONL corpus using GPT-4o.
For every JSONL record (containing a problem statement, a model response,
and a reference answer), the script makes NUM_REPEATS API calls to GPT-4o
to evaluate:
    - whether the model response is correct
    - which cognitive theory the reasoning aligns with (RCT / PMT / None)
    - key reasoning characteristics

Example Usage:
    python analyze_corpus.py \
        --api-key sk-xxx \
        --model-name gpt-4o \
        --input-json cleaned_deepseek-v3-base.jsonl \
        --output-jsonl outputs_1.4k_deepseek-v3-base.jsonl \
        --num-workers 3 \
        --num-repeats 5
"""

import json
import time
import logging
import multiprocessing
from pathlib import Path
from openai import OpenAI
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
from json import JSONDecodeError
import re
from langdetect import detect, DetectorFactory
import argparse
import os

# Ensure deterministic language detection
DetectorFactory.seed = 0

CONTROL_RE = re.compile(r'[\x00-\x1F\x7F]')

def strip_control_chars(line: str) -> str:
    return CONTROL_RE.sub('', line)

def load_existing_problems(path: Path):
    seen = set()
    if not path.exists():
        return seen
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            clean = strip_control_chars(raw)
            try:
                rec = json.loads(clean)
                prob = rec.get("problem")
                if prob:
                    seen.add(prob)
            except:
                continue
    return seen

def init_client(api_key):
    global client
    client = OpenAI(api_key=api_key)

def query_once(problem, model_out, ground, system_prompt, model_name, dry_run=False):
    user_prompt = f"""Problem:\n{problem}\n\nModel Response:\n{model_out}\n\nGround Truth Answer:\n{ground}"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt}
    ]
    if dry_run:
        return '{"correct": false, "aligned_theory": "None", "reasoning_characteristics": []}'
    resp = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=0
    )
    return resp.choices[0].message.content.strip()

def clean_json_block(txt):
    return re.sub(r"^`(?:json)?\s*|\s*`$", "", txt.strip())

def process_example(ex, args):
    analyses = []
    for i in range(args.num_repeats):
        try:
            txt = query_once(
                ex["problem"], ex["model_out"], ex["ground"],
                args.prompt_system, args.model_name, args.dry_run
            )
        except Exception as e:
            logging.warning(f"[{i+1}] API error: {e}")
            time.sleep(2)
            continue

        if not txt.strip():
            logging.warning(f"[{i+1}] Empty response, skipping")
            time.sleep(2)
            continue

        raw = clean_json_block(txt)
        try:
            parsed = json.loads(raw)
        except JSONDecodeError:
            logging.warning(f"[{i+1}] Invalid JSON: {repr(txt)}")
            time.sleep(2)
            continue

        analyses.append(parsed)
        time.sleep(2.5)

    return {
        "problem": ex["problem"],
        "model_response": ex["model_out"],
        "had_model_output": ex["had_model_output"],
        "ground_truth": ex["ground"],
        "analysis_responses": analyses
    }

def main(args):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S"
    )

    existing = load_existing_problems(args.output_jsonl)
    logging.info(f"Skipping {len(existing)} already-processed examples.")

    examples = []
    with args.input_json.open("r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            clean = strip_control_chars(raw)
            try:
                rec = json.loads(clean)
            except:
                continue

            msgs = rec.get("messages", [])
            if len(msgs) < 2:
                continue

            problem = msgs[0].get("content", "").strip()
            if not problem or problem in existing:
                continue

            model_out = msgs[1].get("content", "").strip()
            if not model_out or not re.search(r"[A-Za-z]", model_out):
                continue
            try:
                if detect(model_out) != "en":
                    continue
            except:
                continue

            ground = msgs[0].get("info", {}).get("reference_answer", "") or ""
            examples.append({
                "problem": problem,
                "model_out": model_out,
                "ground": ground,
                "had_model_output": bool(model_out)
            })

    logging.info(f"Will process {len(examples)} new examples.")
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    out_f = args.output_jsonl.open("a", encoding="utf-8")

    with ProcessPoolExecutor(max_workers=args.num_workers,
                             initializer=init_client, initargs=(args.api_key,)) as pool:
        futures = [pool.submit(process_example, ex, args) for ex in examples]
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Analyzing", unit="ex"):
            rec = fut.result()
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out_f.flush()

    out_f.close()
    logging.info("All done.")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description="Analyze JSONL corpus with GPT model evaluation")
    parser.add_argument("--api-key", type=str, default=os.getenv("OPENAI_API_KEY"),
                        help="OpenAI API key (env var OPENAI_API_KEY is fallback)")
    parser.add_argument("--model-name", type=str, default="gpt-4o",
                        help="Model name (default: gpt-4o)")
    parser.add_argument("--input-json", type=Path, required=True,
                        help="Input JSONL file path")
    parser.add_argument("--output-jsonl", type=Path, required=True,
                        help="Output JSONL file path")
    parser.add_argument("--num-workers", type=int, default=3,
                        help="Number of parallel workers")
    parser.add_argument("--num-repeats", type=int, default=5,
                        help="Number of evaluations per example")
    parser.add_argument("--prompt-system", type=str, default='''You are an expert in cognitive science and reasoning analysis.
Given a reasoning problem, a model's generated response, and the ground-truth answer, evaluate:
Return JSON:
{"correct": true|false, "aligned_theory": "RCT"|"PMT"|"None", "reasoning_characteristics": ["..."]}
Only respond with the JSON object.''',
                        help="System prompt string for the assistant.")
    parser.add_argument("--dry-run", action="store_true",
                        help="If set, skip actual API calls and return dummy JSON for testing.")
    args = parser.parse_args()

    if not args.api_key:
        raise ValueError("API key must be provided via --api-key or OPENAI_API_KEY environment variable")

    main(args)
