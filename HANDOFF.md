# HANDOFF.md — PACT project state

> Last updated: 2026-11-11 (branch `feat/judge-ready-payment-guardian`)

## Status at a glance

| Item | State | Evidence |
|---|---|---|
| Backend tests | **103 passed** (was 17) | `cd backend && pytest -q` |
| Frontend production build | **passes**, no mock imports | `cd frontend && npm run build` |
| PayPal Sandbox OAuth | **verified live** | `GET /api/status?check_paypal=true` → `oauth.ok: true` |
| Real Sandbox order creation | **verified live** | orders `45E59597XE7243603` (curl smoke test, later rejected) and `4JN22935LV1612144` (via UI) |
| **Full live E2E (buyer approval + capture)** | **VERIFIED** | Order `05V70376MR1821151` → buyer approved in Sandbox Checkout → PACT verified `APPROVED` with PayPal → capture `9XY78096Y6982133J` **COMPLETED**, 99.99 USD; proposal `61332dde-2664-4da7-a7fb-d0265fde2314` is CAPTURED; repeat capture made no PayPal call |
| Sandbox seller currency | **resolved** | The original Sandbox business account (India) refused USD ("This seller doesn't accept payments in your currency"). Replaced with a US business account + new app credentials in `backend/.env`. |
| Capture refused before buyer approval | **verified live** | PayPal returned `PAYER_ACTION_REQUIRED`; API answered `409 ORDER_NOT_APPROVED` |
| AI provider (Gemini default, OpenAI optional) | **not verified live** | No `GEMINI_API_KEY`/`OPENAI_API_KEY` in local `.env`; recommendations use the labelled heuristic. 14 Gemini tests run against a stubbed endpoint (success, invalid output, quota/403/404/500, timeout, safety block). |
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

1. Create a free Gemini key at https://aistudio.google.com/apikey, add `GEMINI_API_KEY=...` to `backend/.env`,
   restart, and run scenarios A–C (sidebar should read "Google Gemini · gemini-2.5-flash").
   Until then every recommendation is the labelled heuristic.
2. Record the demo video (`docs/DEMO_SCRIPT.md`) and add the link to README and `docs/DEVPOST.md`.
3. Optional: deploy to Render (paid Starter plan + disk), set `APP_BASE_URL`, verify `/api/status?check_paypal=true`.
   Build the Docker image once locally first (`docker build -t pact .`) with Docker Desktop running.
4. Merge `feat/judge-ready-payment-guardian` into `main` and push.
5. Stop the old v1.0.0 server still listening on port 8000.
