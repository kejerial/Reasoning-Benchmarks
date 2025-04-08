import json
import argparse
from pathlib import Path
from typing import Dict
import subprocess

PROMPT_TEMPLATE = """# Matchstick Puzzles

Prompt:

This requires engaging in a comprehensive cycle of analysis, summarizing, exploration, reassessment, reflection, backtracing, and iteration to develop well-considered thinking process. Please structure your response into two main sections: Thought and Solution. In the Thought section, detail your reasoning process using the specified format: <|begin_of_thought|> {thought with steps separated with '\\n\\n'} <|end_of_thought|> Each step should include detailed considerations such as analysing questions, summarizing relevant findings, brainstorming new ideas, verifying the accuracy of the current steps, refining any errors, and revisiting previous steps. In the Solution section, based on various attempts, explorations, and reflections from the Thought section, systematically present the final solution that you deem correct. The solution should remain a logical, accurate, concise expression style and detail necessary step needed to reach the conclusion, formatted as follows: <|begin_of_solution|> {final formatted, precise, and clear solution} <|end_of_solution|> Now, try to solve the following question through the above guidelines:

You are to be given a \"matchstick puzzle\" where you need to identify how to rearrange matches to convert a given numerical equation or expression into another. The format of a digit's expression in matches depends on how many of 7 matchsticks are chosen ( top, upper left, upper right, middle, lower left, lower right, bottom).

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

The key for each of the operator's matchstick representation is:
- Minus (-): 1 matchstick.
- Plus (+): 2 matchsticks (one horizontal and one vertical).
- Multiplication (x) : can not be changed (if an equation has a multiplication sign, then do not change that operator)

Rules:
1. The only valid move is a transfer of matchsticks. In other words, you may move around matchsticks but only such that the total number of matchsticks remains the same. Also, the resulting configuration of all digits/operators adheres to the key above.
2. The puzzle presents an initial equation built from these matchstick configurations.
3. Your task is to identify which matchstick to move (or remove and reattach) in order to create a valid equation.

Problem:
{equation}  Move exactly {number_of_moves} match stick to fix this equation. 

You may not change the equal sign, so !=, ≥, >, <, or ≤ are not allowed. Provide your answer in the form of one line for every moved match stick of the format of which specific segment of which digit/operator will be moved which specific segment of another digit/operator and one line for the resulting equation.
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
    thought = ""
    answer = ""
    explanation = ""

    if "<|begin_of_thought|>" in response and "<|end_of_thought|>" in response:
        thought = response.split("<|begin_of_thought|>")[1].split("<|end_of_thought|>")[0].strip()

    if "<|begin_of_solution|>" in response and "<|end_of_solution|>" in response:
        solution = response.split("<|begin_of_solution|>")[1].split("<|end_of_solution|>")[0].strip()
        lines = [line.strip() for line in solution.splitlines() if line.strip()]
        if len(lines) >= 2:
            explanation = lines[0]
            answer = lines[1]
        elif len(lines) == 1:
            answer = lines[0]

    return {
        "reasoning": thought,
        "answer": answer,
        "explanation": explanation
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
        model_answer = sections["answer"].replace(" ", "")

        correct_field = problem["correct_solution"].get("resulting_equation")

        if isinstance(correct_field, str):
            correct_answers = [correct_field.replace(" ", "")]
        elif isinstance(correct_field, dict):
            correct_answers = [ans.replace(" ", "") for ans in correct_field.values()]
        else:
            correct_answers = []

        is_correct = model_answer in correct_answers

        problem["model_outputs"][model_name] = {
            "reasoning": sections["reasoning"],
            "answer": sections["answer"],
            "explanation": sections["explanation"],
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
