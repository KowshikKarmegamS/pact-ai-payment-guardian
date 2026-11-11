# HANDOFF.md — PACT (AI Payment Authorization Gateway)

> Last updated: 2026-11-11 · branch `main`

## Current state

| Item | State | How to check |
|---|---|---|
| Backend tests | **148 passed** (3 deprecation warnings from Starlette) | `cd backend && pytest -q` |
| Frontend production build | **passes** (2084 modules, Vite) | `cd frontend && npm run build` |
| PayPal Sandbox end to end | **verified live**: order `1TB76166AJ238330L`, capture `7HT24116Y1448214M`, COMPLETED, 89.00 USD (final demo run); earlier capture `9XY78096Y6982133J`, 99.99 USD, with duplicate capture prevented | Transactions page / Authorization Receipt |
| AI recommender | **Gemini `gemini-3.5-flash`** works with the current key (Google reports `gemini-3.6-flash`); backup `gemini-3.5-flash-lite` works and is tried once on 429/500/503; otherwise the labelled keyword fallback ("not AI") | `GET /api/status`; sidebar "Recommender" |
| Agent Gateway + MCP | **verified live**: real Gemini agent over MCP; over-limit Sony request blocked, $34.99 hub request awaiting approval | `integrations/mcp/example_agent.py` |
| Owner sign-in | **implemented and tested** (unit tests + manual browser test): wrong password rejected, sign-in unlocks, sign-out locks | set `OWNER_PASSWORD` |
| Demo video | **final**: `demo/pact-hackathon-final.mp4`, 2:49 (169.4 s), 1920x1080 H.264 High 30 fps + AAC-LC 48 kHz stereo, 51 MB, decodes with zero errors | `ffprobe`, `ffmpeg -v error -i … -f null -` |
| Screenshots | **current** dark UI, 9 images in `docs/screenshots/` (7 desktop 1440x900, 2 mobile 390x844 @2x) | README → Screenshots |
| Render deployment | **live** at https://pact-ai-payment-guardian.onrender.com (free plan; data resets on restart/sleep). Verified: health 200, PayPal Sandbox OAuth OK, Gemini configured, owner routes 401 until sign-in, agent gateway 401 without key, sign-in screen renders | `/api/status?check_paypal=true` |
| Docker image | **builds and runs locally**; fails closed without `OWNER_PASSWORD` | `docker build -t pact .` |

## What PACT is

The payment authorization gateway for AI agents. Any agent (the built-in Gemini reference agent, or an external
agent via `/api/agent/v1` or the MCP server) can only *request* a catalog item. The deterministic policy engine
decides against the owner's mandate, the owner approves the exact purchase (SHA-256 fingerprint over purchase,
mandate rules and requesting agent), and PayPal Orders v2 (Sandbox) executes. `CAPTURED` is set only from a real
PayPal capture ID with status COMPLETED and a matching amount and currency.

## Security model and limitations

- **Owner (Control Center):** `OWNER_PASSWORD` turns on sign-in for every owner-facing `/api` route (mandates,
  proposals/approvals, payments, agents, catalog, audit). The session is an HMAC-signed, HttpOnly, SameSite=Lax
  cookie; failed logins are throttled (5 per 5 minutes per client, in memory). `REQUIRE_OWNER_AUTH=true`
  (set in `render.yaml`) makes a deployment fail closed until a password is set.
- **Open by default locally:** with no `OWNER_PASSWORD`, the Control Center is open to anyone who can reach it
  (the server logs a warning). This mode is only for a local demo.
- **Single owner:** one shared password, no user accounts, no 2FA, no per-user mandates.
- **Agents:** per-agent keys (hash stored, shown once), scoped to granted mandates, revocable. The gateway has no
  approve, order, capture or mandate route, and the MCP server has no pay tool.
- **Single instance only:** SQLite and an in-memory login throttle; multiple instances would need Postgres and
  shared rate limiting.

## Demo video notes

- Recorded in story order on one clean demo database (`demo/tools/pact-demo.db`, git-ignored), with live Gemini
  recommendations and a real PayPal Sandbox payment. The PayPal login form is never recorded.
- Verified on 2026-11-11 by a full Gemini transcription of the soundtrack: all 17 narration lines present, in
  order, and matching `demo/pact-narration.txt`. All transitions are silent (TTS edge artifacts removed); the
  longest pause is 2.6 s. Nobody has listened to it by ear in this session; do that once before submitting.
- Voice: Gemini TTS "Charon". Lines 1–5 come from `gemini-3.8-flash-tts`, the rest from
  `gemini-3.8-flash-lite-tts` (free-tier daily limits), so the timbre may shift slightly around 0:53.
- Known in-footage details: PayPal's checkout page says "Cancel and return to PACT AI Payment Guardian" (the old
  `brand_name`, now "PACT Authorization Gateway" for new orders). The MCP title card shows the transcript of an
  earlier, real `example_agent.py` run against the same mandate state (the agent refused after a dry run); in the
  later run shown on the Agents page, the agent submitted the request and PACT blocked it.
- Rebuild: demo server on :8002 with `DATABASE_URL=sqlite:///…/demo/tools/pact-demo.db`, then in `demo/tools`:
  `bash run_takes.sh` (needs the PayPal Sandbox buyer signed in to the recorder profile: `node record.mjs login`),
  `node record.mjs app4`, `python build.py`. Screenshots: `node screenshots.mjs <blocked> <captured> <voided> <agent-request>`.

## Remaining tasks

1. Watch and listen to `demo/pact-hackathon-final.mp4` once, end to end.
2. Upload the video to YouTube (unlisted) or Vimeo and paste that link into Devpost (`docs/DEVPOST.md` has the
   repository and in-repo video links).
3. Not yet verified on the live site (needs the owner password): a signed-in Gemini recommendation and a PayPal Sandbox payment end to end.
4. An old PACT v1.0.0 server may still be listening on port 8000 on the development machine; stop it before using
   that port.
