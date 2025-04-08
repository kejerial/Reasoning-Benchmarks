import re
import subprocess
import time

class Solver:
    def __init__(self, board_description, expected_moves, extra_info, max_retries=3, timeout=10):
        self.board_description = board_description
        self.expected_moves = int(expected_moves)
        self.extra_info = extra_info
        self.max_retries = max_retries
        self.timeout = timeout
        self.puzzle_setup = None
    
    def parse_puzzle(self):
        self.puzzle_setup = self.board_description
        return self.puzzle_setup
    
    def generate_solution(self, prompt):
        # Replace the below dummy solution with inference method for models on cluster. Set up prompts is provided in readme file.

        dummy_solution = (
            "[F+1 K+1 M-1 C+3 H+2 J-1 E+1 G+3 B-1 I-1 A-3 I+1 L+1 B+3]"
        )
        return dummy_solution
    

    def validate_solution(self, formatted_solution):
        '''
        Validate LLM's solution with provided Go code at 'tasks/car_parking/rush/cmd/solve/main.go'.
        '''
        command = [
            "go", "run", "tasks/car_parking/rush/cmd/solve/main.go",
            self.puzzle_setup, formatted_solution
        ]
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                text=True
            )
            output = result.stdout.strip()
            # Assume a valid solution produces output starting with "{true"
            if output.startswith("{true"):
                return True, output
            else:
                return False, output
        except subprocess.TimeoutExpired:
            return False, "Validation timed out."
        

    def solve(self):
        self.parse_puzzle()
        prompt = (
            "This requires engaging in a comprehensive cycle of analysis, summarizing, exploration, reassessment, reflection, backtracing, and iteration to develop well-considered thinking process. Please structure your response into two main sections: Thought and Solution. In the Thought section, detail your reasoning process using the specified format: <|begin_of_thought|> {thought with steps separated with \'\\n\\n\'} <|end_of_thought|> Each step should include detailed considerations such as analyzing questions, summarizing relevant findings, brainstorming new ideas, verifying the accuracy of the current steps, refining any errors, and revisiting previous steps. In the Solution section, based on various attempts, explorations, and reflections from the Thought section, systematically present the final solution that you deem correct. The solution should remain a logical, accurate, concise expression style and detail necessary step needed to reach the conclusion, formatted as follows: <|begin_of_solution|> {final formatted, precise, and clear solution} <|end_of_solution|> Now, try to solve the following question through the above guidelines: The board description is a 36-character string representing the state of the unsolved board. It is a 6x6 2D array in row-major order. The characters in the description follow these simple rules: o empty cell, x wall (fixed obstacle), A primary piece (red car), B - Z all other pieces. Your goal is to figure out a series of moves to get the primary piece A to exit the board. The primary piece will 'exit the board' if it reaches the square in row 3 column 6. For the following board description," + f"{self.board_description}" + "give me a sequential list of every move that must be taken to get the primary piece A to exit the board. Give your solution in the format as follows: Negative moves are up or left, positive moves are down or right. An example of this is [F+1 K+1 M-1 C+3 H+2 J-1]"
        )
        attempt = 0
        while attempt < self.max_retries:
            raw_solution = self.generate_solution(prompt)
            formatted_solution = self.format_solution(raw_solution)
            valid, validation_output = self.validate_solution(formatted_solution)
            if valid:
                return formatted_solution, validation_output
            else:
                print(f"Attempt {attempt+1} failed for board {self.board_description}: {validation_output}")
                # Refine the prompt with error feedback and retry.
                prompt += f" [Refined after error: {validation_output}]"
                attempt += 1
                time.sleep(1)
        return None, "Max retries reached. No valid solution found."
    
    def process_tasks(file_path):
        total = 0
        solved = 0
        correct_moves = 0
        discrepancies = []
        
        with open(file_path, "r") as f:
            lines = f.readlines()
        
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            expected_moves, board_description, extra_info = parts[0], parts[1], parts[2]
            solver = solver(board_description, expected_moves, extra_info)
            solution, validation_output = solver.solve()
            total += 1
            if solution is not None:
                solved += 1
                move_count = solver.count_moves(solution)
                if move_count == solver.expected_moves:
                    correct_moves += 1
                else:
                    discrepancies.append((board_description, solver.expected_moves, move_count))
            else:
                print(f"Puzzle {board_description} could not be solved: {validation_output}")
        
        print("\n----- Statistics -----")
        print("Total puzzles processed:", total)
        print("Puzzles solved (validated):", solved)
        if total > 0:
            accuracy = correct_moves / total * 100
            print("Accuracy (by correct move count): {:.2f}%".format(accuracy))
        if discrepancies:
            print("\nDiscrepancies (board description, expected moves, actual moves):")
            for board, expected, actual in discrepancies:
                print(f"Board: {board}, Expected: {expected}, Actual: {actual}")

    if __name__ == "__main__":
        file_path = "tasks/car_parking/Rush Hour"
        process_tasks(file_path)