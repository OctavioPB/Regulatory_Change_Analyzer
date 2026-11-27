# Knowledge Learned

Lessons from building, evaluating and hardening the Regulatory Change Analyzer. Each lesson says what
happened, what it taught, and the rule that now follows from it. They are grouped by theme, not by date.
The sprint-by-sprint notes from the first build are in [planning/CLAUDE.md](../planning/CLAUDE.md).

---

## 1. Evaluating AI features

**1.1 Measure every change separately.** The Legal_AI_Assistant work was imported as three changes:
grounding, a code-loaded brief, and multilingual embeddings. Measuring each one on its own showed which
change moved which metric. The brief moved real-clause references from 1–2/9 to 9/9. Embeddings moved
RAG from 5/7 to 7/7. Grounding moved no pass rate, but it blocks invented citations.
*Rule:* one change per eval arm. Record the commit and retrieval mode with the run.

**1.2 Small sets are noisy.** With 9 cases, one case is more than 10 points, and local models differed by
±1 case between runs even at temperature 0 with a fixed seed.
*Rule:* a one-case difference is not an improvement. Look at which case flipped and why.

**1.3 Graders have bugs too.** Two were found:
- A `\b` written through a Python string became a backspace character, so "references a real clause"
  was always false.
- "12.0%" in a draft was compared as text with "12%" in the circular and flagged as an invented figure.

*Rule:* test the graders like code, and re-grade stored outputs (`--regrade`) after fixing them,
without calling the models again.

**1.4 Read failures, not just rates.** Several "model failures" were app bugs once the outputs were
read:
- the ratio leak described in 3.2;
- a wrong diff baseline;
- an empty answer that was reported as success.

Several "passes" hid weak behaviour, such as a reviewer that approves everything.
*Rule:* every eval report is opened and the failing cases are read before any conclusion.

**1.5 A strict rule can dominate a metric.** Four of the 7/9 addendum failures are one rule: the
contract is named "Master Investment Agreement — Fintech ABC", and models write "Master Investment
Agreement" with Fintech ABC as `[PARTY B]`.
*Rule:* report what the rule penalises next to the number. Do not loosen a grader to improve a figure
without deciding that on purpose.

**1.6 Real data finds what synthetic data cannot.** The 3 synthetic circulars passed. On 7 real SEC
amendments from the eCFR, the change-detection suite found four bugs in its first run (2026-11-27):
- T+3 → T+2 was missed;
- every change was flagged as the whole section;
- a deadline change was typed as a new requirement;
- SEC documents could never be paired with their previous version.

The ground truth came from the official paragraph labels, independent of the app. Where the Federal
Register's amendatory instruction lists paragraphs, it agrees with them (Schedule 13D).
*Rule:* every pipeline change is measured on real amendments as well as on the synthetic demo corpus.

## 2. Retrieval and embeddings

**2.1 Monolingual embeddings fail silently across languages.** The circulars are Spanish, many questions
are English. With `all-MiniLM-L6-v2` and keyword search, English questions retrieved nothing and both
models correctly refused. `bge-m3` fixed it: RAG went from 5/7 to 7/7.
*Rule:* choose the embedder for the languages of the corpus *and* of the users.

**2.2 Similarity thresholds belong to a model.** The clause-mapping thresholds (0.65/0.80) were set for
MiniLM. With bge-m3, the best cross-lingual change×clause pair scored 0.675, so almost nothing would have
been mapped. They were re-calibrated from data: covered and unrelated probe questions, and reading the
top pairs.
*Rule:* changing the embedder means re-measuring every threshold. Write the measurement next to the
constant.

**2.3 Top-k is a budget that shrinks as the corpus grows.** With the 3-document eval corpus, the AML
threshold question was answered. With 3 more SEC documents in the demo database, the article that holds
the figure fell out of the top 5, and the model correctly refused.
*Open:* measure top-5 against top-8 on a larger corpus before raising it. Legal_AI's lesson is that
fewer good fragments beat many mediocre ones for weak models.

**2.4 Vectors are not strings.** Once the dimension rose from 384 to 1024, the cross-mapping query
failed. numpy elides arrays longer than 1,000 items (`[a b ... z]`), so `str(vector)` stopped being a
valid pgvector literal. It was found only by launching the real app with real data.
*Rule:* serialise with `vector_literal()`, and run the app end to end after any infrastructure change.

