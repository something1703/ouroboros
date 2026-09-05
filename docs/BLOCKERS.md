# BLOCKERS.md

The coding agent records anything it cannot resolve alone here, then moves on to the next unblocked sub-phase.

Format per entry:

```
## [PHASE x.y] <short title>            (opened: YYYY-MM-DD HH:MM IST)
**Tried:** what was attempted
**Error / gap:** exact message or missing input
**Need from human:** the specific thing (credential, decision, file, approval)
**Status:** open | resolved (date)
```

## [PHASE 1.1] GitHub repo visibility unconfirmed            (opened: 2026-09-03 09:30 IST)
**Tried:** `git ls-remote` and `git clone` against `https://github.com/something1703/ouroboros.git` — succeeded via a credential already saved in the local macOS keychain, confirming push access and that the repo is empty. An anonymous (unauthenticated) call to `https://api.github.com/repos/something1703/ouroboros` returned 404.
**Error / gap:** A 404 on the anonymous API call is consistent with the repo being private (or not yet indexed); I have no GitHub API token to check `visibility` directly, and I should not extract one from the keychain without being asked.
**Need from human:** Confirm in GitHub → repo → Settings → General that visibility is **Public**, and that a license shows in the About sidebar once `LICENSE` is pushed (hackathon rule: repo must be public with a visible OSI license).
**Status:** open

---
## [PHASE 1.8] Parallel balance check needs OAuth, not the API key            (opened: 2026-09-03 10:50 IST)
**Tried:** Fetched `docs.parallel.ai/service-api/balance/get-balance.md` — `GET https://api.parallel.ai/account/service/v1/balance`.
**Error / gap:** The docs state the required header is "an account API access token minted via a supported Parallel OAuth grant, not a standard API key." Our `PARALLEL_API_KEY` (an integration key) cannot call this endpoint — it needs an interactive OAuth device-flow login (`rote login`-style or the Parallel dashboard's own auth), which an automated agent shouldn't attempt on your behalf.
**Need from human:** Check your credit balance directly at platform.parallel.ai (Settings → Billing) when convenient. Not blocking — the pipeline never needs this endpoint at runtime, only the per-project cost meter (`packages/parallel_client/cost.py`, Phase 4) does real budget enforcement.
**Status:** open (low priority)

---
## [PHASE 1.3] Agent sandbox can't reach *.run.app URLs directly            (opened: 2026-09-03 11:20 IST)
**Tried:** Deployed a temporary `hello` Cloud Run service and attempted to hit it (both `/healthz` and via `gcloud run services proxy`) from this agent's Bash tool, using `httpx` (raw `curl` with an `Authorization` header is separately blocked by this sandbox, which redirects to a `rote` wrapper tool of unknown provenance — declined to route secrets through it).
**Error / gap:** Every request to the real, DNS-resolving, healthy `*.run.app` URL returned Google's generic "no backend" 404 page, with zero corresponding entries in the container's own request logs — consistent with a network boundary in this harness's Bash sandbox (not a problem with the deployment; `gcloud run revisions describe` confirmed the container built, started, and passed health checks in 9.4s). Compensated with equivalent local verification of the same Parallel + Gemini calls (see `docs/evidence/01-hello.md`).
**Need from human:** Nothing blocking. If you want to click through the deployed-service path yourself in a future phase (dashboard, webhook receiver, etc.), test from your own terminal/browser, not by asking the agent to curl a `*.run.app` URL — expect the same restriction to reappear whenever real Cloud Run URL testing is needed, and plan to do that verification step yourself or paste results back.
**Status:** open (informational — does not block product work, only affects how *this agent* verifies deployed HTTP endpoints)

---
## [PHASE 7.1] Parallel webhook signing secret is dashboard-only, no API access            (opened: 2026-09-05 13:20 IST)
**Tried:** Fetched `docs.parallel.ai/resources/webhook-setup.md` to find how to retrieve the webhook signing secret `packages/parallel_client/webhooks.py::verify_signature` needs. The docs are explicit: "Go to Settings → Webhooks to view your account webhook secret" — it's a single, account-level secret (format `whsec_...`), shown only in the Parallel account dashboard, never returned by any API call (not from Monitor/Task creation, not from any endpoint I can reach with `PARALLEL_API_KEY`).
**Error / gap:** No programmatic path exists to read this value — it requires an interactive login to platform.parallel.ai, the same category of "needs a human at the dashboard" gap as the earlier balance-check blocker (§1.8).
**Need from human:** Log into platform.parallel.ai → Settings → Webhooks, copy the account webhook secret, and either (a) set it directly in Secret Manager (`gcloud secrets versions add PARALLEL_WEBHOOK_SECRET --data-file=-`) or (b) paste it here so it can be set for you. Until then, `services/webhook_receiver` has a **placeholder** secret set (see `docs/DECISIONS.md` #094) so the rest of the loop (Pub/Sub → reverify_worker → risk/drift/Slack) can be verified end-to-end via `make replay-webhook`, but any *real* Parallel-originated webhook will 401 until the real secret is set.
**Status:** open

---
All of §A (A1–A6) resolved 2026-09-03: project `ouroboros-507503`, IAM owner confirmed, region `us-central1`, Parallel API key stored in Secret Manager, repo URL supplied, BYOK decided. See `docs/DECISIONS.md` #015.
