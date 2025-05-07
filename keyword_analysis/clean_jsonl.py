"""
clean_jsonl.py

This script processes a JSON Lines (JSONL) file by removing all spaces
that are outside of string literals (i.e., spaces that are not inside
quoted strings). This is useful for minimizing JSONL files without
altering the contents of string fields. This script was originally developed for research reproducibility to
clean JSONL files used in large language model experiments.

Usage:
    python clean_jsonl.py input_file.jsonl output_file.jsonl [--verbose]

Arguments:
    input_file      Path to the input JSONL file.
    output_file     Path to save the cleaned JSONL file.
    --verbose       (Optional) Print progress information for each line processed.

Example Usage:
    python clean_jsonl.py mini_1.4k_deepseek-r1.jsonl cleaned_deepseek-r1.jsonl --verbose
"""

import argparse
import json
import re
from pathlib import Path

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

def process_jsonl_file(input_file: Path, output_file: Path, verbose: bool = False):
    if not input_file.exists():
        print(f"Error: Input file {input_file} does not exist.")
        return

    with input_file.open('r', encoding='utf-8') as infile, output_file.open('w', encoding='utf-8') as outfile:
        for line_num, line in enumerate(infile, 1):
            clean_line = remove_spaces_outside_strings(line.rstrip('\n'))
            outfile.write(clean_line + '\n')
            if verbose:
                print(f"Processed line {line_num}")

    print(f"Finished writing cleaned output to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Clean JSONL file by removing spaces outside string literals.")
    parser.add_argument('input_file', type=Path, help="Path to input JSONL file.")
    parser.add_argument('output_file', type=Path, help="Path to output cleaned JSONL file.")
    parser.add_argument('--verbose', action='store_true', help="Print progress for each line.")
    args = parser.parse_args()

    process_jsonl_file(args.input_file, args.output_file, args.verbose)

if __name__ == '__main__':
    main()
