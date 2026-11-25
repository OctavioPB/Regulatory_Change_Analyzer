# Eval run 20261125T185727Z-lessons-1-3-keyword-gemma

- Started: 2026-11-25T18:57:27+00:00  ·  finished: 2026-11-25T19:06:46+00:00
- Suites: rag, agent, addendum, team  ·  retrieval: keyword (embeddings off)
- Code: commit 2ca1b66 + uncommitted changes
- Cases: developer-written over synthetic data, graded by code. Not lawyer-reviewed.

## rag

| model | pass | answerable_pass | refusal_accuracy | false_refusals | answerable_without_context | invalid_citations | errors | p50_seconds |
|---|---|---|---|---|---|---|---|---|
| ollama:gemma4:26b-a4b-it-qat | 5/7 | 3/5 | 2/2 | 2 | 0 | 0 | 0 | 3.5 |

## agent

| model | pass | answerable_pass | refusal_accuracy | false_refusals | invalid_citations | avg_steps | tool_errors | errors | p50_seconds |
|---|---|---|---|---|---|---|---|---|---|
| ollama:gemma4:26b-a4b-it-qat | 8/9 | 6/7 | 2/2 | 1 | 0 | 1.8 | 1 | 0 | 11.4 |

## addendum

| model | pass | avg_structure | cites_circular | references_real_clause | drafts_with_unsupported_pct | seconds |
|---|---|---|---|---|---|---|
| ollama:gemma4:26b-a4b-it-qat | 7/9 | 1.0 | 9/9 | 9/9 | 0 | 227.3 |

## team

| model | pass | review_approved | avg_rounds | avg_structure | cites_circular | references_real_clause | drafts_with_unsupported_pct | agent_failures | seconds |
|---|---|---|---|---|---|---|---|---|---|
| ollama:gemma4:26b-a4b-it-qat | 2/2 | 2/2 | 1.5 | 1.0 | 2/2 | 2/2 | 0 | 0 | 163.0 |
