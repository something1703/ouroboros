"""Live recall tests against real Gemini + real GCS, per PHASE_03.md §3.2's acceptance
criteria: >= 90% recall on the English fixture, >= 80% on the Hindi one, 0 false
positives from the deliberately fictional distractors. Never run in CI (`-m live`,
excluded by `make test`) — needs GOOGLE_CLOUD_PROJECT, real GCS/Vertex AI access, and
costs real (small) money. Run with `make test-live`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from google.cloud import storage

from packages.claims.models import Project
from packages.claims.normalize import normalize_text
from packages.gemini_client.documents import extract_script_claims

pytestmark = pytest.mark.live

_FIXTURES_DIR = Path(__file__).parents[3] / "fixtures" / "scripts"


def _project() -> Project:
    return Project(
        project_id="demo",
        studio_id="studio-demo",
        title="The Long Take",
        distribution_territories=["us", "in"],
        created_at=datetime.now(UTC),
    )


def _upload_fixture(filename: str) -> str:
    bucket_name = os.environ["INTAKE_BUCKET"]
    blob_name = f"scripts/demo/{filename}"
    client = storage.Client()
    blob = client.bucket(bucket_name).blob(blob_name)
    blob.upload_from_filename(str(_FIXTURES_DIR / filename))
    return f"gs://{bucket_name}/{blob_name}"


def _load_labels(filename: str) -> dict[str, object]:
    with (_FIXTURES_DIR / filename).open() as f:
        return yaml.safe_load(f)


def _recall(
    found_normalized_texts: set[str], labels: list[dict[str, str]]
) -> tuple[float, list[str]]:
    missing = [
        label["entity_text"]
        for label in labels
        if normalize_text(label["entity_text"]) not in found_normalized_texts
    ]
    hit_count = len(labels) - len(missing)
    return hit_count / len(labels), missing


def test_english_script_recall_and_no_fictional_false_positives() -> None:
    gcs_uri = _upload_fixture("sample_en.pdf")
    result = extract_script_claims(gcs_uri, asset_id="asset-en-test", project=_project())
    assert result.page_count > 0
    found = {c.normalized_text for c in result.claims}

    labels = _load_labels("sample_en.labels.yaml")
    recall, missing = _recall(found, labels["entities"])  # type: ignore[arg-type]
    assert recall >= 0.9, f"recall {recall:.0%} below 90%; missing: {missing}"

    distractors = labels["fictional_distractors_must_not_appear"]
    false_positives = [d for d in distractors if normalize_text(d) in found]  # type: ignore[union-attr]
    assert not false_positives, f"extracted fictional entities: {false_positives}"


def test_hindi_script_recall() -> None:
    gcs_uri = _upload_fixture("sample_hi.pdf")
    result = extract_script_claims(gcs_uri, asset_id="asset-hi-test", project=_project())
    found = {c.normalized_text for c in result.claims}

    labels = _load_labels("sample_hi.labels.yaml")
    recall, missing = _recall(found, labels["entities"])  # type: ignore[arg-type]
    assert recall >= 0.8, f"recall {recall:.0%} below 80%; missing: {missing}"
