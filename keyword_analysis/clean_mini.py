import json
from pathlib import Path

inp = Path("mini_1.4k.jsonl")
out = Path("clean_mini_1.4k.jsonl")

with inp.open("r", encoding="utf-8") as f_in, \
     out.open("w", encoding="utf-8") as f_out:
    for raw in f_in:
        raw = raw.strip()
        if not raw:
            continue
        # parse to ensure it's valid
        obj = json.loads(raw)
        # write back as one line
        f_out.write(json.dumps(obj, ensure_ascii=False))
        f_out.write("\n")

print(f"Wrote cleaned file with {sum(1 for _ in out.open())} lines to {out}")
