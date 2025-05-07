import json
from pathlib import Path

# Input and output file paths
INPUT_FILE = Path("mini_1.4k.jsonl")
OUTPUT_FILE = Path("mini_1.4k_template.json")

def main():
    records = []
    for line in INPUT_FILE.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        for msg in rec.get("messages", []):
            if msg.get("role") == "assistant":
                msg["content"] = ""
            if msg.get("role") == "assistant" and "info" in msg:
                msg["info"]["think_content"] = ""
                msg["info"]["answer_content"] = ""
        records.append(rec)
    
    OUTPUT_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"Wrote template to {OUTPUT_FILE.resolve()}")

if __name__ == "__main__":
    main()
