# Eval run 20261125T174820Z-same-circular-baseline

- Started: 2026-11-25T17:48:20+00:00  ·  finished: 2026-11-25T18:02:30+00:00
- Suites: rag, agent, addendum, team  ·  retrieval: keyword (embeddings off)
- Cases: developer-written over synthetic data, graded by code. Not lawyer-reviewed.

## rag

| model | pass | answerable_pass | refusal_accuracy | false_refusals | answerable_without_context | invalid_citations | errors | p50_seconds |
|---|---|---|---|---|---|---|---|---|
| ollama:qwen3:4b-instruct-2507-q4_K_M | 5/7 | 3/5 | 2/2 | 2 | 2 | 0 | 0 | 0.4 |
| ollama:gemma4:26b-a4b-it-qat | 5/7 | 3/5 | 2/2 | 2 | 2 | 0 | 0 | 3.2 |

## agent

| model | pass | answerable_pass | refusal_accuracy | false_refusals | invalid_citations | avg_steps | tool_errors | errors | p50_seconds |
|---|---|---|---|---|---|---|---|---|---|
| ollama:qwen3:4b-instruct-2507-q4_K_M | 6/9 | 4/7 | 2/2 | 3 | 0 | 1.7 | 0 | 0 | 2.4 |
| ollama:gemma4:26b-a4b-it-qat | 8/9 | 7/7 | 1/2 | 0 | 0 | 1.8 | 2 | 1 | 10.2 |

## addendum

| model | pass | avg_structure | cites_circular | references_real_clause | drafts_with_unsupported_pct | seconds |
|---|---|---|---|---|---|---|
| ollama:qwen3:4b-instruct-2507-q4_K_M | 9/9 | 1.0 | 9/9 | 1/9 | 0 | 84.1 |
| ollama:gemma4:26b-a4b-it-qat | 7/9 | 1.0 | 9/9 | 2/9 | 0 | 222.0 |

## team

| model | pass | review_approved | avg_rounds | avg_structure | cites_circular | references_real_clause | drafts_with_unsupported_pct | agent_failures | seconds |
|---|---|---|---|---|---|---|---|---|---|
| ollama:qwen3:4b-instruct-2507-q4_K_M | 2/2 | 2/2 | 2.0 | 1.0 | 2/2 | 2/2 | 0 | 0 | 92.5 |
| ollama:gemma4:26b-a4b-it-qat | 2/2 | 2/2 | 2.0 | 1.0 | 2/2 | 0/2 | 0 | 0 | 226.6 |
