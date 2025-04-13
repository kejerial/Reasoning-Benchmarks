import subprocess
import json
import time
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  
INPUT_FILE = os.path.join(SCRIPT_DIR, "master.txt")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "solutions.json")
GO_SOLVER_PATH = os.path.join(SCRIPT_DIR, "rush", "cmd", "solve", "main.go")
TIMEOUT = 10
SLEEP_BETWEEN = 0.2
GO_EXECUTABLE = "/opt/homebrew/bin/go"

def call_go_solver(board_description):
    try:
        command = [GO_EXECUTABLE, "run", GO_SOLVER_PATH, board_description]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=TIMEOUT,
            text=True
        )
        output = result.stdout.strip()
        print("Go Output:", output)

        match = re.search(r"\{true\s+\[([^\]]+)\]", output)
        if match:
            return "[" + match.group(1).strip() + "]"
        return None
    except subprocess.TimeoutExpired:
        print("Timed out:", board_description)
        return None
    except FileNotFoundError as e:
        print(f"Go not found or bad path: {e}")
        return None

def process_master_file():
    solutions = {}
    with open(INPUT_FILE, "r") as file:
        for line in file:
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            raw_board = parts[1]
            board_description = raw_board.replace("o", ".")
            print(f"\nSolving: {raw_board} → {board_description}")
            solution = call_go_solver(board_description)
            if solution:
                print(f"Solved: {solution}")
                solutions[raw_board] = solution
            else:
                print("Unsolved.")
                solutions[raw_board] = "Unsolved"
            time.sleep(SLEEP_BETWEEN)
    return solutions

def save_solutions(solutions):
    with open(OUTPUT_FILE, "w") as out_file:
        json.dump(solutions, out_file, indent=2)

if __name__ == "__main__":
    sols = process_master_file()
    save_solutions(sols)
    print(f"\nSaved {len(sols)} solutions to {OUTPUT_FILE}")
