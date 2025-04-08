import random
import os

script_dir = os.path.dirname(__file__)
input_file = os.path.join(script_dir, "master.txt")
output_file = input_file

with open(input_file, 'r') as f:
    lines = list(f)

print(f"Total lines found: {len(lines)}")

selected = random.sample(lines, 1000)

with open(output_file, 'w') as f:
    f.writelines(selected)
