"""
create_template_json.py

This script processes a JSON Lines (JSONL) file and outputs a JSON array (JSON)
template by clearing specific fields in the "assistant" messages for reproducibility.
In each record's "messages" list:
- It empties the 'content' field of messages with role "assistant".
- If a message with role "assistant" contains an "info" dictionary, it clears
  the 'think_content' and 'answer_content' fields inside "info".

Usage:
    python create_template_json.py input_file.jsonl output_file.json [--verbose]

Arguments:
    input_file      Path to the input JSONL file.
    output_file     Path to save the output JSON file.
    --verbose       (Optional) Print information about each processed record.
"""

import argparse
import json
from pathlib import Path

def process_jsonl_to_template(input_file: Path, output_file: Path, verbose: bool = False):
    if not input_file.exists():
        print(f"Error: Input file {input_file} does not exist.")
        return

    records = []
    with input_file.open('r', encoding='utf-8') as infile:
        for line_num, line in enumerate(infile, 1):
            rec = json.loads(line)
            for msg in rec.get("messages", []):
                if msg.get("role") == "assistant":
                    msg["content"] = ""
                    if "info" in msg:
                        msg["info"]["think_content"] = ""
                        msg["info"]["answer_content"] = ""
            records.append(rec)
            if verbose:
                print(f"Processed record {line_num}")

    output_file.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
    print(f"Wrote template to {output_file.resolve()}")

def main():
    parser = argparse.ArgumentParser(
        description="Create a template JSON file by clearing assistant responses from a JSONL input."
    )
    parser.add_argument('input_file', type=Path, help="Path to input JSONL file.")
    parser.add_argument('output_file', type=Path, help="Path to output JSON file.")
    parser.add_argument('--verbose', action='store_true', help="Print progress for each record.")
    args = parser.parse_args()

    process_jsonl_to_template(args.input_file, args.output_file, args.verbose)

if __name__ == "__main__":
    main()
