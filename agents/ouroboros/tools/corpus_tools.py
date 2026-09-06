"""Vertex AI Search tool for AskOuroboros's private corpus (PHASE_08.md §8.4,
ADK_AGENTS.md §4). A thin ADK-compatible wrapper, same shape as parallel_tools.py:
JSON-schema-friendly parameters, a plain JSON-serializable return.

The private corpus lives in a Vertex AI Search "search engine" (Discovery Engine),
ingested from fixtures/private_corpus/ via scripts/ingest_private_corpus.py, not
written to here.
"""

from __future__ import annotations

import json
from functools import cache

from google.cloud import discoveryengine_v1 as de

_PROJECT_ID = "ouroboros-507503"
_LOCATION = "global"
_ENGINE_ID = "ouroboros-private-corpus-engine"

# google.cloud.discoveryengine_v1's own `serving_config_path` helper builds a
# `dataStores/{id}/servingConfigs/{...}` path unconditionally -- wrong shape for a
# search *engine* (`engines/{id}/servingConfigs/{...}`), found live testing this
# module directly (a real 404 `DataStore ... not found`, not a client bug we can
# route around via a different helper method). Built by hand instead.
_SERVING_CONFIG = (
    f"projects/{_PROJECT_ID}/locations/{_LOCATION}/collections/default_collection/"
    f"engines/{_ENGINE_ID}/servingConfigs/default_search"
)


@cache
def _client() -> de.SearchServiceClient:
    return de.SearchServiceClient()


def search_private_corpus(query: str, result_limit: int = 3) -> str:
    """Search the studio's private corpus of past clearance memos and studio
    guidelines (not the live web, not the claim ledger) for precedent relevant to
    `query`. Returns a JSON array of `{doc_name, gcs_uri, snippet}`, most relevant
    first. Use this before web search when the question sounds like it might already
    have a studio precedent (a past decision, a standing guideline)."""
    spec = de.SearchRequest.ContentSearchSpec(
        snippet_spec=de.SearchRequest.ContentSearchSpec.SnippetSpec(return_snippet=True),
    )
    request = de.SearchRequest(
        serving_config=_SERVING_CONFIG,
        query=query,
        page_size=result_limit,
        content_search_spec=spec,
    )
    response = _client().search(request)

    results = []
    for hit in response.results:
        data = hit.document.derived_struct_data
        title = str(data.get("title", hit.document.id))
        link = str(data.get("link", ""))
        snippets = data.get("snippets") or []
        snippet_text = ""
        if snippets:
            first = snippets[0]
            snippet_text = str(first.get("snippet", "")) if hasattr(first, "get") else ""
        results.append({"doc_name": title, "gcs_uri": link, "snippet": snippet_text})

    return json.dumps(results)