**2.5 Make the dimension a configuration with a guard.** A database built for 384 dimensions and code
expecting 1024 would fail on every insert.
*Rule:* make the column size explicit (`EMBEDDING_DIM`) and migrate by emptying vectors, never by
truncating or padding. Check the schema at startup and degrade to keyword search on a mismatch.

## 3. Grounding and prompting

**3.1 The model should not write the refusal.** A model asked to "say you don't know" explains itself
and still answers. Small models cite tags they never saw (qwen's `[CON-7]`).
*Rule:* the system checks citations, regenerates once with feedback written by code, and then emits a
fixed refusal. It does not call the model at all when nothing was retrieved. This is Legal_AI ADR-007.

**3.2 Give the model the source, not a label for it.** The single-call addendum prompt carried only the
diff summary, `content modified (ratio=0.96)`. qwen turned that into a "96% net capital ratio"
obligation.
*Rule:* send the regulation text itself, and strip internal metrics from anything a model reads.

**3.3 Small models skip optional lookups.** gemma's drafter made 0 tool calls in team mode and invented
"Clause [X]".
*Rule:* anything the output must reference (contract clauses, regulation text) is loaded into the brief
by code. Tools are for what is genuinely optional. This is the Legal_AI pattern: the pipeline retrieves,
the model writes.

**3.4 A reviewer is only as good as its model.** qwen's reviewer approved every draft in round 1. With
gemma, the reviewer found real issues: an invented obligation and a non-existent clause.
*Rule:* do not count "approved by the reviewer" as quality when the reviewer is a small model. Measure
it.

**3.5 Provider quirks need adapters, not prompt hacks.** With both `tools` and a JSON `format` in one
Ollama request, qwen produced nothing until max_tokens.
*Rule:* fix it in the adapter by running two phases (tools, then the schema), and cover it with a test.
Do not change every prompt.

## 4. Regulatory domain

**4.1 "Previous version" means the same regulation, not the same source.** Diffing each circular
against the last one from the same regulator created false repeal alerts and mixed two unrelated texts,
and it confused both models.
*Rule:* identify the regulation, here by circular number, and analyse a document with no identifier on
its own.

**4.2 Small changes are the important ones.** A move from "20%" to "15%" in a 40-character section is a
change ratio of about 0.05. The original 0.30 threshold dropped it. It is now 0.02. Short provisions
(under 60 characters) are real provisions too.

**4.3 Match numbers by position, not by context window.** In a short sentence, two percentages share
the same context window. Matching the N-th old figure to the N-th new one is simpler and correct for
amendments.

**4.4 Spanish patterns need plural forms.** `fondo de inversión` does not match "fondos de
inversión". Write `fondos?`, and test each pattern on real wording.

**4.5 Each jurisdiction has its own unit of change.** CNBV circulars are split by "Artículo"; CFR
sections have no such headers, only lettered paragraphs "(a)", "(b)(1)". Without them, the whole
section was one block, a one-word amendment fell under the change threshold, and reviewers were
shown 100% of the text when 20–76% had changed.
*Rule:* split on the jurisdiction's own unit (lettered paragraphs, in sequence so roman "(i)" is not
mistaken for the letter). Decide "changed" by words, not by a character ratio.

**4.6 Classify what changed, not what the provision says.** Almost every provision contains
"shall", "must" or "deberán", so whole-text keywords typed "within 10 days" → "within five business
days" as a new requirement.
*Rule:* for modified provisions, classify the edited words with a few words of context. A changed
amount means limit_modification; a changed period means deadline. Only large rewrites fall back to
whole-text rules.

**4.7 PDF text is not the law's text.** On five real DOF reforms (2026-11-27) the app flagged 100,
173, 64 and 32 articles when 1–12 had changed. Two causes:
- **Split words.** The text layer splits words at random and differently in each version ("fo ndo",
  "Valore s"). That alone accounted for 99 of 100 false alerts in the CFF.
- **Lost suffixes.** Article numbers lost their suffixes ("107 Bis", "17-H"), so variant articles
  merged into their base article.

After comparing words with their separators removed and keeping the suffixes, every case flags
exactly the decree's articles.
*Rule:* treat word splits and line breaks as layout, never as a change. An article's identity
includes "Bis/Ter…" and "-A". The page headers and "Párrafo reformado DOF…" notes the publisher adds
are not law.

