import os
import re
import json
import time
import glob
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
if not client.api_key:
    logging.error("OPENAI_API_KEY environment variable not set.")
    exit(1)

MODEL_NAME = "o4-mini-2025-04-16"
PROMPT_SYSTEM = '''
        You are an expert in cognitive psychology.  
        Given a reasoning trace from an LLM, identify and extract all phrases that align with  
        1) Representational Change Theory (e.g., segment relocation, attribute re-encoding, problem restructuring) example: “Let me restructure the problem: instead of adding the numbers directly, I’ll rearrange the segments on the display.”  
        2) Progress Monitoring Theory (e.g., intermediate checks, solution evaluation, monitoring steps) example: “At this point, I’ve verified each partial step; let me evaluate whether the overall solution satisfies the conditions.”  
        Respond in JSON with keys: 
        - representational_change_phrases: list of strings  
        - progress_monitoring_phrases: list of strings  
        - counts: { 'representational_change': int, 'progress_monitoring': int }
        The phrases should be verbatim from the reasoning trace.
    '''


def _to_bool(val: Any) -> Optional[int]:
    if pd.isna(val):
        return None
    if isinstance(val, bool):
        return int(val)
    s = str(val).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return 1
    if s in {"false", "0", "no", "n"}:
        return 0
    return None


def query(snippet: str) -> Dict[str, Any]:
    if not snippet.strip():
        return {"RCT_phrases": [], "PMT_phrases": [], "counts": {"RCT": 0, "PMT": 0}}

    messages = [
        {"role": "system", "content": PROMPT_SYSTEM},
        {"role": "user",   "content": f"Here is the reasoning trace:\n'''{snippet}'''"},
    ]
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
        )
        content = resp.choices[0].message.content.strip()
        data = json.loads(content)
        return {
            "RCT_phrases": data.get("representational_change_phrases", []),
            "PMT_phrases": data.get("progress_monitoring_phrases", []),
            "counts": {
                "RCT": data.get("counts", {}).get("representational_change", 0),
                "PMT": data.get("counts", {}).get("progress_monitoring", 0),
            },
        }
    except Exception as exc:
        logging.error("LLM call failed: %s", exc)
        return {"RCT_phrases": [], "PMT_phrases": [], "counts": {"RCT": 0, "PMT": 0}}


def find_sample_column(columns: List[str], checkpoint_id: str) -> Optional[str]:
    for col in columns:
        if checkpoint_id in col and "sample" in col:
            return col
    pattern = re.compile(rf"{checkpoint_id}.*sample", re.IGNORECASE)
    for col in columns:
        if pattern.search(col):
            return col
    return None


def parse_filename(fname: str) -> Tuple[str, int]:
    m = re.search(r"_([0-9a-f]{7})_(\d+)\.csv$", fname)
    if m:
        return m.group(1), int(m.group(2))
    m2 = re.search(r"_([0-9a-f]{7})\.csv$", fname)
    if m2:
        return m2.group(1), 0
    raise ValueError(f"Unexpected filename pattern: {fname}")


def problem_description(row: pd.Series, task: str) -> str:
    if task == "car_problems":
        return row.get("board", "")
    if task == "matchstick":
        return row.get("equation", "")
    if task == "crossword":
        return row.get("clue", "")
    return ""


def process_csv(
    file_path: str,
    task: str,
    training_type: str,
    delay: float = 0.5,
) -> List[Dict[str, Any]]:
    checkpoint_id, training_step = parse_filename(os.path.basename(file_path))
    df = pd.read_csv(file_path)
    sample_col = find_sample_column(df.columns.tolist(), checkpoint_id)
    if not sample_col:
        logging.warning("Sample column for checkpoint %s not found in %s", checkpoint_id, file_path)
        return []

    correct_col = next((c for c in ["model_correct", "correct", "is_correct"] if c in df.columns), None)
    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        snippet = str(row.get(sample_col, ""))
        analysis = query(snippet)
        records.append({
            "task": task,
            "training_type": training_type,
            "training_step": training_step,
            "checkpoint_id": checkpoint_id,
            "problem_description": problem_description(row, task),
            "is_correct": _to_bool(row.get(correct_col)) if correct_col else None,
            "rct_phrases": analysis["RCT_phrases"],
            "pmt_phrases": analysis["PMT_phrases"],
            "rct_count": analysis["counts"]["RCT"],
            "pmt_count": analysis["counts"]["PMT"],
        })
        time.sleep(delay)
    return records


