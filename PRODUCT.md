# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Three internal, role-gated users at a film/TV studio: **legal** (rights/clearance, overrides `kind=legal` claims), **editorial** (factual accuracy, overrides `kind=factual` claims), and **producer** (oversight, read-only — never overrides, exports only). They verify legal and factual claims made in a production's script and cut before theatrical/streaming release, across multiple shooting countries and distribution territories, under a fixed per-project budget cap.

Near-term, the actual audience judging this specific build is the *Agentic Cinema* hackathon's judges, evaluating it via a live demo project and a ≤3-minute video before the 10 Sept 2026, 02:30 IST deadline (`README.md`). Confirmed by the user: for this redesign pass, design priority favors that judged first impression over incremental day-to-day operate efficiency (see Product Principles).

Added 2026-09-06: a second audience now exists ahead of the sign-in wall — a public visitor (a judge exploring the live URL directly, a prospective studio evaluator, anyone following the repo link) who has never signed in and needs to understand what Ouroboros is, why it exists, and how the loop works, from the marketing site alone.

## Product Purpose

Ouroboros ("research that feeds itself") continuously re-verifies legal and factual claims made in a production's script and cut against the live world, catching *risk drift* — a claim that was true when written becoming false, disputed, or newly risky — before release. Success is a project whose claims stay verified all the way to release, not just at ingest.

## Positioning

Unlike point-in-time clearance/fact-checking tools, Ouroboros's Monitors keep re-checking claims against live web sources on an accelerating cadence (`1w → 1d → 1h`, "the coil") as release approaches, surfacing a project-wide **Reality Drift** score and an event feed that proves the system kept re-verifying itself — including visibly continuing after the hackathon submission deadline (`SUBMISSION_AT`).

## Operating Context

Studio users sign in via Google Identity Services (no Cloud IAP — no GCP Organization exists for this project, `docs/DECISIONS.md` #104) and work inside per-project views: script risk heatmap, video claim timeline, live Ouroboros feed, Reality Drift gauge, grounded Q&A, and E&O-grade exports. Built on Cloud Run, Vertex Agent Engine, and Parallel's Search/Task/Monitor APIs. Claims carry jurisdiction, risk level, verification status, and a full evidence/citation history.

Added 2026-09-06: the web app now serves two distinct surfaces at two distinct route roots — a public marketing site (`/`, `/how-it-works`, `/resources`, `/docs/*`, no auth wall) and the authenticated dashboard (moved to `/app`, everything already built in Phases 8.1–8.3, GIS sign-in unchanged). Confirmed by the user: docs go deep — real in-app documentation pages under `/docs`, not just outbound links to the GitHub repo.

## Capabilities and Constraints

- Three enforced roles: `legal` overrides `kind=legal` claims, `editorial` overrides `kind=factual` claims, `producer` is read-only everywhere (exports only).
- "Run CLEAR" / "Run TRUE CUT" / "Trigger monitors" are real, billed Vertex Agent Engine / Parallel calls against a fixed per-project `budget_cap_usd` — role gates must be enforced server-side, not just hidden in the UI (a real gap already found and fixed once this phase, `docs/DECISIONS.md` #109).
- Must demonstrably run on Google Cloud and call Parallel's Search API at runtime, verifiable in the submitted public repo (`README.md`'s Non-negotiables).
- Must pass Lighthouse a11y ≥ 90 and work correctly at 1280px and 390px with zero console errors (`phases/PHASE_08.md` §8.2 acceptance criteria).

## Brand Commitments

Name **Ouroboros**. An original, hand-drawn-then-vectorized two-snake infinity-loop mark in brand orange `#FB631B` (`web/public/logo.svg`, `favicon.svg`), already designed and user-approved this session. A dark-editorial palette and Fraunces (display) / IBM Plex Sans (body) / IBM Plex Mono (IDs, timecodes, cadence badge, and other measurement/data values — percentages, currency, counts) type system is already committed as the single visual identity — these are binding, not open for this redesign to replace (see Product Principles). Amended 2026-09-06 during the 8.2 redesign's finish review: the mono scope was originally worded narrower than what was already legitimately in use (the Reality Drift ring's percentage, spend, days-to-release) — this line now matches actual practice rather than the practice silently drifting from the doc.

## Evidence on Hand

A real, live demo project seeded in the deployed system (`project_id: demo`, "Demo Film"). A real deployed `dashboard-api` at `https://dashboard-api-492372502792.us-central1.run.app`. No existing user research, testimonials, benchmarks, or case studies exist — do not fabricate any.

## Product Principles

1. Design must read as impressive to a judge watching a ≤3-minute demo video first, before it reads as an efficient daily tool — the user's explicit priority call for this pass.
2. Never let a quick action's role gate be cosmetic: whatever the UI hides, the API must also refuse.
3. The Reality Drift gauge and monitor-cadence badge are the product's actual differentiator (continuous, accelerating re-verification) — they must never read as a decorative afterthought.
4. Prefer showing real data from the real deployed API over mocked or static content, matching how the rest of this project has always verified itself.
5. Preserve the already-committed dark-editorial brand identity (palette, type system, mark) — this redesign means layout, hierarchy, and craft, not a new visual world.
6. Added 2026-09-06: the marketing site earns attention through real mechanism and real craft, never fabricated proof — no invented customer logos, testimonials, usage numbers, or pricing. What it can show honestly: the real Reality Drift/coil concept, the real architecture (Gemini + Parallel + Google Cloud), and real links to the real public repo.

## Accessibility & Inclusion

`phases/PHASE_08.md` §8.2 sets Lighthouse a11y ≥ 90 as an explicit, scored acceptance bar; must remain fully usable at 1280px and 390px with zero console errors.
