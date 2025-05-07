# Auditing Aha! Moments in Finetuned Language Models: A Cognitive-Theory Driven Analysis of CoT
[![Static Badge](https://img.shields.io/badge/Hugging%20Face%20🤗-Qwen2.5-7B-Instruct-SFT-blue)](https://huggingface.co/od2961/Qwen2.5-7B-Instruct-SFT)
[![Static Badge](https://img.shields.io/badge/Hugging%20Face%20🤗-Qwen2.5-7B-Instruct-GRPO-blue)](https://huggingface.co/od2961/Qwen2.5-7B-Instruct-GRPO)

Abstract:
We present a human psychology-ground audit to maps chain-of-thought (CoT) traces to two complementary cognitive theories of insight—\emph{Representational Change Theory} (RCT) and \emph{Progress Monitoring Theory} (PMT)—using a GPT-4o-based majority-vote classifier with inter-rater reliability of $\kappa > 0.85$. We apply this audit to two model families and multiple alignment regimes:
(1) On \texttt{Qwen2.5‑7B‑Instruct}, Guided Reinforcement Preference Optimization (GRPO) improves accuracy by +7 problems (+9.1\%) over the pretrained baseline and shifts the RCT:PMT ratio from 0.65 to 0.81, while Supervised Fine-Tuning (SFT) maintains accuracy but preserves strategy diversity.
(2) \textbf{(2)~DeepSeek‑V3 (MoE, 37B active / 671B total).} GRPO boosts accuracy from $134/254$ to $179/254$ ($52.8\%\!\to\!70.5\%$, \,+17.7pp) and magnifies the RCT:PMT ratio from $4.8$ to $16.5$.
