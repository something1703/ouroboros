#!/usr/bin/env python3
"""Upload fixtures/private_corpus/*.txt to GCS and import them into AskOuroboros's
Vertex AI Search datastore (PHASE_08.md §8.4). Idempotent — re-running re-uploads and
re-imports (FULL reconciliation), safe to run again after adding/editing a corpus doc.

Usage: uv run python scripts/ingest_private_corpus.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from google.cloud import discoveryengine_v1 as de
from google.cloud import storage

PROJECT_ID = "ouroboros-507503"
LOCATION = "global"
DATA_STORE_ID = "ouroboros-private-corpus"
BUCKET_NAME = "ouroboros-507503-fixtures"
GCS_PREFIX = "private_corpus"
CORPUS_DIR = Path(__file__).parent.parent / "fixtures" / "private_corpus"


def _upload_corpus(client: storage.Client) -> list[str]:
    bucket = client.bucket(BUCKET_NAME)
    uris = []
    for path in sorted(CORPUS_DIR.glob("*.txt")):
        blob_name = f"{GCS_PREFIX}/{path.name}"
        bucket.blob(blob_name).upload_from_filename(str(path))
        uris.append(f"gs://{BUCKET_NAME}/{blob_name}")
        print(f"uploaded {path.name} -> gs://{BUCKET_NAME}/{blob_name}")
    return uris


def _import_documents(uris: list[str]) -> None:
    client = de.DocumentServiceClient()
    parent = client.branch_path(PROJECT_ID, LOCATION, DATA_STORE_ID, "default_branch")
    request = de.ImportDocumentsRequest(
        parent=parent,
        gcs_source=de.GcsSource(input_uris=uris, data_schema="content"),
        reconciliation_mode=de.ImportDocumentsRequest.ReconciliationMode.FULL,
    )
    operation = client.import_documents(request=request)
    print(f"import started: {operation.operation.name}")
    result = operation.result(timeout=300)
    print(f"import complete: {result}")


def main() -> int:
    if not CORPUS_DIR.exists() or not any(CORPUS_DIR.glob("*.txt")):
        print(f"no .txt files found in {CORPUS_DIR}", file=sys.stderr)
        return 1

    storage_client = storage.Client(project=PROJECT_ID)
    uris = _upload_corpus(storage_client)
    _import_documents(uris)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
