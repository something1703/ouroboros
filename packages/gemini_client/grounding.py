"""Gemini grounding via Parallel's ToolParallelAiSearch (PARALLEL_INTEGRATION.md §4.8,
ADK_AGENTS.md §4). Lives here, not packages/parallel_client, because this calls Gemini
directly and Parallel is attached as a grounding *tool* Gemini invokes internally
during generation -- we never call Parallel's own API in this module.

Always BYOK (`api_key=` set): this project has no Vertex AI Marketplace subscription
for Parallel, only the Secret Manager key every other Parallel call already uses.
"""

from __future__ import annotations

import os
from functools import cache

from google import genai
from google.genai import types

from config.models import GROUNDING_MODEL
from packages.common.secrets import get_secret


@cache
def _client() -> genai.Client:
    # Cached for the same reason packages/gemini_client/documents.py's _client() is:
    # an unbound genai.Client() has been observed garbage-collected mid-request.
    return genai.Client(vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT"))


def _render_citations(
    text: str, metadata: types.GroundingMetadata | None
) -> tuple[str, list[dict[str, str]]]:
    """Insert `[n]` markers at each grounding support's byte offset. Two passes:
    first assign citation numbers in natural reading order (ascending offset), so
    `[1]` really is the first citation a reader encounters; then insert the
    already-numbered markers in reverse offset order, so an earlier insertion never
    shifts the offset of a support not yet processed (PARALLEL_INTEGRATION.md §4.8's
    own explicit instruction) -- numbering and insertion are deliberately separate
    passes so neither concern has to fight the other's ordering requirement."""
    if metadata is None or not metadata.grounding_supports or not metadata.grounding_chunks:
        return text, []

    chunks = metadata.grounding_chunks
    # Narrow (end_index, chunk_indices) into concrete non-Optional tuples once, up
    # front, rather than re-checking `support.segment`/`.grounding_chunk_indices` for
    # None at every later use site.
    supports: list[tuple[int, list[int]]] = [
        (s.segment.end_index or 0, list(s.grounding_chunk_indices))
        for s in metadata.grounding_supports
        if s.segment is not None and s.grounding_chunk_indices
    ]
    supports.sort(key=lambda s: s[0])

    citations: list[dict[str, str]] = []
    chunk_index_to_citation_number: dict[int, int] = {}
    for _end, chunk_indices in supports:
        for chunk_i in chunk_indices:
            if chunk_i in chunk_index_to_citation_number:
                continue
            web = chunks[chunk_i].web if chunk_i < len(chunks) else None
            citations.append(
                {"url": web.uri or "" if web else "", "title": web.title or "" if web else ""}
            )
            chunk_index_to_citation_number[chunk_i] = len(citations)

    annotated = text
    for end, chunk_indices in sorted(supports, key=lambda s: s[0], reverse=True):
        numbers = sorted({chunk_index_to_citation_number[i] for i in chunk_indices})
        marker = "".join(f"[{n}]" for n in numbers)
        annotated = annotated[:end] + marker + annotated[end:]

    return annotated, citations


def ask_grounded(question: str, *, location: str) -> dict[str, object]:
    """Ask Gemini a question grounded in live web search via Parallel. Returns
    `{"text": <answer with [n] citation markers>, "citations": [{"url","title"}],
    "web_search_queries": [...]}` -- the last field is what PHASE_08.md §8.4's
    acceptance criteria requires logging."""
    tool = types.Tool(
        parallel_ai_search=types.ToolParallelAiSearch(
            api_key=get_secret("PARALLEL_API_KEY"),
            custom_configs={"mode": "basic", "max_results": 10, "location": location},
        )
    )
    response = _client().models.generate_content(
        model=GROUNDING_MODEL,
        contents=question,
        config=types.GenerateContentConfig(tools=[tool]),
    )
    candidate = response.candidates[0] if response.candidates else None
    raw_text = ""
    if candidate and candidate.content and candidate.content.parts:
        raw_text = "".join(part.text or "" for part in candidate.content.parts)

    metadata = candidate.grounding_metadata if candidate else None
    text, citations = _render_citations(raw_text, metadata)
    web_search_queries = list(metadata.web_search_queries or []) if metadata else []

    return {"text": text, "citations": citations, "web_search_queries": web_search_queries}
