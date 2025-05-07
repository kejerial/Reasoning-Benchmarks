#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

# ─── Config ────────────────────────────────────────────────────────────────
JSONL_PATH = Path("mini_1.4k_deepseek-v3-base:free.jsonl")

def find_duplicate_questions():
    counts = Counter()
    if not JSONL_PATH.exists():
        print(f"File not found: {JSONL_PATH}")
        return

    with JSONL_PATH.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Extract the first user message
            msgs = obj.get("messages", [])
            if not msgs or not isinstance(msgs[0], dict):
                continue
            q = msgs[0].get("content", "").strip()
            if q:
                counts[q] += 1

    # Report duplicates
    print("Duplicate user questions (count > 1):\n")
    for question, cnt in counts.items():
        if cnt > 1:
            print(f"[{cnt}×] {question}\n")

if __name__ == "__main__":
    find_duplicate_questions()
