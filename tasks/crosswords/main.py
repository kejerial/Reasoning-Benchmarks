import os
import sys
import json
import subprocess
from difflib import SequenceMatcher
from tqdm import tqdm
import matplotlib.pyplot as plt
import numpy as np

sys.path.append(os.path.join(os.path.dirname(__file__), "decrypt"))
from decrypt.decrypt.scrape_parse import load_guardian_splits

def remote_infer(clue, remote_host="user@remote", script_path="~/decrypt_infer/model_infer.py"):
    clue = clue.replace('"', '\\"')
    cmd = f'ssh {remote_host} \'python3 {script_path} --clue "{clue}"\''
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode("utf-8").strip()

def accuracy(preds, targets):
    return sum(p == t for p, t in zip(preds, targets)) / len(targets)

def avg_edit_distance(preds, targets):
    return sum(SequenceMatcher(None, p, t).ratio() for p, t in zip(preds, targets)) / len(targets)

def plot_metrics(preds, targets):
    edit_scores = [SequenceMatcher(None, p, t).ratio() for p, t in zip(preds, targets)]

    plt.figure(figsize=(12, 5))
    plt.subplot(1, 2, 1)
    plt.hist(edit_scores, bins=20, color='gray')
    plt.title("Edit Similarity Score Distribution")
    plt.xlabel("Edit similarity")
    plt.ylabel("Count")

    plt.subplot(1, 2, 2)
    plt.bar(["Accuracy"], [accuracy(preds, targets)])
    plt.title("Accuracy")
    plt.ylim(0, 1)

    plt.tight_layout()
    plt.savefig("performance_metrics.png")
    plt.show()

def analyze_lengths(clues, preds, targets):
    clue_lens = [len(c.split()) for c in clues]
    pred_lens = [len(p.split()) for p in preds]
    sol_lens = [len(t.split()) for t in targets]

    plt.figure(figsize=(8, 6))
    plt.hist(clue_lens, bins=15, alpha=0.5, label="Clue Length")
    plt.hist(pred_lens, bins=15, alpha=0.5, label="Prediction Length")
    plt.hist(sol_lens, bins=15, alpha=0.5, label="Solution Length")
    plt.legend()
    plt.title("Length Distributions")
    plt.xlabel("Number of Words")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.savefig("length_distributions.png")
    plt.show()

def length_stats(preds, targets):
    correct_lens = [len(p) for p, t in zip(preds, targets) if p == t]
    incorrect_lens = [len(p) for p, t in zip(preds, targets) if p != t]
    print(f"Avg len (correct): {np.mean(correct_lens):.2f}")
    print(f"Avg len (incorrect): {np.mean(incorrect_lens):.2f}")

def run_inference(remote_host, script_path, split='test', max_samples=100):
    _, _, (train, val, test) = load_guardian_splits()
    dataset = {'train': train, 'val': val, 'test': test}[split][:max_samples]

    predictions = []
    targets = []
    clues = []

    print(f"Running inference on {split} set (n={len(dataset)})")
    for clue in tqdm(dataset):
        clue_text = clue.surface
        sol = clue.solution
        try:
            pred = remote_infer(clue_text, remote_host, script_path)
        except Exception as e:
            pred = "[ERROR]"
        predictions.append(pred)
        targets.append(sol)
        clues.append(clue_text)

    return clues, predictions, targets

def save_results(clues, preds, targets, out_path="decrypt_results.json"):
    results = [
        {"clue": c, "prediction": p, "target": t}
        for c, p, t in zip(clues, preds, targets)
    ]
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    remote_host = "user@slurm-node"  # Update with SLURM login node
    script_path = "~/decrypt_infer/model_infer.py"  # Remote model script

    clues, preds, targets = run_inference(remote_host, script_path, split='test', max_samples=100)

    acc = accuracy(preds, targets)
    ed = avg_edit_distance(preds, targets)

    print(f"\nAccuracy: {acc:.3f}")
    print(f"Avg Edit Similarity: {ed:.3f}")
    length_stats(preds, targets)

    save_results(clues, preds, targets)
    plot_metrics(preds, targets)
    analyze_lengths(clues, preds, targets)
