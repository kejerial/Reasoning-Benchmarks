from keyword_analysis.main import plot_trends

files = [
    "keyword_analysis/analysis/crossword_grpo_analysis.json",
    "keyword_analysis/analysis/crossword_sft_analysis.json"
]

for path in files:
    plot_trends(path)
    print("Plotted:", path)

