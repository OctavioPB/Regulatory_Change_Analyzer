# Documentation

| Document | For | What it covers |
|---|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Engineers, architects | Components, pipeline, data model, retrieval, grounding boundary, agents, providers, security, deployment |
| [ENGINEERING.md](ENGINEERING.md) | Contributors | Stack, layout, running and testing, conventions, CI, engineering decision log (ED-01 – ED-10) |
| [APPLIED_AI.md](APPLIED_AI.md) | AI/ML engineers, reviewers | Where AI is used and where it is not, calibrated hybrid retrieval, citation validation, agents, eval results |
| [BUSINESS_VALUE.md](BUSINESS_VALUE.md) | Compliance, risk, legal, sponsors | Problem, before/after, value drivers, safeguards, cost profile, limits |
| [KNOWLEDGE_LEARNED.md](KNOWLEDGE_LEARNED.md) | Everyone maintaining the system | Lessons from building and evaluating it, lessons imported from Legal_AI_Assistant, open findings |

Also: [evals/README.md](../evals/README.md) (model evaluation), [planning/Business.md](../planning/Business.md)
(full business case), [planning/Decisions.md](../planning/Decisions.md) (original design record).

## Screenshots

Taken on 2026-11-25 from a demo database: the 3 synthetic CNBV circulars, 3 synthetic SEC publications
and 6 demo contracts. LLM features ran on local models through Ollama (gemma4 26B, and qwen3 4B for the
refusal example), with bge-m3 embeddings.

| | |
|---|---|
| **Dashboard** — documents, changes, alerts, pending reviews, severity mix ![](img/dashboard.png) | **Impact alerts** — one alert per changed article, with severity and item count ![](img/alerts.png) |
| **Review queue** — approve, modify or reject each suggested action ![](img/reviews.png) | **Documents** — ingested CNBV and SEC publications ![](img/documents.png) |
| **Risk heatmap** — impacts by department and change type ![](img/heatmap.png) | **Trend analysis** — signals from proposed rules and no-action letters ![](img/trends.png) |
| **Policy chat** — answer with validated `[REG-n]`/`[CON-n]` citations ![](img/chat-rag.png) | **Research agent** — visible tool steps, multi-hop answer ![](img/chat-agent.png) |
| **System refusal** — written by code when the answer cannot be grounded ![](img/chat-system-refusal.png) | **Drafting team** — per-contract drafter + reviewer verdicts ![](img/addendum-team-progress.png) |
| **Drafted addendum** — cites the circular and the real clause ![](img/addendum-team.png) | **Pipeline** — run each stage from the browser ![](img/pipeline.png) |
| **Audit trail** — append-only record of every step ![](img/audit-log.png) | |
