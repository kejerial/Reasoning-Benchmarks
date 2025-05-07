"""
count_theories_with_total.py

This script counts the distribution of theory alignment labels (e.g., RCT, PMT, None)
from a JSONL file containing analysis responses. For each record, it selects the
majority-vote theory from the list of analysis responses. It outputs a summary
count of each label as well as the total number of records.

Usage:
    python count_theories_with_total.py input_file.jsonl output_file.txt --labels RCT PMT None

Arguments:
    input_file      Path to the input JSONL file containing analysis responses.
    output_file     Path to save the label distribution summary.
    --labels        (Optional) List of theory labels to count (default: RCT PMT None).
    --verbose       (Optional) Print progress information.
"""

import argparse
from pathlib import Path
import json
from collections import Counter

def majority_label(responses):
    """
    Given a list of analysis responses (each a dict containing 'aligned_theory'),
    return the majority aligned_theory or 'None' if tie or no responses.
    """
    counts = Counter()
    for r in responses:
        label = r.get("aligned_theory", "None")
        counts[label] += 1

    if not counts:
        return "None"
    most_common = counts.most_common()
    if len(most_common) == 1:
        return most_common[0][0]
    if most_common[0][1] > most_common[1][1]:
        return most_common[0][0]
    return "None"

def main():
    parser = argparse.ArgumentParser(
        description="Count distribution of majority-vote aligned_theory labels from JSONL."
    )
    parser.add_argument('input_file', type=Path, help="Path to input JSONL file.")
    parser.add_argument('output_file', type=Path, help="Path to output text file.")
    parser.add_argument('--labels', nargs='+', default=['RCT', 'PMT', 'None'],
                        help="List of theory labels to count (default: RCT PMT None).")
    parser.add_argument('--verbose', action='store_true', help="Print progress info.")
    args = parser.parse_args()

    distribution = Counter()
    total_records = 0

    with args.input_file.open('r', encoding='utf-8') as infile:
        for line_num, line in enumerate(infile, 1):
            try:
                rec = json.loads(line)
                label = majority_label(rec.get("analysis_responses", []))
                distribution[label] += 1
            except json.JSONDecodeError:
                if args.verbose:
                    print(f"⚠️ Skipping malformed JSON at line {line_num}")
                continue
            total_records += 1
            if args.verbose and line_num % 100 == 0:
                print(f"Processed {line_num} lines...")

    with args.output_file.open('w', encoding='utf-8') as fout:
        fout.write("Distribution of aligned_theory labels:\n")
        for label in args.labels:
            fout.write(f"{label}: {distribution[label]}\n")
        fout.write(f"Total: {total_records}\n")

    print(f"✅ Distribution written to {args.output_file.resolve()}")

if __name__ == "__main__":
    main()
