# OUROBOROS — Planning Package

> **Research that feeds itself.** A self-verifying production-intelligence agent for film & TV, built on Google Cloud's Gemini Enterprise Agent Platform with Parallel Web Systems as the research layer.
>
> Hackathon: *Agentic Cinema: The Blockbuster Hackathon* — **Parallel track**. Deadline: **10 Sept 2026, 02:30 IST**.

This folder is the complete build plan. It is written to be handed, file by file, to a coding agent. **No code has been written yet.** Every document is a contract the code must satisfy.

---

## How to use this package

1. Read `AGENTS.md` first — it is the operating manual for the coding agent (conventions, repo layout, guardrails, definition of done).
2. Read `00_REQUIREMENTS_FROM_USER.md` — it lists every credential, account, file and decision the human must supply. Nothing in Phase 1 can start until the "Blocking" items are provided.
3. Read `ARCHITECTURE.md`, `DATA_MODEL.md`, `ADK_AGENTS.md`, `PARALLEL_INTEGRATION.md` — these are the cross-cutting contracts. Phases reference them; they do not repeat them.
4. Execute `phases/PHASE_01.md` → `phases/PHASE_10.md` in order. Each phase has sub-phases, acceptance criteria, and an explicit **exit gate**. Do not start phase N+1 until phase N's exit gate passes.

## File map

| File | Purpose |
|---|---|
| `AGENTS.md` | Coding-agent operating manual: stack, repo layout, conventions, commands, guardrails, definition of done |
| `00_REQUIREMENTS_FROM_USER.md` | Everything the human must provide or decide, grouped by phase and blocking status |
| `ARCHITECTURE.md` | System architecture, component responsibilities, data flow, the three Ouroboros loops, non-functional requirements |
| `DATA_MODEL.md` | Claim schema, Task output schemas, Cloud SQL / Firestore / BigQuery schemas, Reality Drift formula |
| `ADK_AGENTS.md` | Runtime agent catalog: every ADK agent, its tools, inputs, outputs, instructions skeleton, state keys |
| `PARALLEL_INTEGRATION.md` | Exact usage contracts for every Parallel API we call, cost guardrails, mode selection rules, error handling |
| `phases/PHASE_01.md` | Foundation: GCP project, IAM, secrets, repo scaffold, CI, Parallel account, local dev loop |
| `phases/PHASE_02.md` | Claim Ledger: Cloud SQL, MCP Toolbox for Databases, Firestore, BigQuery, migrations |
| `phases/PHASE_03.md` | Ingest: GCS → Eventarc → Cloud Run, Gemini document/video understanding, Model Armor, claim extraction |
| `phases/PHASE_04.md` | Parallel integration layer: typed clients, Task specs, Basis parsing, cost meter, fixtures |
| `phases/PHASE_05.md` | CLEAR head: ADK multi-agent system on Agent Engine, fan-out, risk, reporting |
| `phases/PHASE_06.md` | TRUE CUT head: factual-claim verification, Responses API, Task escalation, Extract, timeline |
| `phases/PHASE_07.md` | The Ouroboros loop: Monitors, webhooks, Pub/Sub, re-verification, coil tightening, memory, Reality Drift |
| `phases/PHASE_08.md` | Dashboard & governance: Cloud Run UI, IAP roles, heatmap, timeline, feed, exports, Slack, grounded Q&A |
| `phases/PHASE_09.md` | Quality: golden set, Vertex evaluation, security hardening, observability, cost/load tests |
| `phases/PHASE_10.md` | Remediation (stretch), demo video, README, license, Devpost submission |

## The 10-day calendar (deadline 10 Sept, 02:30 IST)

| Day | Date | Phases |
|---|---|---|
| 1 | 31 Aug | Phase 1 (all), Phase 2.1–2.2 |
| 2 | 1 Sep | Phase 2 (finish), Phase 3.1–3.3 |
| 3 | 2 Sep | Phase 3 (finish), Phase 4 (all) |
| 4 | 3 Sep | Phase 5.1–5.4 |
| 5 | 4 Sep | Phase 5 (finish), Phase 6.1–6.2 |
| 6 | 5 Sep | Phase 6 (finish), Phase 7.1–7.3 |
| 7 | 6 Sep | Phase 7 (finish), Phase 8.1–8.3 |
| 8 | 7 Sep | Phase 8 (finish), Phase 9 (all) |
| 9 | 8 Sep | Phase 10.1–10.3 (remediation only if 1–9 green), demo recording |
| 10 | 9 Sep | Phase 10.4–10.6: README, license, submission by **22:00 IST** (4.5h buffer) |

**Critical rule:** the Monitor loop (Phase 7) must be live by the end of Day 6 so that by judging time the demo project has visibly re-verified itself many times. This is the single most important differentiator.

## Non-negotiables (from the Official Rules)

- Hosted project URL.
- ≤3-minute demo video on YouTube/Vimeo, public, English or English subtitles, showing the agent **functioning as built**.
- Public repo (GitHub/GitLab/Bitbucket) with **all source, assets, run instructions**, and an **OSI license file visible in the About section**.
- Repo must demonstrate **runtime** use of Google Cloud and of **Parallel's Search API** — imported and called in code, not just named in the README.
- Select the **Parallel** partner track on Devpost.
