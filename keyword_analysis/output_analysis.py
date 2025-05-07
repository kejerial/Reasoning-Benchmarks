# count_theories_with_total.py

from pathlib import Path
import json
from collections import Counter

# Hard-coded file paths
INPUT_FILE = Path("outputs_1.4k.jsonl")
OUTPUT_FILE = Path("distribution.txt")

def majority_label(responses):
    """
    Given a list of analysis responses (each a dict containing 'aligned_theory'),
    return the majority aligned_theory or 'None' if there's a tie or no responses.
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
    distribution = Counter()
    total_records = 0

    # Read every JSONL record
    for line in INPUT_FILE.read_text(encoding="utf-8").splitlines():
        total_records += 1
        rec = json.loads(line)
        label = majority_label(rec.get("analysis_responses", []))
        distribution[label] += 1

    # Write the results to a text file
    with OUTPUT_FILE.open("w", encoding="utf-8") as fout:
        fout.write("Distribution of aligned_theory labels:\n")
        for label in ["RCT", "PMT", "None"]:
            fout.write(f"{label}: {distribution[label]}\n")
        fout.write(f"Total: {total_records}\n")

if __name__ == "__main__":
    main()
