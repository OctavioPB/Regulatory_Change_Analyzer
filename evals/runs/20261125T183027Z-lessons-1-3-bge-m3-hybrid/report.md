# Eval run 20261125T183027Z-lessons-1-3-bge-m3-hybrid

- Started: 2026-11-25T18:30:27+00:00  ·  finished: 2026-11-25T18:56:58+00:00
- Suites: rag, agent, addendum, team  ·  retrieval: hybrid: ollama:bge-m3 + keyword, RRF
- Code: commit 2ca1b66 + uncommitted changes
- Cases: developer-written over synthetic data, graded by code. Not lawyer-reviewed.

## rag

| model | pass | answerable_pass | refusal_accuracy | false_refusals | answerable_without_context | invalid_citations | errors | p50_seconds |
|---|---|---|---|---|---|---|---|---|
| ollama:qwen3:4b-instruct-2507-q4_K_M | 7/7 | 5/5 | 2/2 | 0 | 0 | 0 | 0 | 9.4 |
| ollama:gemma4:26b-a4b-it-qat | 7/7 | 5/5 | 2/2 | 0 | 0 | 0 | 0 | 33.3 |

## agent

| model | pass | answerable_pass | refusal_accuracy | false_refusals | invalid_citations | avg_steps | tool_errors | errors | p50_seconds |
|---|---|---|---|---|---|---|---|---|---|
| ollama:qwen3:4b-instruct-2507-q4_K_M | 5/9 | 3/7 | 2/2 | 4 | 0 | 1.3 | 0 | 0 | 10.9 |
| ollama:gemma4:26b-a4b-it-qat | 9/9 | 7/7 | 2/2 | 0 | 0 | 1.7 | 1 | 0 | 43.5 |

## addendum

| model | pass | avg_structure | cites_circular | references_real_clause | drafts_with_unsupported_pct | seconds |
|---|---|---|---|---|---|---|
| ollama:qwen3:4b-instruct-2507-q4_K_M | 7/9 | 1.0 | 9/9 | 9/9 | 0 | 81.6 |
| ollama:gemma4:26b-a4b-it-qat | 7/9 | 1.0 | 9/9 | 9/9 | 0 | 221.6 |

## team

| model | pass | review_approved | avg_rounds | avg_structure | cites_circular | references_real_clause | drafts_with_unsupported_pct | agent_failures | seconds |
|---|---|---|---|---|---|---|---|---|---|
| ollama:qwen3:4b-instruct-2507-q4_K_M | 2/2 | 2/2 | 1.0 | 1.0 | 2/2 | 2/2 | 0 | 0 | 46.3 |
| ollama:gemma4:26b-a4b-it-qat | 2/2 | 1/2 | 2.0 | 1.0 | 2/2 | 2/2 | 0 | 0 | 248.4 |
