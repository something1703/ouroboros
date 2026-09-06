# Phase 9.1 — Golden-set evaluation evidence

`evals/golden/{legal,factual}.yaml` (25 + 25 claims) run through the real specialist
code paths — `agents.ouroboros.clear.specialist.verify_batch` and
`agents.ouroboros.truecut.fact.verify_fact_batch`, the exact same functions the
deployed CLEAR/TRUE CUT pipelines call, not a reimplementation — via
`evals/run_golden.py`, against real Parallel API calls (core-fast, escalating to pro
per each path's own real rules) and a real local Postgres + Toolbox
(`docker compose up -d postgres toolbox`, `alembic upgrade head`).

## Results (2026-09-06)

| Metric | Legal | Factual |
|---|---|---|
| Field/verdict accuracy | **92%** (23/25) | **88%** (22/25) |
| Citation presence | 92% | 100% |
| High-confidence precision | **94%** (16 high) | 88% (25 high) |
| Total cost | $0.600 | $1.350 |
| Avg latency/claim | 3.2s | 1.7s |
| Errors | 0 | 0 |

**Acceptance bar:** field accuracy ≥ 85% legal (✅ 92%), verdict accuracy ≥ 85%
factual (✅ 88%), high-confidence precision ≥ 90% — legal clears it (✅ 94%), factual
falls just short (❌ 88%, 22/25 correct among 25 "high"-confidence claims). Raw
results: `evals/results/2026-09-06.json`.

**Note on reproducibility:** the golden set was re-run once more (same day) after an
unrelated offline `pytest` run truncated the local dev database (a real, LLM-driven
process, so re-runs aren't bit-identical): 88% legal / 96% factual accuracy, 92%/100%
citation presence, 88%/96% high-confidence precision. Same story — both domains clear
their primary accuracy bar every time; the high-confidence-precision bar (≥90%) sits
close enough to the line that which domain clears it can flip run to run. The
per-miss analysis below is from the original run whose exact numbers are quoted in
the table above.

## A real bug caught before it skewed the numbers

The first full run showed legal at 60% accuracy with **10 of 25 claims erroring**
`secret not found: PARALLEL_API_KEY`. All 10 failures were legal claims fired in the
very first concurrent burst (25 claims at once via `asyncio.gather`); factual (which
ran second) had zero errors. Root cause: `packages/common/secrets.py::get_secret` is
`@lru_cache`d, but the *first* burst of concurrent `asyncio.to_thread` calls all race
to populate that cache simultaneously, and a concurrent Secret Manager error during
that race gets mapped to a generic `NotFound` ("secret not found") regardless of the
real underlying cause — misleading at first glance, since the secret obviously
exists (it's used everywhere else in this repo). Fixed by priming the cache once,
synchronously, before any concurrent work starts (`evals/run_golden.py::main`).
Re-running with the fix: 0 errors in both domains, and the legal score moved to its
real value (92%, not 60%) — the original 60% was pure infra noise, not specialist
quality.

## Every miss, inspected

**Legal (2 misses / 25):**
- `legal-music-04` (Bohemian Rhapsody) — expected `composition_rights_holder`
  containing "Sony"; got `"EMI Glenwood Music Corp. o/b/o Queen Music Ltd."` — EMI
  Music Publishing was acquired by Sony in 2018 but still operates under its own
  name for catalog administration. Arguably a **golden-set labeling issue**, not a
  system error — the system's answer is more precise than my expected substring.
- `legal-music-05` (Beethoven's Symphony No. 9) — expected `is_public_domain: true`;
  got `false`, but the same evidence's own `territory_notes` field says *"the
  composition is in the public domain, but any modern recording is copyrighted and
  requires clearance"* — the claim text described a filmed *performance*, and the
  system reasonably flagged that a recording/performance carries separate rights
  even though the underlying composition is PD. Also arguably a **golden-set
  oversimplification** (a single boolean can't capture composition-PD vs.
  recording-not-PD).

**Factual (3 misses / 25):**
- `factual-statistic-02` (world population passed 8 billion in 2022) — expected
  `supported`; got `unverifiable`, high confidence. This one looks like a genuine
  **system under-confidence** case worth a closer look (the fact is well-documented:
  the UN's own "Day of 8 Billion," Nov 15, 2022).
- `factual-attribution-03` (Edison invented the light bulb) — expected
  `partially_supported`; got `contradicted`. Both are defensible for a claim this
  historically contested (multiple prior inventors); a coin-flip case I chose
  deliberately to test nuance, not a clean miss.
- `factual-attribution-07` (Declaration of Independence signed in 1776) — expected
  `partially_supported` (nitpicking adoption-vs-signing dates); got `supported`,
  which is arguably *more* correct since the claim only asserts the year. Likely a
  **golden-set labeling issue**.

Net: 3 of the 5 misses look like golden-set labeling imprecision on inspection, not
specialist errors — logged in `docs/BLOCKERS.md` as a human spot-check request
(PHASE_09.md's own suggested process for exactly this disagreement class) rather than
silently relabeling the golden set to inflate the score.

## Coverage

- Legal: 5 claims each across music/brand/person/location/artwork (the four
  categories with a real Task spec — `quote` has none yet, excluded).
- Factual: 9 event, 8 statistic, 8 attribution claims.
- Jurisdictions mixed per PHASE_09.md §9.1: `us, gb, in, de, jp` plus a few others
  (`fr, es, nl, no, np, cn, br, pl, it`) for claims where a more specific real
  jurisdiction made sense.
- 5 non-English claim texts (3 Hindi, 2 Spanish) — real translations of otherwise
  English-language golden cases, not separate claims.
