# Phase 3.1 / 3.5 — ingest pipeline evidence

`services/ingest` deployed to Cloud Run (`sa-ingest`, private/internal ingress only,
invoked exclusively by the Eventarc trigger's own identity — never
`--allow-unauthenticated`), triggered by a direct Cloud Storage Eventarc trigger on
`ouroboros-507503-intake-dev`'s `object.finalized` event.

## Real upload, real end-to-end run

```
$ gsutil cp fixtures/scripts/sample_en.pdf gs://ouroboros-507503-intake-dev/scripts/demo/sample_en.pdf
```

Cloud Run request logs (`run.googleapis.com/requests`) show 4 POSTs for this one upload —
Eventarc/Pub/Sub redelivered the event 3 times because the handler's first run (real
Gemini extraction) took longer than the underlying push subscription's ack deadline:

```
POST 200  77.8s   <- did the real work: extract, screen, dedupe, upsert, project, publish
POST 200  55.4s   <- redelivery, blocked on DB session until the first commit landed
POST 200  29.9s   <- redelivery, same
POST 200  0.02s   <- later redelivery, instant idempotency short-circuit
```

Structured logs confirm exactly one full run:

```
ingest_complete            asset_id=c2937f867965a8cf423f0d5c  claim_count=23
ingest_already_processed   asset_id=c2937f867965a8cf423f0d5c   (x3, the redeliveries above)
```

Firestore projection, queried directly:

```python
>>> client.collection("projects").document("demo").get().to_dict()
{'title': 'The Long Take', 'counts_by_status': {'pending': 23}, 'spend_usd': 0.0,
 'release_date': '2026-10-10', 'reality_drift': 0.0, 'counts_by_risk': {}}
>>> len(list(client.collection("projects").document("demo").collection("claims").stream()))
23
```

Pub/Sub — exactly one message on `claims-extracted-verify`, none on the DLQ:

```
$ gcloud pubsub subscriptions pull claims-extracted-verify --auto-ack
{"project_id": "demo", "asset_id": "c2937f867965a8cf423f0d5c", "kind": "script", "claim_count": 23, "run_hint": "ingest"}

$ gcloud pubsub subscriptions pull claims-extracted-dlq-pull --auto-ack
(empty)
```

This is idempotency working exactly as designed (`Asset.compute_id`, `docs/DECISIONS.md`
#031): 4 delivered events, 1 completed pipeline run, 1 Pub/Sub message, 0 duplicate
claims, 0 dead-lettered messages.

## Second run — Hindi script, confirms multilingual + re-verifies idempotency

```
$ gsutil cp fixtures/scripts/sample_hi.pdf gs://.../scripts/demo/sample_hi_<ts>.pdf
ingest_complete  claim_count=6
ingest_already_processed  (1 redelivery, short-circuited)
```

## Cloud Trace — full span hierarchy, after fixing the CPU-throttling bug (#032)

First attempt: zero traces reached Cloud Trace despite a fully successful run — Cloud
Run's request-based billing freezes CPU once the response is sent, so
`BatchSpanProcessor`'s background export thread never ran. Added
`packages.common.tracing.flush_tracing()`, called at the end of
`services/ingest`'s request handler while CPU is still allocated. Redeployed, re-ran:

```
trace 0030c63c29c0073a709035a6477bfad3
  / 						14:45:22.35
  POST /					14:45:22.38
  POST / http receive		14:45:22.38
  ingest					14:45:22.38
  extract					14:45:23.23
  screen					14:45:43.06
  upsert					14:45:44.65
  project					14:45:44.72
  publish					14:45:45.60
  POST / http send			14:45:45.78
```

Matches PHASE_03.md §3.5's acceptance criterion exactly: `ingest > extract > screen >
upsert > project > publish`.

## Two real bugs found and fixed along the way

1. **Eventarc trigger creation ordering** — `terraform apply` for the trigger failed
   until `ingest` was deployed to Cloud Run first. Fixed by reordering
   `.github/workflows/deploy.yml` (deploy services, then `terraform apply`). See
   `docs/DECISIONS.md` #030.
2. **Eventarc's own service agent needs bucket read access** — trigger creation then
   failed with `403 storage.buckets.get`, fixed with a dedicated
   `roles/storage.objectViewer` grant on the intake bucket for
   `service-{project}@gcp-sa-eventarc.iam.gserviceaccount.com`. See `docs/DECISIONS.md`
   #030.

## Offline coverage

`tests/services/ingest/test_ingest_main.py` — naming-convention regex matching and the
within-asset dedupe merge (pure logic, no live dependencies).
`tests/packages/claims/test_models_schema.py::test_asset_compute_id_*` — the idempotency
key's determinism.

```
$ uv run pytest tests/services/ingest -v
11 passed
```
