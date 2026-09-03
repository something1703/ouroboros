"""Gemini video understanding: rough cut -> factual (+ visual legal) Claim[]. See PHASE_03.md §3.3.

Structurally complete but **not yet verified against a real video file** — no sample cut
exists yet (docs/DECISIONS.md; the human said they'll provide one later). Mirrors
documents.py's chunking/merge shape as closely as the two domains allow; ffmpeg-based
chunking in particular needs a real multi-chunk video to exercise. Treat any change here
as needing a fresh live pass against `fixtures/cuts/sample.mp4` once it exists, per
PHASE_03.md §3.3's acceptance criteria.
"""

from __future__ import annotations

import os
import subprocess
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
    MAX_VIDEO_MINUTES_PER_CHUNK,
    VIDEO_CHUNK_OVERLAP_SECONDS,
)
from packages.claims.enums import ClaimCategory, ClaimKind
from packages.claims.models import Claim, Project, SourceRef
from packages.common.logging import get_logger
from packages.gemini_client.schemas import CutExtraction, ExtractedCutClaim

_PROMPT_PATH = Path(__file__).parent / "prompts" / "cut_extraction.md"
_LEGAL_VISUAL_CATEGORIES = {"brand", "person", "artwork"}


@dataclass(frozen=True)
class CutExtractionResult:
    claims: list[Claim]
    duration_ms: int


log = get_logger(__name__)


def _prompt() -> str:
    return _PROMPT_PATH.read_text()


@cache
def _client() -> genai.Client:
    # See documents.py — an uncached genai.Client() was observed to be GC'd mid-request.
    return genai.Client(vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT"))


def _parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"expected a gs:// URI, got {gcs_uri!r}")
    without_scheme = gcs_uri.removeprefix("gs://")
    bucket, _, blob = without_scheme.partition("/")
    return bucket, blob


def _video_duration_seconds(local_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(local_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def _split_chunks(
    local_path: Path, *, chunk_seconds: int, overlap_seconds: int
) -> list[tuple[Path, int]]:
    """Returns [(chunk_video_path, start_offset_seconds), ...]. Re-encodes each window
    with ffmpeg (not stream-copy) so every chunk starts on a keyframe — a copy-mode cut
    at an arbitrary timestamp can produce an unplayable or misaligned first fraction of
    a second, which would silently skew every claim timestamp in that chunk."""
    total = _video_duration_seconds(local_path)
    chunks: list[tuple[Path, int]] = []
    start = 0.0
    idx = 0
    while start < total:
        end = min(start + chunk_seconds, total)
        chunk_path = local_path.with_name(f"{local_path.stem}.chunk{idx}{local_path.suffix}")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(start),
                "-i",
                str(local_path),
                "-t",
                str(end - start),
                str(chunk_path),
            ],
            capture_output=True,
            check=True,
        )
        chunks.append((chunk_path, int(start)))
        if end >= total:
            break
        start = end - overlap_seconds
        idx += 1
    return chunks


def _extract_from_uri(gcs_uri: str, *, mime_type: str) -> CutExtraction:
    response = _client().models.generate_content(
        model=EXTRACTION_MODEL,
        contents=[
            types.Part.from_uri(file_uri=gcs_uri, mime_type=mime_type),
            _prompt(),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CutExtraction,
            temperature=EXTRACTION_TEMPERATURE,
            safety_settings=EXTRACTION_SAFETY_SETTINGS,
        ),
    )
    parsed = response.parsed
    if parsed is None:
        return CutExtraction(segments=[], claims=[])
    return parsed if isinstance(parsed, CutExtraction) else CutExtraction.model_validate(parsed)


def _rebase(claims: list[ExtractedCutClaim], *, offset_ms: int) -> list[ExtractedCutClaim]:
    for claim in claims:
        claim.t_start_ms += offset_ms
        claim.t_end_ms += offset_ms
    return claims


def _to_domain_claims(
    extracted: list[ExtractedCutClaim], *, asset_id: str, project: Project
) -> list[Claim]:
    by_id: dict[str, Claim] = {}
    for item in extracted:
        source = SourceRef(
            asset_id=asset_id,
            t_start_ms=item.t_start_ms,
            t_end_ms=item.t_end_ms,
            channel=item.channel,
            excerpt=item.excerpt[:500],
        )
        kind = ClaimKind.LEGAL if item.category in _LEGAL_VISUAL_CATEGORIES else ClaimKind.FACTUAL
        claim = Claim.new(
            project_id=project.project_id,
            studio_id=project.studio_id,
            kind=kind,
            category=ClaimCategory(item.category),
            entity_text=item.entity_text,
            claim_text=item.claim_text,
            language=item.language,
            source=source,
            jurisdictions=project.distribution_territories,
        )
        # First occurrence wins across chunk overlap, same as documents.py; the full
        # occurrence-count/all_refs dedupe lives in services/ingest (PHASE_03.md §3.5).
        by_id.setdefault(claim.claim_id, claim)
    return list(by_id.values())


def extract_cut_claims(gcs_uri: str, *, asset_id: str, project: Project) -> CutExtractionResult:
    """Extract every factual (+ visual legal) claim from the rough cut at `gcs_uri`, plus
    its duration in ms (services/ingest writes this to the `assets` row — PHASE_03.md §3.5)."""
    bucket_name, blob_name = _parse_gcs_uri(gcs_uri)
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    suffix = Path(blob_name).suffix or ".mp4"
    mime_type = "video/quicktime" if suffix == ".mov" else "video/mp4"

    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = Path(tmp_dir) / Path(blob_name).name
        bucket.blob(blob_name).download_to_filename(str(local_path))

        duration_seconds = _video_duration_seconds(local_path)
        max_chunk_seconds = MAX_VIDEO_MINUTES_PER_CHUNK * 60

        if duration_seconds <= max_chunk_seconds:
            extraction = _extract_from_uri(gcs_uri, mime_type=mime_type)
            all_claims = list(extraction.claims)
        else:
            all_claims = []
            chunks = _split_chunks(
                local_path,
                chunk_seconds=max_chunk_seconds,
                overlap_seconds=VIDEO_CHUNK_OVERLAP_SECONDS,
            )
            for chunk_path, offset_seconds in chunks:
                chunk_blob_name = f"{blob_name}.chunks/{chunk_path.name}"
                chunk_blob = bucket.blob(chunk_blob_name)
                chunk_blob.upload_from_filename(str(chunk_path))
                try:
                    chunk_uri = f"gs://{bucket_name}/{chunk_blob_name}"
                    extraction = _extract_from_uri(chunk_uri, mime_type=mime_type)
                    all_claims.extend(_rebase(extraction.claims, offset_ms=offset_seconds * 1000))
                finally:
                    chunk_blob.delete()

    claims = _to_domain_claims(all_claims, asset_id=asset_id, project=project)
    return CutExtractionResult(claims=claims, duration_ms=int(duration_seconds * 1000))
