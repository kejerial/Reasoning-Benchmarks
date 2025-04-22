import os
import time
import json
import pandas as pd
import logging
from typing import Dict, List, Any
import openai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Load OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    logging.error("OPENAI_API_KEY environment variable not set.")
    exit(1)

def analyze_snippet(snippet: str) -> Dict[str, Any]:
    """
    Calls the LLM to identify phrases aligning with Representational Change Theory
    and Progress Monitoring Theory. Returns a dict with lists and counts.
    """
    system_prompt = '''
        You are an expert in cognitive psychology.  
        Given a reasoning trace from an LLM, identify and extract all phrases that align with  
        1) Representational Change Theory (e.g., segment relocation, attribute re-encoding, problem restructuring) example: “Let me restructure the problem: instead of adding the numbers directly, I’ll rearrange the segments on the display.”  
        2) Progress Monitoring Theory (e.g., intermediate checks, solution evaluation, monitoring steps) example: “At this point, I’ve verified each partial step; let me evaluate whether the overall solution satisfies the conditions.”  
        Respond in JSON with keys: 
        - representational_change_phrases: list of strings  
        - progress_monitoring_phrases: list of strings  
        - counts: { 'representational_change': int, 'progress_monitoring': int }"
        The phrases should be verbatim from the reasoning trace.
    '''
    user_prompt = f"Here is the reasoning trace:\n{snippet}"

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ],
            temperature=0.0,
        )
        content = resp.choices[0].message.content.strip()
        data = json.loads(content)
        return data
    except Exception as e:
        logging.error(f"Error during LLM call: {e}")
        return {
            "representational_change_phrases": [],
            "progress_monitoring_phrases": [],
            "counts": {"representational_change": 0, "progress_monitoring": 0}
        }


def main(input_csv: str, output_csv: str, delay: float = 1.0) -> None:
    # Read input
    df = pd.read_csv(input_csv)
    results: List[Dict[str, Any]] = []

    total = len(df)
    logging.info(f"Processing {total} rows from {input_csv}")

    for idx, row in df.iterrows():
        snippet = row.get("model_reasoning_snippet", "")
        if pd.isna(snippet) or not snippet.strip():
            data = {"representational_change_phrases": [], "progress_monitoring_phrases": [], "counts": {"representational_change": 0, "progress_monitoring": 0}}
        else:
            data = analyze_snippet(snippet)

        record: Dict[str, Any] = {
            "checkpoint": row.get("checkpoint"),
            "training_step": row.get("training_step"),
            "puzzle_id": row.get("puzzle_id"),
            "equation": row.get("equation"),
            "model_final_answer": row.get("model_final_answer"),
            "model_correct": row.get("model_correct"),
            "ground_truth_answer": row.get("ground_truth_answer"),
            "ground_truth_reasoning": row.get("ground_truth_reasoning"),
            "representational_change_phrases": data.get("representational_change_phrases"),
            "progress_monitoring_phrases": data.get("progress_monitoring_phrases"),
            "representational_change_count": data.get("counts", {}).get("representational_change", 0),
            "progress_monitoring_count": data.get("counts", {}).get("progress_monitoring", 0),
        }
        results.append(record)

        logging.info(f"Row {idx+1}/{total} done: RCT={record['representational_change_count']}, PMT={record['progress_monitoring_count']}")
        time.sleep(delay)

    # Save results
    out_df = pd.DataFrame(results)
    out_df.to_csv(output_csv, index=False)
    logging.info(f"Analysis results saved to {output_csv}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze LLM reasoning traces for cognitive theory phrases.")
    parser.add_argument("--input", required=True, help="Path to input CSV file.")
    parser.add_argument("--output", required=True, help="Path to output CSV file.")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between LLM calls in seconds.")
    args = parser.parse_args()

    main(args.input, args.output, args.delay)
