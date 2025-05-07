#!/usr/bin/env python
import json
from pathlib import Path

files = [Path("0.9M.jsonl"), Path("0.5M.jsonl")]
sources = set()

for fn in files:
    print(f"Scanning {fn.name}…")
    with fn.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                # safely dig out 'source'
                msgs = rec.get("messages", [])
                if not msgs: 
                    continue
                info = msgs[0].get("info", {})
                src = info.get("source")
                if src is None:
                    #print(f"Warning: no source for {rec}")
                    continue      # skip null or missing sources
                sources.add(src)
            except json.JSONDecodeError:
                continue

print("\nFound the following unique instruction‑source names:")
for s in sorted(sources):
    print(" ", repr(s))
