import json
import argparse
from pathlib import Path
from typing import Dict
import subprocess

# Updated prompt template using the model's trained format.
PROMPT_TEMPLATE = """# Matchstick Puzzles

Prompt:
You are a helpful AI Assistant that provides well-reasoned and detailed responses.
You first think about the reasoning process as an internal monologue and then provide the user with the answer.
Respond in the following format:
<think>
[Your step-by-step reasoning with detailed considerations.]
</think>
<answer>
[Your final solution in a clear, concise format, including every move and the resulting equation.]
</answer>

This requires engaging in a comprehensive cycle of analysis, summarizing, exploration, reassessment, reflection, backtracing, and iteration to develop a well-considered thinking process.

You are to be given a "matchstick puzzle" where you need to identify how to rearrange matchsticks to convert a given numerical equation or expression into another.
The format of a digit's expression in matches depends on how many of 7 matchsticks are chosen (top, upper left, upper right, middle, lower left, lower right, bottom).

The key for each digit's matchstick representation is:
- 0: 6 matchsticks — segments: top, upper left, upper right, lower left, lower right, bottom.
- 1: 2 matchsticks — segments: upper right, lower right.
- 2: 5 matchsticks — segments: top, upper right, middle, lower left, bottom.
- 3: 5 matchsticks — segments: top, upper right, middle, lower right, bottom.
- 4: 4 matchsticks — segments: upper left, middle, upper right, lower right.
- 5: 5 matchsticks — segments: top, upper left, middle, lower right, bottom.
- 6: 6 matchsticks — segments: top, upper left, middle, lower left, lower right, bottom.
- 7: 3 matchsticks — segments: top, upper right, lower right.
- 8: 7 matchsticks — segments: top, upper left, upper right, middle, lower left, lower right, bottom.
- 9: 6 matchsticks — segments: top, upper left, upper right, middle, lower right, bottom.

The key for each operator's matchstick representation is:
- Minus (-): 1 matchstick.
- Plus (+): 2 matchsticks (one horizontal and one vertical).
- Multiplication (x): cannot be changed (if an equation has a multiplication sign, then do not change that operator).

Rules:
1. The only valid move is a transfer of matchsticks (i.e., you may move matchsticks as long as the total number remains the same and all digits/operators follow the above key).
2. The puzzle presents an initial equation built from these matchstick configurations.
3. Your task is to identify which matchstick to move (or remove and reattach) in order to create a valid equation.

Problem:
{equation}
Move exactly {number_of_moves} match stick to fix this equation.

Note: You may not change the equal sign.
"""

def query_model(prompt: str, model_name: str) -> str:
    process = subprocess.run(
        ["ssh", "user@slurm-cluster", f"python3 /path/to/{model_name}_interface.py"],
        input=prompt.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if process.returncode != 0:
        raise RuntimeError(f"Remote execution failed: {process.stderr.decode()}")
    return process.stdout.decode().strip()

def parse_response(response: str) -> Dict[str, str]:
    """
    Parse the model response that is expected to contain:
      - Internal monologue in between <think> and </think>
      - Final answer in between <answer> and </answer>
    """
    thought = ""
    answer = ""
    
    if "<think>" in response and "</think>" in response:
        thought = response.split("<think>")[1].split("</think>")[0].strip()
    
    if "<answer>" in response and "</answer>" in response:
        answer = response.split("<answer>")[1].split("</answer>")[0].strip()
    
    return {
        "reasoning": thought,
        "answer": answer
    }

def run_on_dataset(data_path: Path, model_name: str):
    with open(data_path, "r") as f:
        dataset = json.load(f)

    for problem in dataset:
        eq = problem["equation"]
        moves = problem["correct_solution"]["number_of_moves"]
        prompt = PROMPT_TEMPLATE.format(equation=eq, number_of_moves=moves)

        response = query_model(prompt, model_name)
        sections = parse_response(response)
        # Remove spaces from the model's answer for comparison.
        model_answer = sections["answer"].replace(" ", "")

        correct_field = problem["correct_solution"].get("resulting_equation")

        if isinstance(correct_field, str):
            correct_answers = [correct_field.replace(" ", "")]
        elif isinstance(correct_field, dict):
            correct_answers = [ans.replace(" ", "") for ans in correct_field.values()]
        else:
            correct_answers = []

        is_correct = model_answer in correct_answers

        # Save the outputs under the model's name in the problem record.
        # It now includes both the reasoning (the internal monologue) and the answer.
        problem.setdefault("model_outputs", {})[model_name] = {
            "reasoning": sections["reasoning"],
            "answer": sections["answer"],
            "correct": is_correct
        }

    with open(data_path, "w") as f:
        json.dump(dataset, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json_file", type=str, required=True)
    parser.add_argument("--model", type=str, required=True)
    args = parser.parse_args()

    run_on_dataset(Path(args.json_file), args.model)
