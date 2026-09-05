"""Structured-output schemas for Gemini extraction. Passed directly as `response_schema` —
google-genai converts a Pydantic BaseModel to the JSON schema Gemini expects."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Legal categories only — a screenplay makes legal claims (ARCHITECTURE.md §1).
ScriptClaimCategory = Literal["music", "brand", "person", "location", "artwork", "quote"]
Channel = Literal["dialogue", "action_line"]


class ExtractedScriptClaim(BaseModel):
    category: ScriptClaimCategory
    entity_text: str = Field(
        description="Canonical surface form, e.g. 'Coca-Cola', 'Bohemian Rhapsody'"
    )
    claim_text: str = Field(description="One sentence describing the claim in context")
    page: int = Field(description="The PDF page index this appears on — never invented")
    scene_number: str | None = Field(
        default=None, description="Scene number if the script has one, else null"
    )
    scene_heading: str | None = Field(
        default=None, description="e.g. 'INT. KITCHEN - MORNING', else null"
    )
    channel: Channel
    excerpt: str = Field(
        description="Verbatim source text, at most 500 characters, in its original language"
    )
    language: str = Field(description="BCP-47 language tag of the excerpt, e.g. 'en', 'hi'")


class ScriptExtraction(BaseModel):
    claims: list[ExtractedScriptClaim]


# Factual categories, plus the three legal categories that also apply to what's visually
# on screen (ARCHITECTURE.md §1 — a cut can show a real brand/person/artwork even if the
# script never named one explicitly).
CutClaimCategory = Literal[
    "event", "statistic", "attribution", "archival", "identity", "brand", "person", "artwork"
]
CutChannel = Literal["narration", "dialogue", "on_screen_text", "visual"]


class TranscriptSegment(BaseModel):
    t_start_ms: int = Field(description="Segment start, milliseconds from the start of this chunk")
    t_end_ms: int = Field(description="Segment end, milliseconds from the start of this chunk")
    speaker: str | None = Field(default=None, description="Speaker label, else null for narration")
    transcript: str = Field(description="Verbatim spoken/on-screen text for this segment")


class ExtractedCutClaim(BaseModel):
    category: CutClaimCategory
    entity_text: str = Field(description="Canonical surface form, e.g. 'Coca-Cola', 'Apollo 11'")
    claim_text: str = Field(description="One sentence describing the claim in context")
    channel: CutChannel
    t_start_ms: int = Field(description="Claim start, milliseconds from the start of this chunk")
    t_end_ms: int = Field(description="Claim end, milliseconds from the start of this chunk")
    excerpt: str = Field(
        description="Verbatim narration/dialogue/on-screen text that produced the claim, "
        "at most 500 characters, in its original language"
    )
    language: str = Field(description="BCP-47 language tag of the excerpt, e.g. 'en', 'hi'")
    archival: bool = Field(
        default=False, description="True if the footage looks historical or third-party sourced"
    )


class CutExtraction(BaseModel):
    segments: list[TranscriptSegment]
    claims: list[ExtractedCutClaim]
