# Auditing Aha! Moments in Finetuned Language Models: A Cognitive-Theory Driven Analysis of CoT
[![Hugging Face 🤗–Qwen2.5-7B Instruct SFT](https://img.shields.io/badge/Hugging%20Face-%F0%9F%A4%97--Qwen2.5--7B--Instruct--SFT-blue?logo=HuggingFace&logoColor=white)](https://huggingface.co/od2961/Qwen2.5-7B-Instruct-SFT)
[![Hugging Face 🤗–Qwen2.5-7B Instruct GRPO](https://img.shields.io/badge/Hugging%20Face-%F0%9F%A4%97--Qwen2.5--7B--Instruct--GRPO-blue?logo=HuggingFace&logoColor=white)](https://huggingface.co/od2961/Qwen2.5-7B-Instruct-GRPO)

#### Abstract:
We present a human psychology-ground audit to maps chain-of-thought (CoT) traces to two complementary cognitive theories of insight—\emph{Representational Change Theory} (RCT) and \emph{Progress Monitoring Theory} (PMT)—using a GPT-4o-based majority-vote classifier with inter-rater reliability of $\kappa > 0.85$. We apply this audit to two model families and multiple alignment regimes:
(1) On \texttt{Qwen2.5‑7B‑Instruct}, Guided Reinforcement Preference Optimization (GRPO) improves accuracy by +7 problems (+9.1\%) over the pretrained baseline and shifts the RCT:PMT ratio from 0.65 to 0.81, while Supervised Fine-Tuning (SFT) maintains accuracy but preserves strategy diversity.
(2) \textbf{(2)~DeepSeek‑V3 (MoE, 37B active / 671B total).} GRPO boosts accuracy from $134/254$ to $179/254$ ($52.8\%\!\to\!70.5\%$, \,+17.7pp) and magnifies the RCT:PMT ratio from $4.8$ to $16.5$. 

\textbf{Contributions:}
\begin{itemize}[nosep,leftmargin=1em]
    \item We introduce an automated, language-only reasoning audit grounded in psychology, requiring no model internals.
    \item We evaluate GRPO vs. SFT across both medium- and large-scale models, revealing alignment-driven shifts in reasoning structure.
    \item We show that GRPO consistently promotes representational restructuring (RCT) over progress-monitoring (PMT), with effects robust across scale.
\end{itemize}

Our findings suggest that alignment methods influence not only \emph{how many} tasks LLMs solve, but \emph{how} they reason—insightfully or heuristically. We release all \href{https://github.com/kejerial/Reasoning-Benchmarks}{code} alongside model checkpoints for both \href{https://huggingface.co/od2961/Qwen2.5-7B-Instruct-SFT}{Qwen2.5-7B-Instruct-SFT} and \href{https://huggingface.co/od2961/Qwen2.5-7B-Instruct-GRPO}{Qwen2.5-7B-Instruct-GRPO}.
