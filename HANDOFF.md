# HANDOFF.md — PACT project state

> Last updated: 2026-11-11 (branch `feat/judge-ready-payment-guardian`)

## Status at a glance

| Item | State | Evidence |
|---|---|---|
| Backend tests | **108 passed** (was 17) | `cd backend && pytest -q` |
| Frontend production build | **passes**, no mock imports | `cd frontend && npm run build` |
| PayPal Sandbox OAuth | **verified live** | `GET /api/status?check_paypal=true` → `oauth.ok: true` |
| Real Sandbox order creation | **verified live** | orders `45E59597XE7243603` (curl smoke test, later rejected) and `4JN22935LV1612144` (via UI) |
| **Full live E2E (buyer approval + capture)** | **VERIFIED** | Order `05V70376MR1821151` → buyer approved in Sandbox Checkout → PACT verified `APPROVED` with PayPal → capture `9XY78096Y6982133J` **COMPLETED**, 99.99 USD; proposal `61332dde-2664-4da7-a7fb-d0265fde2314` is CAPTURED; repeat capture made no PayPal call |
| Sandbox seller currency | **resolved** | The original Sandbox business account (India) refused USD ("This seller doesn't accept payments in your currency"). Replaced with a US business account + new app credentials in `backend/.env`. |
| Capture refused before buyer approval | **verified live** | PayPal returned `PAYER_ACTION_REQUIRED`; API answered `409 ORDER_NOT_APPROVED` |
| AI provider: Google Gemini (default) | **verified live** | `gemini-3.5-flash` with minimal thinking (Google reports modelVersion `gemini-3.6-flash`), 3-5 s per request. Scenario A -> Logitech mouse, all 11 rules pass; B -> PS5 blocked (6 rules); C -> Gemini picked the injected marketplace listing, policy blocked it (merchant). `gemini-2.5-flash` returns 404 "no longer available to new users"; `gemini-3.8-flash` timed out (>45 s); `gemini-flash-latest` returned 503. OpenAI remains optional (`AI_PROVIDER=openai`). |
| Scenario A / B / C in UI | **verified** | screenshots in `docs/screenshots/` |
| Route refresh, `/docs`, API 404s (single-process) | **verified** | `/`, `/assistant`, `/mandates`, `/audit`, `/docs` → 200 HTML; `/api/nope` → JSON 404 |
| DB persistence with disk-path config | **verified** | data survived restart with `DATABASE_URL=sqlite:///<dir>/pact.db` |
| Docker image build | **not run** | Docker Desktop daemon was not running |
| Render deployment | **not deployed** | `render.yaml` needs a paid plan for the persistent disk |
| Demo video | not recorded | script in `docs/DEMO_SCRIPT.md` |

## What changed in this milestone

### Payment correctness (priority 1)
- Removed the capture fallbacks that could store `"COMPLETED"` / `"ALREADY_CAPTURED"` as a capture ID.
- Capture now: atomic lock → GET order → verify id/reference/mandate/amount/currency and status `APPROVED`
  → re-verify approval fingerprint and policy → capture with stable `PayPal-Request-Id`
  → CAPTURED only with a real capture ID, status COMPLETED, matching amount and currency.
- Timeouts leave `CAPTURE_PENDING`; retry is idempotent and `/verify` reconciles an order PayPal already captured.
- New state machine (see AGENTS.md). Legacy rows were migrated: old `APPROVED` → `APPROVAL_EXPIRED`
  (no fingerprint existed), `PENDING` → `AWAITING_HUMAN_APPROVAL`, `REJECTED` → `POLICY_REJECTED`/`HUMAN_REJECTED`.
  A backup of the pre-migration DB is at `backend/pact.db.bak-20261110` (git-ignored).
- `PAYPAL_CURRENCY`, `APP_BASE_URL` settings; Sandbox-only enforcement; classified, sanitized PayPal errors.

### Approval binding
- SHA-256 fingerprint over canonical proposal + mandate policy. Approve must echo it.
  Re-checked at order creation and capture, and on every mandate update.

### AI
- Strict pydantic validation of model output, catalog-only IDs, quantity 1–20, extra fields ignored and logged.
- Provider/model/fallback reason stored per proposal and shown in UI; `/api/status` reports mode.

### Frontend
- All pages on live data; `mockData.ts` deleted. Authorization Receipt, lifecycle stepper, popup-safe checkout,
  PayPal return/cancel handling (BroadcastChannel + postMessage + polling), mandate CRUD/pause.

### Deployment/docs
- `Dockerfile`, `.dockerignore`, `render.yaml`; FastAPI serves `frontend/dist` when present.
- README rewritten; `docs/DEMO_SCRIPT.md`, `docs/DEVPOST.md`.

## Local run (as used for verification)

```bash
cd frontend && npm run build
cd ../backend && APP_BASE_URL=http://localhost:8001 venv/Scripts/python -m uvicorn app.main:app --port 8001
# open http://localhost:8001
```

Note: an older PACT server (v1.0.0) was found already listening on port 8000 and was left running untouched.
Stop it before using port 8000 for the new build.

## Next steps (in order)

1. Record the demo video (`docs/DEMO_SCRIPT.md`) and add the link to README and `docs/DEVPOST.md`.
2. Optional: deploy to Render (paid Starter plan + disk), set `APP_BASE_URL`, verify `/api/status?check_paypal=true`.
   Build the Docker image once locally first (`docker build -t pact .`) with Docker Desktop running.
3. Merge `feat/judge-ready-payment-guardian` into `main` and push.
4. Stop the old v1.0.0 server still listening on port 8000.

## UI redesign and demo video (2026-11-11)

- Dark redesign of all screens is committed; 124 backend tests pass; frontend builds.
- `demo/pact-hackathon-final.mp4`: 1920x1080, H.264 + AAC, 2:41. Real app footage, real Gemini recommendations,
  real PayPal Sandbox order `7Y359490LL8423124` / capture `6FG482642G189541M` (COMPLETED, 89.00 USD).
  Narration is Windows built-in TTS ("David"); script in `demo/pact-narration.txt`, captions in `demo/pact-demo-assets/captions.srt`.
- Known imperfections in the video: the mandate shows a $200 budget in the early scene and $400 in the payment
  scene (budget was widened between takes after a wasted payment); pixel format is full-range (yuvj420p).
- A clean in-order re-record was attempted (`demo/tools/run_takes.sh`) but Gemini's free tier returned 503/429 on
  the payment take six times. `demo/tools/frames/app2` now holds a failed partial take; the good take survives only
  as cached video in `demo/tools/work/` (git-ignored). To re-record: wait for Gemini quota, then
  `cd demo/tools && bash run_takes.sh && python build.py` (demo server on :8002 with `pact-demo.db`; the recorder's
  Chrome profile must be signed in to the PayPal Sandbox buyer: `node record.mjs login`).
- Servers left running: old v1.0.0 on :8000, main app on :8001 (restart to pick up latest backend), demo on :8002.
