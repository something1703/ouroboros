"""Gemini document understanding: screenplay PDF -> legal Claim[]. See PHASE_03.md §3.2.

Scripts over MAX_SCRIPT_PAGES_PER_CHUNK pages are split into overlapping windows (each
uploaded as a temporary GCS object, deleted after) so Gemini never sees more than one
window at a time; results are merged by claim_id, which naturally dedupes the overlap.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import google.cloud.storage as storage
from google import genai
from google.genai import types

from config.models import (
    EXTRACTION_MODEL,
    EXTRACTION_SAFETY_SETTINGS,
    EXTRACTION_TEMPERATURE,
    MAX_SCRIPT_PAGES_PER_CHUNK,
    SCRIPT_CHUNK_OVERLAP_PAGES,
)
from packages.claims.enums import ClaimCategory, ClaimKind
from packages.claims.models import Claim, Project, SourceRef
from packages.gemini_client.schemas import ExtractedScriptClaim, ScriptExtraction

_PROMPT_PATH = Path(__file__).parent / "prompts" / "script_extraction.md"


@dataclass(frozen=True)
class ScriptExtractionResult:
    claims: list[Claim]
    page_count: int


def _prompt() -> str:
    return _PROMPT_PATH.read_text()


@cache
def _client() -> genai.Client:
    # Cached (not a fresh instance per call): an uncached, unbound genai.Client() as a
    # bare temporary was observed to be garbage-collected mid-request — the SDK issues
    # the HTTP call from a worker thread, and with no name binding on the caller's side
    # keeping it alive, CPython's refcounting GC's the client (closing its httpx client)
    # while that thread is still using it, raising "Cannot send a request, as the client
    # has been closed." A long-lived cached client avoids the race entirely.
    return genai.Client(vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT"))


def _parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"expected a gs:// URI, got {gcs_uri!r}")
    without_scheme = gcs_uri.removeprefix("gs://")
    bucket, _, blob = without_scheme.partition("/")
    return bucket, blob


def _extract_from_uri(gcs_uri: str, *, page_offset: int = 0) -> list[ExtractedScriptClaim]:
    # A single types.Content, not a bare list literal -- mypy --strict infers a list
    # mixing a Part and a str as list[object], and list's own invariance means even an
    # explicitly-annotated list[PartUnion] still can't match generate_content's
    # declared (differently-membered) union type. Content is an exact, non-list member
    # of that union, sidestepping the whole list-variance question.
    contents = types.Content(
        role="user",
        parts=[
            types.Part.from_uri(file_uri=gcs_uri, mime_type="application/pdf"),
            types.Part.from_text(text=_prompt()),
        ],
    )
    response = _client().models.generate_content(
        model=EXTRACTION_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ScriptExtraction,
            temperature=EXTRACTION_TEMPERATURE,
            safety_settings=EXTRACTION_SAFETY_SETTINGS,
        ),
    )
    parsed = response.parsed
    if parsed is None:
        return []
    extraction = (
        parsed if isinstance(parsed, ScriptExtraction) else ScriptExtraction.model_validate(parsed)
    )
    for claim in extraction.claims:
        claim.page += page_offset
    return extraction.claims


def _split_chunks(local_path: Path, *, chunk_size: int, overlap: int) -> list[tuple[Path, int]]:
    """Returns [(chunk_pdf_path, first_page_0_based_offset), ...]."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(local_path))
    total = len(reader.pages)
    chunks: list[tuple[Path, int]] = []
    start = 0
    idx = 0
    while start < total:
        end = min(start + chunk_size, total)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        chunk_path = local_path.with_name(f"{local_path.stem}.chunk{idx}.pdf")
        with chunk_path.open("wb") as f:
            writer.write(f)
        chunks.append((chunk_path, start))
        if end == total:
            break
        start = end - overlap
        idx += 1
    return chunks


def _to_domain_claims(
    extracted: list[ExtractedScriptClaim], *, asset_id: str, project: Project
) -> list[Claim]:
    by_id: dict[str, Claim] = {}
    for item in extracted:
        source = SourceRef(
            asset_id=asset_id,
            page=item.page,
            scene_number=item.scene_number,
            scene_heading=item.scene_heading,
            channel=item.channel,
            excerpt=item.excerpt[:500],
        )
        claim = Claim.new(
            project_id=project.project_id,
            studio_id=project.studio_id,
            kind=ClaimKind.LEGAL,
            category=ClaimCategory(item.category),
            entity_text=item.entity_text,
            claim_text=item.claim_text,
            language=item.language,
            source=source,
            jurisdictions=project.distribution_territories,
        )
        # First occurrence wins across chunk overlap. Phase 3.5 (services/ingest) handles
        # the full occurrence-count/all_refs dedupe bookkeeping across the whole asset.
        by_id.setdefault(claim.claim_id, claim)
    return list(by_id.values())


def extract_script_claims(
    gcs_uri: str, *, asset_id: str, project: Project
) -> ScriptExtractionResult:
    """Extract every legal claim from the screenplay PDF at `gcs_uri`, plus the PDF's
    page count (services/ingest writes this to the `assets` row — PHASE_03.md §3.5)."""
    bucket_name, blob_name = _parse_gcs_uri(gcs_uri)
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = Path(tmp_dir) / Path(blob_name).name
        bucket.blob(blob_name).download_to_filename(str(local_path))

        from pypdf import PdfReader

        page_count = len(PdfReader(str(local_path)).pages)

        if page_count <= MAX_SCRIPT_PAGES_PER_CHUNK:
            extracted = _extract_from_uri(gcs_uri)
        else:
            extracted = []
            chunks = _split_chunks(
                local_path,
                chunk_size=MAX_SCRIPT_PAGES_PER_CHUNK,
                overlap=SCRIPT_CHUNK_OVERLAP_PAGES,
            )
            for chunk_path, offset in chunks:
                chunk_blob_name = f"{blob_name}.chunks/{chunk_path.name}"
                chunk_blob = bucket.blob(chunk_blob_name)
                chunk_blob.upload_from_filename(str(chunk_path))
                try:
                    chunk_uri = f"gs://{bucket_name}/{chunk_blob_name}"
                    extracted.extend(_extract_from_uri(chunk_uri, page_offset=offset))
                finally:
                    chunk_blob.delete()

    claims = _to_domain_claims(extracted, asset_id=asset_id, project=project)
    return ScriptExtractionResult(claims=claims, page_count=page_count)
