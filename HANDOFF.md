# HANDOFF.md — PACT project state (AI Payment Authorization Gateway)

> Last updated: 2026-11-11 (branch `feat/judge-ready-payment-guardian`)

## Status at a glance

| Item | State | Evidence |
|---|---|---|
| Backend tests | **139 passed** | `cd backend && pytest -q` |
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
- `demo/pact-hackathon-final.mp4`: 1920x1080, H.264 (yuv420p) + AAC, 2:39. All three app takes were recorded in story
  order on one clean copy of the database, with Gemini recommendations and a real PayPal Sandbox payment:
  order `6X20893840026523N`, capture `223819305K399301H` (COMPLETED, 89.00 USD).
- Narration: Google Gemini text-to-speech, voice "Charon" (`demo/tools/tts_gemini.py`). Lines 1-4 come from
  `gemini-3.8-flash-tts`, lines 5-15 from `gemini-3.8-flash-lite-tts`, because the free tier allows about 10 speech
  requests per day per model. Every line was checked by transcript against the script. To make the voice uniform,
  run `python tts_gemini.py --model <one model> <ids...>` after the daily quota resets, then `python build.py`.
  The earlier Windows-voice narration is kept in `demo/tools/work/voice-david/` (git-ignored).
- To re-record: demo server on :8002 with `demo/tools/pact-demo.db`, recorder profile signed in to the PayPal Sandbox
  buyer (`node record.mjs login`), then `bash run_takes.sh && python build.py` in `demo/tools`.
- Servers left running: old v1.0.0 on :8000, main app on :8001 (restart to pick up latest backend and key), demo on :8002.
- Not done: Docker build, Render deployment, README screenshots of the new design, publishing the video.

## Repositioned as middleware: Agent Gateway + MCP (2026-11-11)

- PACT is now presented as the **payment authorization gateway for AI agents**. The standalone app is the
  **PACT Control Center**; the built-in Gemini assistant is the **reference agent** (nav: "Reference agent").
- Agent Gateway `/api/agent/v1` (`backend/app/routers/gateway.py`): per-agent keys (`services/agent_keys.py`,
  SHA-256 hash stored, shown once), scoped to granted mandates; whoami/authority, catalog search, dry-run evaluate,
  request purchase (idempotent `request_id`), status. No approve/order/capture/mandate route; a test checks the
  OpenAPI schema. Control Center side: `/api/agents` (register, list, revoke) and the **Agents** page.
- The requesting agent is added to `canonical_snapshot()` only when set, so fingerprints of older proposals are unchanged.
- `integrations/mcp/pact_mcp_server.py`: stdlib-only MCP stdio server with 5 tools and no pay tool.
  `integrations/mcp/example_agent.py`: a real Gemini agent that knows PACT only through MCP (verified live on :8001
  and :8002: over-limit headphones refused; $34.99 USB-C hub request waiting for human approval).
- Known gap (documented in README): Control Center endpoints have no owner login yet, so in production approval
  must sit behind authentication.

### Video changes

- Static at cuts: every Gemini TTS clip started with a ~5 ms full-scale blip and ended with ~125 ms of loud noise.
  `tts_gemini.py` now runs `declick()` on every clip (`python tts_gemini.py --declick` cleans existing ones).
  All transitions in the final file now measure -56 to -75 dB.
- Lag at cuts: several clips were a frozen frame for 5-10 s while narration ran, then jumped. `build.py` now adds
  a slow 3.5% push-in to app footage, joins clips with 0.35 s crossfades, and places each voice line on the
  crossfaded timeline. Remaining still moments are short title-card holds (<= 3 s).
- New scenes: `card-mcp` (the real example-agent transcript) and take `app4` (Agents page and the agent's request).
  Intro, dashboard line, reference-agent line and outro re-voiced. Final: **2:50**, 1920x1080 H.264 + AAC.
- Voice models: lines 01-04 and 05 from `gemini-3.8-flash-tts`; 06-14 and 14b/14c/15 from
  `gemini-3.8-flash-lite-tts` (both free-tier daily limits were reached). Not listened to by a human yet.
- Demo DB backup before the agent scenes: `demo/tools/pact-demo.db.bak-before-agents` (git-ignored).
- All four app takes were re-recorded on a clean demo database with the new Control Center labels:
  blocked $125 NuPhy, $89 Keychron paid via PayPal Sandbox (order `1TB76166AJ238330L`, capture `7HT24116Y1448214M`,
  COMPLETED), second approval voided by a $99.50 price change, then the MCP agent's Sony request (blocked) and
  USB-C hub request (awaiting approval). Recommendations: `gemini-3.5-flash` (Google reports `gemini-3.6-flash`).
- The PayPal checkout in the recording still says "Cancel and return to PACT AI Payment Guardian"; the order
  `brand_name` is now "PACT Authorization Gateway" for future orders.
- `run_takes.sh` cleanup now removes only proposals created by the failed attempt (it used to remove anything from
  the last 10 minutes). Free-tier Gemini text quota is 20 requests/day per model; the takes need several.
