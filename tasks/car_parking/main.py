import json
import re
import requests

SOLUTIONS_PATH = "tasks/car_parking/solutions.json"
REMOTE_MODEL_ENDPOINT = "http://your.cluster.endpoint/api/v1/predict" 
TIMEOUT = 10

def format_prompt(board_description):
    return f'''Prompt:
        You are a helpful AI Assistant that provides well-reasoned and detailed responses.
        You first think about the reasoning process as an internal monologue and then provide the user with the answer.
        Respond in the following format:
        <think>
        [Your step-by-step reasoning with detailed considerations.]
        </think>
        <answer>
        [Your final solution in a clear, concise format, including every move.]
        </answer>

        Example Answer: [F+1 K+1 M-1 C+3 H+2 J-1]

        Each move must:
        - Use UPPERCASE letters A-Z for the piece ID
        - Follow with +N or -N where N is the number of spaces moved
        - Be separated by single spaces
        - Be enclosed in square brackets, like: [A+1 B-2]

        Solve the puzzle with board description: {board_description}
        '''

def extract_moves(solution_string):
    return re.findall(r"[A-Z][+-]\d+", solution_string)

def compare_solutions(pred, truth):
    return extract_moves(pred) == extract_moves(truth)

def query_remote_model(prompt):
    response = requests.post(
        REMOTE_MODEL_ENDPOINT,
        json={"prompt": prompt},
        timeout=TIMEOUT
    )
    if response.status_code != 200:
        raise RuntimeError(f"Model call failed: {response.status_code}\n{response.text}")
    return response.json()["output"]

# === Main logic ===
def main():
    with open(SOLUTIONS_PATH, "r") as f:
        solutions = json.load(f)

    total = 0
    correct = 0
    mismatches = []

    for board, expected in solutions.items():
        if expected == "Unsolved":
            continue

        prompt = format_prompt(board)
        try:
            output = query_remote_model(prompt)
            match = re.search(r"<answer>\s*(\[.*?\])\s*</answer>", output, re.DOTALL)
            if not match:
                print(f"Malformed output for {board}")
                continue

            predicted = match.group(1)
            total += 1
            if compare_solutions(predicted, expected):
                correct += 1
            else:
                mismatches.append((board, expected, predicted))
                print(f"\nMismatch for {board}\nExpected:  {expected}\nPredicted: {predicted}")

        except Exception as e:
            print(f"Error processing board {board}: {e}")

    print("\n--- Evaluation Complete ---")
    print(f"Total: {total}, Correct: {correct}, Accuracy: {100 * correct / total:.2f}%")
    if mismatches:
        print(f"\n{len(mismatches)} mismatches:")
        for b, e, p in mismatches:
            print(f"- {b}\n  Expected:  {e}\n  Predicted: {p}\n")

if __name__ == "__main__":
    main()
