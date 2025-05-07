"""
Analyze each example in the cleaned 1.4K mini-corpus with GPT-4o.

For every JSONL record (problem, model response, and reference answer), dispatch
NUM_REPEATS API calls to evaluate correctness, theory alignment (RCT/PMT/None),
and reasoning characteristics. Skip any examples where the assistant response
is empty, contains no alphabetic letters, or is detected as non-English.
Run in parallel across multiple worker processes, show a live progress bar,
and write each JSON judgment immediately to the output file to avoid data loss.

This version strips out invalid control characters before JSON parsing.
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

# Ensure deterministic language detection
DetectorFactory.seed = 0

# ─── Configuration ─────────────────────────────────────────────────────────
API_KEY      = "OPENAI_KEY_REDACTED"
MODEL_NAME   = "gpt-4o"
INPUT_JSON   = Path("cleaned_deepseek-v3-base.jsonl")
OUTPUT_JSONL = Path("outputs_1.4k_deepseek-v3-base.jsonl")
NUM_WORKERS  = 3
NUM_REPEATS  = 5

PROMPT_SYSTEM = '''
You are an expert in cognitive science and reasoning analysis.

Given a reasoning problem, a model's generated response, and the ground-truth
answer, evaluate the following:

Return a JSON object in the following format:
{
  "correct": true | false,
  "aligned_theory": "RCT" | "PMT" | "None",
  "reasoning_characteristics": ["...","..."]
}
Only respond with the JSON object. Note -- it can be an incorrect response and aligned with RCT / PMT attempts. Only use None as a last resort.
'''

# ─── Single global logging setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)

# ─── Utility: remove control chars ──────────────────────────────────────────
CONTROL_RE = re.compile(r'[\x00-\x1F\x7F]')
def strip_control_chars(line: str) -> str:
    return CONTROL_RE.sub('', line)

# ─── Utility: load already‐done problems ────────────────────────────────────
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

# ─── Worker initializer to give each process its own client ────────────────
def init_client():
    global client
    client = OpenAI(api_key=API_KEY)

# ─── Single‐shot API call ───────────────────────────────────────────────────
def query_once(problem, model_out, ground):
    user_prompt = f"""Problem:
{problem}

Model Response:
{model_out}

Ground Truth Answer:
{ground}
"""
    messages = [
        {"role": "system", "content": PROMPT_SYSTEM},
        {"role": "user",   "content": user_prompt}
    ]
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0
    )
    return resp.choices[0].message.content.strip()

# ─── Clean json outputs ────────────────────────────────────────────────────
def clean_json_block(txt):
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", txt.strip())

# ─── Process one example (NUM_REPEATS calls) ───────────────────────────────
def process_example(ex):
    analyses = []
    for i in range(NUM_REPEATS):
        try:
            txt = query_once(ex["problem"], ex["model_out"], ex["ground"])
        except Exception as e:
            logging.warning(f"[{i+1}] API error: {e}")
            time.sleep(2)
            continue

        if not txt or not txt.strip():
            logging.warning(f"[{i+1}] Empty response, skipping")
            time.sleep(2)
            continue

        raw = clean_json_block(txt)
        try:
            parsed = json.loads(raw)
        except JSONDecodeError:
            logging.warning(f"[{i+1}] Invalid JSON after stripping fences:\n{repr(txt)}")
            time.sleep(2)
            continue

        analyses.append(parsed)
        time.sleep(2.5)

    return {
        "problem":            ex["problem"],
        "model_response":     ex["model_out"],
        "had_model_output":   ex["had_model_output"],
        "ground_truth":       ex["ground"],
        "analysis_responses": analyses
    }

# ─── Main entrypoint ───────────────────────────────────────────────────────
def main():
    existing = load_existing_problems(OUTPUT_JSONL)
    logging.info(f"Skipping {len(existing)} already-processed examples.")

    examples = []
    with INPUT_JSON.open("r", encoding="utf-8", errors="ignore") as f:
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
                "problem":           problem,
                "model_out":         model_out,
                "ground":            ground,
                "had_model_output":  bool(model_out)
            })

    logging.info(f"Will process {len(examples)} new examples.")

    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    out_f = OUTPUT_JSONL.open("a", encoding="utf-8")

    with ProcessPoolExecutor(max_workers=NUM_WORKERS, initializer=init_client) as pool:
        futures = [pool.submit(process_example, ex) for ex in examples]
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Analyzing", unit="ex"):
            rec = fut.result()
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out_f.flush()

    out_f.close()
    logging.info("All done.")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
