# Phase 3.2 — script extraction recall evidence

Both fixtures are agent-authored synthetic screenplays (see `docs/DECISIONS.md` #025) —
short, but dense with real entities across every `ClaimCategory`, plus deliberate
fictional distractors (a script-labelled-fictional cafe, fictional character names) to
test false-positive avoidance, not just recall.

## English (`fixtures/scripts/sample_en.pdf`, 4 pages)

`uv run --env-file .env pytest tests/packages/gemini_client/ -m live -v`:

```
test_english_script_recall_and_no_fictional_false_positives PASSED
```

17/17 labelled entities found (**100% recall**, target >= 90%). 0 of the 4 fictional
distractors (`Cafe Lumiere`, `Maya Chen`, `Priya Sharma`, `Albert Weiss`) were extracted.

The model also correctly surfaced several claims beyond the strict label list (not
counted toward recall, but a sign of real understanding, not pattern-matching against the
labels): `MacBook Pro` alongside `Apple`, `Queen` alongside `Bohemian Rhapsody`, `Vincent
van Gogh` alongside `The Starry Night`, `Hamlet` as its own artwork claim distinct from
the Shakespeare quote, and `Coke` as a second surface form of `Coca-Cola` (a dedupe
concern for Phase 3.5, not an extraction miss).

## Hindi (`fixtures/scripts/sample_hi.pdf`, 2 pages)

```
test_hindi_script_recall PASSED
```

6/7 labelled entities found (**85.7% recall**, target >= 80%). Missed: `Mumbai` (only
appears in spoken Hindi narration, not a scene heading or action line). Per-excerpt
language tagging is correct, not just per-file: entities mentioned in English action
lines/scene headings within the Hindi script (`India Gate`, `Vande Mataram`, `Amul`) are
tagged `lang=en`; entities in Devanagari dialogue (`Amitabh Bachchan`, `Tata Motors`) are
tagged `lang=hi` — confirming the model discriminates language per excerpt rather than
inheriting the source file's dominant language.

## Two real bugs found and fixed while getting this working

1. **`genai.Client` garbage-collected mid-request** — an unbound client
   (`_client().models.generate_content(...)`) raised `RuntimeError: Cannot send a
   request, as the client has been closed` reproducibly. Fixed by caching the client
   (`@functools.cache`). See `docs/DECISIONS.md` #026.
2. **Vertex AI's own service agent lacked GCS read access** — `403 PERMISSION_DENIED`
   from `service-<project-number>@gcp-sa-aiplatform.iam.gserviceaccount.com`, not from my
   own identity. Fixed permanently via Terraform (`infra/modules/storage`), not a one-off
   grant. See `docs/DECISIONS.md` #027.
