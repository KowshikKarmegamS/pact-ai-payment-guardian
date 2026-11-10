# HANDOFF.md — PACT project state

> Last updated: 2026-11-10 (branch `feat/judge-ready-payment-guardian`)

## Status at a glance

| Item | State | Evidence |
|---|---|---|
| Backend tests | **89 passed** (was 17) | `cd backend && pytest -q` |
| Frontend production build | **passes**, no mock imports | `cd frontend && npm run build` |
| PayPal Sandbox OAuth | **verified live** | `GET /api/status?check_paypal=true` → `oauth.ok: true` |
| Real Sandbox order creation | **verified live** | orders `45E59597XE7243603` (curl smoke test, later rejected) and `4JN22935LV1612144` (via UI) |
| Capture refused before buyer approval | **verified live** | PayPal returned `PAYER_ACTION_REQUIRED`; API answered `409 ORDER_NOT_APPROVED` |
| Buyer approval + real capture | **NOT YET VERIFIED** | needs a human to log in with the Sandbox personal account (see next steps) |
| OpenAI path | **not verified live** | `OPENAI_API_KEY` is empty in local `.env`; recommendations use the labelled heuristic. Unit tests cover the OpenAI branch with a stubbed client. |
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

1. **Finish the live end-to-end test**: in the app, open proposal `d3764342-70b0-4a8e-bf65-686a450a89d9`
   (order `4JN22935LV1612144`), click *Open PayPal checkout*, log in with the **Sandbox personal** account,
   approve, then click *Capture $99.99*. Record the capture ID and audit events here.
   If order creation/capture reports `CURRENCY_NOT_SUPPORTED`, see README "PayPal Sandbox setup → Currency".
2. Add `OPENAI_API_KEY` to `backend/.env`, restart, and run scenarios A–C to confirm the OpenAI path
   (sidebar should read "OpenAI gpt-4o-mini").
3. Re-take screenshots of a CAPTURED receipt for the README.
4. Record the demo video (`docs/DEMO_SCRIPT.md`), then add the link to README and Devpost.
5. Optional: deploy to Render (paid Starter plan + disk), set `APP_BASE_URL`, verify `/api/status?check_paypal=true`.
6. Merge `feat/judge-ready-payment-guardian` into `main`.
