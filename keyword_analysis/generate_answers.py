"""
generate_answers.py

This script queries a specified OpenRouter API model to fill in <think> and <answer> fields
for a set of input questions provided in a JSONL template. For each input question:
1. Sends a prompt to the model (with system instructions).
2. Extracts <think> and <answer> tags from the reply.
3. Writes a completed JSON object to an output JSONL file.
4. Updates the template file by removing successfully answered questions.

Usage:
    python generate_answers.py --model deepseek/deepseek-r1-zero:free --template input_template.jsonl --output output_file.jsonl --api-key sk-XXX [--verbose]

Arguments:
    --model        Model identifier (as accepted by OpenRouter API), e.g., deepseek/deepseek-r1-zero:free
    --template     Path to input template JSONL file.
    --output       Path to output JSONL file to append results.
    --api-key      API key for OpenRouter API.
    --verbose      (Optional) Print progress information.
"""

import argparse
import json
import re
import time
from pathlib import Path
import requests
from json import JSONDecodeError
from tqdm import tqdm

# ─── REGEX SETUP ──────────────────────────────────────────────────────────────
THINK_RE  = re.compile(r"<think>\s*([A-Za-z].*?)\s*</think>", re.S)
ANSWER_RE = re.compile(r"<answer>\s*([A-Za-z].*?)\s*</answer>", re.S)

SYSTEM_PROMPT_TEMPLATE = (
    "You are a helpful AI Assistant that provides well‑reasoned but concise answers.\n"
    "Think briefly in an internal monologue, then answer.\n"
    "Respond in this format:\n\n"
    "Problem: {problem}\n\n"
    "<think>\n"
    "</think>\n\n"
    "<answer>\n"
    "</answer>\n"
)

API_URL = "https://openrouter.ai/api/v1/chat/completions"

def extract_think_answer(text: str) -> tuple[str, str]:
    think  = THINK_RE.search(text)
    answer = ANSWER_RE.search(text)
    return (
        think.group(1).strip()  if think  else "",
        answer.group(1).strip() if answer else "",
    )

def call_model(problem: str, model: str, api_key: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(problem=problem)},
            {"role": "user",   "content": problem},
        ],
        "max_tokens": 1200,
        "temperature": 0.0,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    session = requests.Session()
    r = session.post(API_URL, headers=headers, json=payload, timeout=(10, 45))
    r.raise_for_status()
    data = r.json()
    content = (
        data["choices"][0].get("message", {}).get("content")
        or data["choices"][0].get("text", "")
    )
    return content.strip()

def remove_spaces_outside_strings(line):
    quoted_positions = []
    for match in re.finditer(r'"(?:\\.|[^"\\])*"', line):
        quoted_positions.append((match.start(), match.end()))
    result = []
    i = 0
    while i < len(line):
        in_quoted = False
        for start, end in quoted_positions:
            if start <= i < end:
                in_quoted = True
                result.append(line[i])
                i += 1
                break
        if not in_quoted:
            if line[i] != ' ':
                result.append(line[i])
            i += 1
    return ''.join(result)

def load_existing_questions(output_file: Path) -> set[str]:
    seen = set()
    if not output_file.exists():
        return seen
    with output_file.open(encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                obj = json.loads(line)
                messages = obj.get("messages", [])
                if messages and messages[0].get("role") == "user":
                    content = messages[0].get("content", "").strip()
                    if content:
                        seen.add(content)
            except JSONDecodeError as e:
                print(f"[WARN][Line {line_num}] Skipping malformed JSON: {e}")
    return seen

def save_template_file(template_file: Path, updated_objs):
    with template_file.open("w", encoding="utf-8") as f:
        for obj in updated_objs:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    print(f"[UPDATE] Updated template file with {len(updated_objs)} remaining questions.")

def main():
    parser = argparse.ArgumentParser(
        description="Query OpenRouter model to generate <think> and <answer> for template questions."
    )
    parser.add_argument('--model', type=str, required=True, help="OpenRouter model identifier.")
    parser.add_argument('--template', type=Path, required=True, help="Path to input template JSONL file.")
    parser.add_argument('--output', type=Path, required=True, help="Path to output JSONL file.")
    parser.add_argument('--api-key', type=str, required=True, help="API key for OpenRouter API.")
    parser.add_argument('--verbose', action='store_true', help="Print progress information.")
    args = parser.parse_args()

    seen_questions = load_existing_questions(args.output)
    if args.verbose:
        print(f"Loaded {len(seen_questions)} previously answered questions.")

    with args.template.open(encoding="utf-8") as f:
        template_lines = [json.loads(line) for line in f if line.strip()]

    new_records = [
        obj for obj in template_lines
        if obj.get("messages", [{}])[0].get("content", "").strip() not in seen_questions
    ]
    print(f"{len(new_records)} new questions to process.")

    processed_objs = []
    failed_objs = []

    with args.output.open("a", encoding="utf-8") as fout:
        for obj in tqdm(new_records, desc="Processing", unit="question"):
            problem = obj["messages"][0]["content"].strip()
            if args.verbose:
                print(f"[QUERY] {problem[:80]}")

            for attempt in range(10):
                try:
                    reply = call_model(problem, args.model, args.api_key)
                    think, answer = extract_think_answer(reply)
                    if think and answer:
                        if args.verbose:
                            print(f"[SUCCESS] Think: {think[:40]} | Answer: {answer[:40]}")
                        break
                except Exception as e:
                    print(f"[ERROR] Attempt {attempt+1} failed for: {problem[:60]}")
                    print("↪", e)
                    time.sleep(2)
            else:
                print(f"[WARN] Failed 10 attempts; skipping: {problem[:60]}")
                failed_objs.append(obj)
                continue

            if len(obj["messages"]) < 2:
                obj["messages"].append({"role": "assistant", "content": "", "info": {}})
            assistant_entry = obj["messages"][1]
            assistant_entry["content"] = reply
            assistant_entry["info"]["think_content"] = think
            assistant_entry["info"]["answer_content"] = answer

            json_line = json.dumps(obj, ensure_ascii=False)
            cleaned_line = remove_spaces_outside_strings(json_line)
            fout.write(cleaned_line + "\n")
            fout.flush()
            seen_questions.add(problem)
            processed_objs.append(obj)
            time.sleep(1.0)

    failed_questions = {obj["messages"][0].get("content", "").strip() for obj in failed_objs}
    updated_template = [
        obj for obj in template_lines
        if obj["messages"][0].get("content", "").strip() not in failed_questions
    ]
    save_template_file(args.template, updated_template)

    with open("failed_questions.log", "w", encoding="utf-8") as log:
        for obj in failed_objs:
            log.write(obj["messages"][0]["content"].strip() + "\n")

    print(f"✓ Finished. Results saved to {args.output}")

if __name__ == "__main__":
    main()