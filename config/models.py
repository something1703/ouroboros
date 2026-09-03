"""Gemini model IDs, temperatures, and safety settings. The single source of truth — no model ID string appears anywhere else in the codebase."""

from __future__ import annotations

from google.genai import types

# Model IDs
EXTRACTION_MODEL = "gemini-3.5-flash"
REASONING_MODEL = "gemini-3.1-pro-preview"
GROUNDING_MODEL = "gemini-3.5-flash"

# Temperatures
EXTRACTION_TEMPERATURE = 0.1
REASONING_TEMPERATURE = 0.3

# Safety settings: scripts legitimately contain violence/profanity/drugs — block
# only HIGH severity so extraction doesn't crash on ordinary screenplay content.
# Blocked responses are recorded (asset notes / claim safety_flags), never silently dropped.
EXTRACTION_SAFETY_SETTINGS: list[types.SafetySetting] = [
    types.SafetySetting(
        category=category,
        threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    )
    for category in (
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
    )
]

# Gemini per-1M-token pricing (USD), for the cost meter's token-based estimate.
# Source: Vertex AI Gemini pricing, checked 2026-08-31. Update alongside any model change.
GEMINI_PRICE_PER_1M_TOKENS_USD: dict[str, dict[str, float]] = {
    "gemini-3.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 5.00},
}

# Video/document chunking thresholds
MAX_SCRIPT_PAGES_PER_CHUNK = 40
SCRIPT_CHUNK_OVERLAP_PAGES = 2
MAX_VIDEO_MINUTES_PER_CHUNK = 20
VIDEO_CHUNK_OVERLAP_SECONDS = 30