def collect_all(
    base_dir: str = "Reasoning-Benchmarks/data",
    delay: float = 0.5,
    output_dir: str = "analysis_output",
) -> None:
    tasks = [("crossword","crossword"), ("car_problems","car_problems"), ("matchstick","matchstick")] 
    training_types = ["grpo","sft"]
    os.makedirs(output_dir, exist_ok=True)
    for task_dir, task_name in tasks:
        for training_type in training_types:
            pattern = os.path.join(base_dir,task_dir,training_type,"*.csv")
            files = sorted(glob.glob(pattern))
            logging.info("%s | %s : %d CSV files", task_name, training_type, len(files))
            all_records: List[Dict[str, Any]] = []
            for fp in files:
                logging.info("Processing %s", fp)
                all_records.extend(process_csv(fp, task_name, training_type, delay))
            out = os.path.join(output_dir,f"{task_name}_{training_type}_analysis.json")
            with open(out,"w",encoding="utf-8") as f:
                json.dump(all_records,f,ensure_ascii=False, indent=2)
            logging.info("Saved %d records -> %s",len(all_records),out)


def plot_trends(json_path: str, save_dir: str = "plots") -> None:
    import matplotlib.pyplot as plt
    os.makedirs(save_dir,exist_ok=True)
    with open(json_path,"r",encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        logging.warning("No data in %s",json_path)
        return
    df = pd.DataFrame(data)
    grouped = df.groupby("training_step").agg({"rct_count":"mean","pmt_count":"mean"}).sort_index()
    for col in ["rct_count","pmt_count"]:
        plt.figure();plt.plot(grouped.index,grouped[col])
        plt.title(f"{os.path.basename(json_path).replace('_analysis.json','')} — {col}")
        plt.xlabel("Training step");plt.ylabel("Mean count per puzzle")
        fn=os.path.join(save_dir,f"{os.path.basename(json_path).replace('.json','')}_{col}.png")
        plt.tight_layout();plt.savefig(fn,dpi=300);plt.close()
        logging.info("Saved plot -> %s",fn)
    df["total_phrase_count"]=df["rct_count"]+df["pmt_count"]
    df["rct_prop"]=df.apply(lambda r:r["rct_count"]/r["total_phrase_count"] if r["total_phrase_count"]>0 else 0,axis=1)
    df["pmt_prop"]=df.apply(lambda r:r["pmt_count"]/r["total_phrase_count"] if r["total_phrase_count"]>0 else 0,axis=1)
    prop = df.groupby("training_step").agg({"rct_prop":"mean","pmt_prop":"mean","is_correct":"mean"}).sort_index()
    plt.figure()
    plt.plot(prop.index,prop["rct_prop"],label="RCT proportion")
    plt.plot(prop.index,prop["pmt_prop"],label="PMT proportion")
    if "is_correct" in prop.columns: plt.plot(prop.index,prop["is_correct"],label="Accuracy")
    plt.title(os.path.basename(json_path).replace("_analysis.json","")+" — Proportions & Accuracy")
    plt.xlabel("Training step");plt.ylabel("Relative value");plt.legend();plt.tight_layout()
    fnm=os.path.join(save_dir,f"{os.path.basename(json_path).replace('.json','')}_proportions_accuracy.png")
    plt.savefig(fnm,dpi=300);plt.close();logging.info("Saved plot -> %s",fnm)

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description="Run multi‑task analysis and plotting.")
    parser.add_argument("action",choices=["run","plot"],help="run or plot")
    parser.add_argument("--base_dir",default="Reasoning-Benchmarks/data",help="Root dir of datasets.")
    parser.add_argument("--output_dir",default="analysis_output",help="Where to save JSONs/plots.")
    parser.add_argument("--delay",type=float,default=0.5,help="LLM call delay (s)." )
    args=parser.parse_args()
    if args.action=="run": collect_all(base_dir=args.base_dir,delay=args.delay,output_dir=args.output_dir)
    else:  
        for jp in glob.glob(os.path.join(args.output_dir,"*_analysis.json")): plot_trends(jp)
