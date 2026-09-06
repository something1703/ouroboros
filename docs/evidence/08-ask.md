# Phase 8.4 — Ask Ouroboros acceptance evidence

`AskOuroboros` (`agents/ouroboros/ask/ask_ouroboros.py`) deployed as a sub-agent of
`OuroborosCoordinator` on the same Vertex AI Agent Engine resource used since Phase 5.5
(`agents/deploy/deploy.py` — required one fix here: `google-cloud-discoveryengine` was
a real transitive import from the new `search_private_corpus` tool, missing from
`_REQUIREMENTS`; the update failed with a bare `400 The Reasoning Engine failed to be
updated` until it was added and traced the same `sys.modules`-diffing way Phase 5.5's
own missing-requirements bugs were found).

All three questions below were run against the **live, redeployed** engine via
`services/dashboard_api/runs.py::ask_question` (project `demo`, real Cloud SQL ledger
data, real Vertex AI Search corpus, real Gemini + Parallel grounding) — not mocked.

## (a) Cites a real ledger claim

**Question:** "Is there an existing claim about the Coca-Cola product placement in
this project, and what is its risk level?"

**Answer (excerpt):**
> Yes, there are two existing verified claims in the ledger for this project regarding
> Coca-Cola/Coke:
>
> ### 1. Visual Placement Claim (Claim ID: `97dfd8f22a95e4908916efc8`)
> Risk Level: **Low** (Risk Score: 0.2) ...
>
> ### 2. Dialogue Mention Claim (Claim ID: `d858a792c9f136760193ad34`)
> Risk Level: **Blocking** (Risk Score: 0.95) ...
>
> ### Studio Precedent
> ... studio clearance memo for the production *"Late Autumn"* (2023) ... decision was
> **"Cleared with Modification"** [3].
>
> **Citations:**
> `[1]` Ledger Claim `97dfd8f22a95e4908916efc8`
> `[2]` Ledger Claim `d858a792c9f136760193ad34`
> `[3]` Private Corpus Document `clearance-memo-late-autumn-2023`
>
> Evidence, not legal advice.

Real claim IDs, real risk scores from the ledger's own risk assessment, cross-checked
against real `packages/claims/models.py::Claim`/`Risk` rows — and, as a bonus, this
answer independently also satisfies (b) by citing the corpus doc.

## (b) Cites a real private-corpus document

**Question:** "What did we decide about Beatles music rights last time?"

**Answer (excerpt):**
> Based on our studio's clearance records, the last decision regarding Beatles music
> rights was documented in a clearance memo for the production **"Northbound" (2022)**
> [1].
>
> **Decision:** NOT CLEARED — REPLACED.
> ... licensing these tracks carries a very high cost and requires a negotiation
> timeline of 3 to 6 months, which was incompatible with the production's release date
> and budget ...
>
> **Citations:**
> [1] clearance-memo-northbound-2022
>
> Evidence, not legal advice.

Matches `fixtures/private_corpus/clearance-memo-northbound-2022.txt` verbatim (ingested
via `scripts/ingest_private_corpus.py` into the real Vertex AI Search datastore,
`infra/modules/vertex_search`), retrieved via `search_private_corpus`, not fabricated.

## (c) Cites a real Parallel-grounded web source

**Question:** "Can we show a Pepsi sign in the Mumbai scene?"

**Answer (excerpt):**
> ... Under the Indian Trade Marks Act, 1999 ... Incidental and De Minimis Use:
> Captured background signage that naturally exists in a streetscape is generally
> legally permissible under the doctrine of *de minimis* ... [3]
>
> [1] Claims Ledger for Project "demo"
> [2] https://rodriqueslaw.com/blog/how-use-brands-and-products-film/
> [3] https://legalblogs.wolterskluwer.com/copyright-blog/defense-of-de-minimis-in-ip-matters-in-india/
> [4] https://www.lexology.com/library/detail.aspx?g=82b78d04-41f5-4181-a87a-aadb0d04c9c7
> [5] https://www.legalservicesindia.com/article/2067/trademark-law-in-music-and-film-industry.html
> [6] https://darkskiesfilm.com/do-i-need-to-clear-every-brand-in-my-film
>
> Evidence, not legal advice.

Six real, distinct citations, byte-offset-inserted by
`packages/gemini_client/grounding.py::_render_citations` (verified separately against
two other live queries during development — see conversation history — before this
question ran).

## `grounding_metadata.web_search_queries` logged

`agents/ouroboros/tools/grounding_tools.py` logs every grounded call's
`web_search_queries` via `structlog`. Confirmed in Cloud Logging for the Pepsi question
above (query run within the same minute the answer was produced):

```
$ gcloud logging read 'resource.type="aiplatform.googleapis.com/ReasoningEngine" AND
    jsonPayload.event="ask_grounded_web_search_queries"' --project=ouroboros-507503 \
    --limit=5 --freshness=1h

jsonPayload.event: "ask_grounded_web_search_queries"
jsonPayload.question: "Is it legally permissible to show a real brand sign like a
  Pepsi sign in a film scene set in Mumbai under Indian trademark law? ..."
jsonPayload.web_search_queries: [
  "\"product placement\" \"trademark infringement\" India",
  "trademark infringement films India incidental use",
  "nominative fair use trademark India movies",
  "\"trademark infringement\" movie brand India"
]
```

## Endpoint

`POST /projects/{project_id}/ask` (`services/dashboard_api/main.py`) — synchronous,
unlike `/runs`'s fire-and-forget `run_id` — returns `{"answer": "<full text>"}` in one
round trip, open to every authenticated role (asking is read-only). Offline-tested in
`tests/services/dashboard_api/test_dashboard_api_main.py`
(`test_ask_returns_answer_text`, `test_ask_surfaces_coordinator_error_as_422`,
`test_ask_requires_auth`).
