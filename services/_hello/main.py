"""Temporary Phase 1.3 smoke test service. Deployed once, screenshotted, deleted.

Proves the runtime path works end to end: Cloud Run -> Secret Manager (PARALLEL_API_KEY)
-> Parallel Search, and Cloud Run -> Vertex AI -> Gemini. Not part of the product.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from google import genai
from parallel import Parallel

from packages.common.secrets import get_secret

app = FastAPI()


@app.get("/status")
def status() -> dict[str, object]:
    return {"ok": True, "service": "_hello"}


@app.get("/")
def hello() -> dict[str, object]:
    parallel_client = Parallel(api_key=get_secret("PARALLEL_API_KEY"))
    search_result = parallel_client.search(
        objective="Who founded Parallel Web Systems?",
        search_queries=["Parallel Web Systems founder"],
        mode="turbo",
        advanced_settings={"max_results": 2},
    )

    gemini_client = genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
    )
    gemini_response = gemini_client.models.generate_content(
        model="gemini-3.5-flash", contents="say ok"
    )

    return {
        "ok": True,
        "parallel_search": {
            "top_result_title": search_result.results[0].title if search_result.results else None,
            "top_result_url": search_result.results[0].url if search_result.results else None,
            "result_count": len(search_result.results),
        },
        "gemini": {"text": gemini_response.text},
    }
