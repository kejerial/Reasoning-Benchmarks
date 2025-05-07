"""
sample_mini_1.4k.py

This script samples a 1,400-example subset ("mini_1.4k") from the AM-DeepSeek-R1-Distilled-1.4M dataset,
ensuring proportional representation across different dataset sources.

Key features:
- Performs stratified sampling according to a predefined distribution of parent sources.
- Uses reservoir sampling to process large input JSONL files in streaming fashion.
- Applies filters to exclude examples containing:
    1. Missing reference answers
    2. Code/test-case fields
    3. Non-ASCII characters (e.g., Chinese)

Input files:
    0.9M.jsonl
    0.5M.jsonl

Output:
    mini_1.4k.jsonl — sampled JSONL file with exactly 1,400 records distributed proportionally.
"""

import json
import random
import re
from pathlib import Path
from tqdm import tqdm

# 1) Configuration

counts = {
    "natural_reasoning":      319085,
    "InfinityInstruct":       306675,
    "KodCode":                210838,
    "Dolphin-R1":              63921,
    "openR1Math_extended":     63290,
    "NuminaMath_1.5":          62446,
    "openR1Math_default":      62239,
    "codeio":                  55176,
    "GeneralThought-Feb25":    50600,
    "openThoughts":            34620,
    "OpenCoder":               22249,
    "data_ablation_full59K":   14155,
    "MetaMathQA":              14083,
    "Other":                 120623,
}

parent_map = {
    # primary mappings
    "natural_reasoning":     "natural_reasoning",
    "InfinityInstruct":      "InfinityInstruct",
    "KodCode":               "KodCode",
    "Dolphin-R1":            "Dolphin-R1",
    "dolphin_R1_other":      "Dolphin-R1",
    "openR1Math_extended":   "openR1Math_extended",
    "openR1Math_default":    "openR1Math_default",
    "NuminaMath_1.5":        "NuminaMath_1.5",
    "MATH_numina":           "NuminaMath_1.5",
    "MATH-lighteval":        "NuminaMath_1.5",
    "GeneralThought-Feb25":  "GeneralThought-Feb25",
    "openThoughts":          "openThoughts",
    "openThoughts_other":    "openThoughts",
    "OpenCoder":             "OpenCoder",
    "OpenCoderStage2":       "OpenCoder",
    "codeio":                "codeio",
    "data_ablation_full59K": "data_ablation_full59K",
    "MetaMathQA":            "MetaMathQA",
    "MATH_metamathQA":       "MetaMathQA",
    # everything else → Other
    "Bespoke17k":    "Other",
    "Omni-MATH":     "Other",
    "PRIME":         "Other",
    "prime":         "Other",
    "aime":          "Other",
    "evol-en":       "Other",
    "evol-zh":       "Other",
    "limo":          "Other",
    "open_orca":     "Other",
    "s1K-1.1":       "Other",
}

total_population = sum(counts.values())
n = 1400  # target sample size

# compute proportional quotas
sample_sizes = {
    parent: int(round(n * cnt / total_population))
    for parent, cnt in counts.items()
}
# adjust to exactly n
delta = n - sum(sample_sizes.values())
if delta > 0:
    for parent in sorted(sample_sizes, key=lambda s: counts[s], reverse=True)[:delta]:
        sample_sizes[parent] += 1
elif delta < 0:
    for parent in sorted(sample_sizes, key=lambda s: counts[s], reverse=True)[: -delta]:
        sample_sizes[parent] -= 1

# prepare reservoirs & counters
reservoirs = {parent: [] for parent in counts}
counters   = {parent: 0  for parent in counts}

# regex to detect non-ASCII (e.g. Chinese)
non_ascii = re.compile(r'[^\x00-\x7F]')

# fallback structures
all_filtered = []
selected_set = set()

def reservoir_sample_file(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in tqdm(f, desc=f"Sampling {path.name}", unit="lines"):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            msgs = rec.get("messages", [])
            if not msgs:
                continue
            info = msgs[0].get("info", {})

            # 1) must have a reference answer
            if not info.get("reference_answer"):
                continue

            # 2) skip code problems
            if info.get("test_case") is not None:
                continue

            # 3) skip any non-ASCII content
            text = " ".join(m.get("content", "") for m in msgs)
            if non_ascii.search(text):
                continue

            # map raw source to parent bucket
            raw_src = info.get("source")
            parent = parent_map.get(raw_src, raw_src)
            if parent not in sample_sizes:
                continue

            # collect for fallback
            all_filtered.append(line)

            # reservoir sampling
            c = counters[parent] + 1
            counters[parent] = c
            k = sample_sizes[parent]

            if c <= k:
                reservoirs[parent].append(line)
                selected_set.add(line)
            else:
                j = random.randrange(c)
                if j < k:
                    old = reservoirs[parent][j]
                    selected_set.discard(old)
                    reservoirs[parent][j] = line
                    selected_set.add(line)

# process both shards
reservoir_sample_file(Path("0.9M.jsonl"))
reservoir_sample_file(Path("0.5M.jsonl"))

# fallback fill
total_selected = sum(len(v) for v in reservoirs.values())
missing = n - total_selected
if missing > 0:
    pool = [ln for ln in all_filtered if ln not in selected_set]
    extra = random.sample(pool, min(missing, len(pool)))
else:
    extra = []

# write out final sample
out_path = Path("mini_1.4k.jsonl")
with out_path.open("w", encoding="utf-8") as out:
    for parent in counts:
        for ln in reservoirs[parent]:
            out.write(ln)
    for ln in extra:
        out.write(ln)

total_sampled = sum(len(v) for v in reservoirs.values()) + len(extra)
print(f"\nDone - wrote {total_sampled} records to {out_path}")