**4.8 An official decree is the best ground truth.** Each DOF decree lists, per law, the articles it
amends. In all five cases that list matched the articles whose text changed between the archived
copies, so the eval's ground truth is official, not inferred.

## 5. Engineering

**5.1 Patch where the name is looked up.** A dict of scraper classes captures references at import, so
patching the class name does nothing. Use `patch.dict`. Make assertions on mocks inside the `with`
block, or keep a reference to the mock.

**5.2 Async sessions cannot lazy-load.** Accessing `change.document` without `selectinload` raises
`MissingGreenlet`.

**5.3 One session, many agents, one lock.** Parallel drafting subagents share one `AsyncSession`.
`AgentContext` serialises database access with an `asyncio.Lock` while the slow model calls overlap.

**5.4 A test environment must not depend on the developer's machine.** Once Ollama became the default
embedder, a running Ollama would have changed unit-test results and slowed them down: 16 s with network
probes against 6 s without.
*Rule:* conftest forces `EMBEDDING_PROVIDER=none` and the Anthropic provider with no key.

**5.5 Local GPUs fail in ways cloud APIs do not.** Ollama crashed loading gemma with a CUDA error in one
eval run, and the rerun worked. bge-m3 and a 26B model share 8 GB of VRAM, so RAG latency rose from 3 s
to 33 s with gemma.
*Rule:* make long runs resumable per model and per suite, and report latency together with accuracy.

**5.6 Environment conflicts are part of the setup.** Port 5432 belonged to another project's Postgres,
so evals and integration tests use a throwaway container on port 55432. Database names must end in
`_test` or `_eval`, because these suites TRUNCATE.

## 6. Lessons imported from Legal_AI_Assistant

Reviewed on 2026-11-25. Applied here:

| Lesson (Legal_AI) | Applied as |
|---|---|
| Refusal is a system action (ADR-007) | `grounding.py`: no model call without sources; fixed refusal text |
| Citation validator, regenerate once with code feedback, then refuse | Chat and research agent |
| The pipeline retrieves; small models do not choose what to read (ADR-022) | Drafter brief loads clauses and regulation text |
| Multilingual embedder (bge-m3 via Ollama, ADR-014) | Default embedder; Docker image without torch |
| Hybrid retrieval, RRF with rank-only fusion and stable ties | `retrieval.py` |
| Calibrate thresholds with probe sets, do not guess (ADR-007 b) | Similarity floors and mapper thresholds |
| 1–2 cases are noise; read failures; graders have bugs | Eval practice and `--regrade` |
| Record commit and dirty flag with every run | Eval reports |

Not applied, because they do not fit here: row-level multi-tenancy, a reranker with a calibrated τ
gate, verbatim-quote checks, and per-conversation model profiles. Model choice per task is still open;
see §7.

## 7. Open findings

| Finding | Evidence | Next step |
|---|---|---|
| Top-5 retrieval drops relevant articles as the corpus grows | AML question refused in the demo database with 3 SEC docs added | Measure top-5 vs top-8 on a larger corpus |
| Cross-jurisdiction floor (0.60) not re-measured for bge-m3 | Eval corpus has no SEC data | Build a CNBV+SEC probe set |
| qwen gives up on multi-hop agent questions | 5/9 in every run | Use gemma (or Claude) for the agent; pick a model per task on evidence |
| Claude never evaluated | No API key configured | Run the same eval with `anthropic:claude-opus-5-5` (billed) |
| Eval cases not lawyer-reviewed | Developer-written, synthetic corpus | Lawyer review before quoting figures |
| No CNBV rulebook (CUB) resolutions in the change-detection suite | It covers 5 law reforms (LIC, LGOAAC, LMV, Ley Fintech, CFF); the CUB is a ~1,000-page PDF with no archived versions bracketing a single resolution yet | Find archived CUB versions, or build the "after" text from the resolution itself |
| The 2025 AML-law (LFPIORPI) reform cannot be evaluated | No archived consolidated text exists between the 2021 and 2025 reforms | Keep watching the archive, or reconstruct from the 2021 decree |
| Lettered-paragraph split needs one paragraph per line | The eCFR loader renders it that way; SEC press releases and PDFs may not | Feed eCFR text for SEC rules, or normalise line breaks at ingestion |
| Renumbered paragraphs count as modified | T+1: old (b)(2) became (b)(3) | Accept it (the instruction says "revise"), or match moved paragraphs by text |
