import json
import re
from pathlib import Path

# ─── HARD CODED FILE PATHS ──────────────────────────────────────────────
INPUT_FILE = Path('mini_1.4k_deepseek-r1.jsonl')
OUTPUT_FILE = Path('cleaned_deepseek-r1.jsonl')

def remove_spaces_outside_strings(line):
    quoted_positions = []
    for match in re.finditer(r'"(?:\\.|[^"\\])*"', line):
        quoted_positions.append((match.start(), match.end()))

    result = []
    i = 0
    while i < len(line):
        # Check if current position is inside a quoted section
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

def process_jsonl_file():
    if not INPUT_FILE.exists():
        print(f"Input file {INPUT_FILE} does not exist.")
        return

    with INPUT_FILE.open('r', encoding='utf-8') as infile, OUTPUT_FILE.open('w', encoding='utf-8') as outfile:
        for line_num, line in enumerate(infile, 1):
            clean_line = remove_spaces_outside_strings(line.rstrip('\n'))
            outfile.write(clean_line + '\n')
            print(f"Processed line {line_num}")

    print(f"Finished writing cleaned output to {OUTPUT_FILE}")

# Run the processing
process_jsonl_file()