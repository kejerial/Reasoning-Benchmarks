#!/usr/bin/env python
import json
import re
import time
from pathlib import Path
import requests
from json import JSONDecodeError
from tqdm import tqdm

# Models: deepseek/deepseek-r1-zero:free, deepseek/deepseek-v3-base:free
MODEL       = "deepseek/deepseek-v3-base:free"
MODEL_NAME  = MODEL.split(":")[0]
TEMPLATE_FILE  = Path("mini_1.4k_template.jsonl")
OUTPUT_FILE = Path(f"cleaned_{MODEL_NAME.split('/')[1]}.jsonl")
API_URL     = "https://openrouter.ai/api/v1/chat/completions"
API_KEY     = "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"

SYSTEM_PROMPT = (
    "You are a helpful AI Assistant that provides well‑reasoned but concise answers.\n"
    "Think briefly in an internal monologue, then answer.\n"
    "Respond in this format:\n\n"
    "Problem: {problem}\n\n"
    "<think>\n"
    "</think>\n\n"
    "<answer>\n"
    "</answer>\n"
)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# ─── REGEX SETUP ──────────────────────────────────────────────────────────────
# Matches <think>...</think> where inside has at least one alphabet letter
THINK_RE  = re.compile(r"<think>\s*([A-Za-z].*?)\s*</think>", re.S)
# Matches <answer>...</answer> where inside has at least one alphabet letter
ANSWER_RE = re.compile(r"<answer>\s*([A-Za-z].*?)\s*</answer>", re.S)

def extract_think_answer(text: str) -> tuple[str, str]:
    """
    Extracts the <think> and <answer> contents from the model's reply.
    
    Input:
    - text (str): full string response from the model
    
    Output:
    - tuple: (think_content, answer_content)
      If missing, returns empty strings.
    """
    think  = THINK_RE.search(text)
    answer = ANSWER_RE.search(text)
    return (
        think.group(1).strip()  if think  else "",
        answer.group(1).strip() if answer else "",
    )

def call_model(problem: str) -> str:
    """
    Sends a POST request to the OpenRouter API with the system prompt and question.
    
    Input:
    - problem (str): the user question to send
    
    Output:
    - str: the raw reply content from the model, stripped of leading/trailing whitespace
    """
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(problem=problem)},
            {"role": "user",   "content": problem},
        ],
        "max_tokens": 1200,
        "temperature": 0.0,
    }
    session = requests.Session()
    r = session.post(API_URL, headers=HEADERS, json=payload, timeout=(10, 45))
    r.raise_for_status()
    data = r.json()
    content = (
        data["choices"][0].get("message", {}).get("content") 
        or data["choices"][0].get("text", "")
    )
    return content.strip()

def load_existing_questions(path: Path) -> set[str]:
    """
    Reads an existing .jsonl file and extracts all unique questions.
    
    Input:
    - path (Path): the path to the existing output JSONL file
    
    Output:
    - set[str]: set of all question strings found in obj["messages"][0]["content"]
    """
    seen = set()
    if not path.exists():
        return seen
    with path.open(encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                obj = json.loads(line)
                messages = obj.get("messages", [])
                if messages and messages[0].get("role") == "user":
                    content = messages[0].get("content", "").strip()
                    if content:
                        #print(f"[EXISTING][Line {line_num}] {content[:60]}")
                        seen.add(content)
            except JSONDecodeError as e:
                print(f"[WARN][Line {line_num}] Skipping malformed JSON with error: {e}")
                continue
    return seen

def remove_spaces_outside_strings(line):
    quoted_positions = []
    for match in re.finditer(r'"(?:\\.|[^"\\])*"', line):
        quoted_positions.append((match.start(), match.end()))

    result = []
    i = 0
    while i < len(line):
        in_quoted = False
        for start, end in quoted_positions:
            if i >= start and i < end:
                in_quoted = True
                result.append(line[i])
                i += 1
                break
        if not in_quoted:
            if line[i] != ' ':
                result.append(line[i])
            i += 1
    return ''.join(result)

def save_template_file(updated_objs):
    with TEMPLATE_FILE.open("w", encoding="utf-8") as f:
        for obj in updated_objs:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    print(f"[UPDATE] TEMPLATE_FILE updated with {len(updated_objs)} remaining questions.")


# ─── MAIN ───────────────────────────────────────────────────────────────

def main():
    """
    Main function:
    - Loads all existing answered questions.
    - Loads all template questions.
    - For each unseen question:
        → repeatedly queries the model until valid <think> and <answer> are found.
        → writes the completed record to the output JSONL file.
    """
    seen_questions = load_existing_questions(OUTPUT_FILE)
    print(f"Loaded {len(seen_questions)} already answered questions.")

    template_lines = []
    with TEMPLATE_FILE.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if line.strip():
                try: 
                    obj = json.loads(line)
                    question = obj.get("messages", [{}])[0].get("content", "").strip()
                    #print(f"[Line {i}] Question: {repr(question)}")
                    template_lines.append(obj)
                except json.JSONDecodeError as e:
                    print(f"[WARN] Skipping malformed line {i}: {e}")

    new_records = [
      obj for obj in template_lines
      if obj.get("messages", [{}])[0].get("content", "").strip() not in seen_questions 
    ]


    print(f"{len(new_records)} new questions to process.")

    processed_objs = []
    failed_objs = []

    with OUTPUT_FILE.open("a", encoding="utf-8") as fout:
        for obj in tqdm(new_records, desc="Processing", unit="question"):
            problem = obj["messages"][0]["content"].strip()
            print(f"[QUERY] Trying question: {problem[:80]}")

            for attempt in range(10):
                try:
                    reply = call_model(problem)
                    think, answer = extract_think_answer(reply)
                    if think and answer:
                        print(f"[SUCCESS] Question: {problem[:40]}")
                        print(f"          Think: {think[:40]}")
                        print(f"          Answer: {answer[:40]}")
                        break
                except Exception as e:
                    print(f"[ERROR] Query failed on attempt {attempt+1} for: {problem[:60]}")
                    print("↪", e)
                    time.sleep(2)
            else:
                print(f"[WARN] Failed 10 times, removing from TEMPLATE_FILE: {problem[:60]}")
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
            seen_questions.add(problem.strip())
            processed_objs.append(obj)
            time.sleep(1.0)  # polite pacing

    # Rewrite TEMPLATE_FILE excluding the failed ones
    failed_questions = {
       obj["messages"][0].get("content", "").strip() for obj in failed_objs
    }
    updated_template = [
        obj for obj in template_lines
        if obj["messages"][0].get("content", "").strip() not in failed_questions
    ]
    save_template_file(updated_template)

    with open("failed_questions.log", "w", encoding="utf-8") as log:
        for obj in failed_objs:
            log.write(obj["messages"][0]["content"].strip() + "\n")


    print(f"✓ Finished. Appended results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
