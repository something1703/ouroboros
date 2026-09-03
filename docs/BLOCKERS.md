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
All of §A (A1–A6) resolved 2026-09-03: project `ouroboros-507503`, IAM owner confirmed, region `us-central1`, Parallel API key stored in Secret Manager, repo URL supplied, BYOK decided. See `docs/DECISIONS.md` #015.
