# HANDOFF.md — PACT (AI Payment Authorization Gateway)

> Last updated: 2026-11-12 (sponsor integrations) · branch `main`

## Current state

| Item | State | How to check |
|---|---|---|
| Backend tests | **181 passed** (3 deprecation warnings from Starlette) | `cd backend && pytest -q` |
| Frontend production build | **passes** (2084 modules, Vite) | `cd frontend && npm run build` |
| PayPal Sandbox end to end | **verified live**: order `1TB76166AJ238330L`, capture `7HT24116Y1448214M`, COMPLETED, 89.00 USD (final demo run); earlier capture `9XY78096Y6982133J`, 99.99 USD, with duplicate capture prevented | Transactions page / Authorization Receipt |
| AI recommender | **Gemini `gemini-3.5-flash`** works with the current key (Google reports `gemini-3.6-flash`); backup `gemini-3.5-flash-lite` works and is tried once on 429/500/503; otherwise the labelled keyword fallback ("not AI") | `GET /api/status`; sidebar "Recommender" |
| Agent Gateway + MCP | **verified live**: real Gemini agent over MCP; over-limit Sony request blocked, $34.99 hub request awaiting approval | `integrations/mcp/example_agent.py` |
| Owner sign-in | **implemented and tested** (unit tests + manual browser test): wrong password rejected, sign-in unlocks, sign-out locks | set `OWNER_PASSWORD` |
| Demo video | **final (v2)**: `demo/pact-hackathon-final.mp4`, 2:54 (174.1 s), 1920x1080 H.264 30 fps + AAC 48 kHz stereo, 22 MB, decodes with zero errors. Adds agent connection, the fingerprint card, merchant connectors and the architecture card | `ffprobe`, `ffmpeg -v error -i … -f null -` |
| Screenshots | **current** dark UI, 9 images in `docs/screenshots/` (7 desktop 1440x900, 2 mobile 390x844 @2x) | README → Screenshots |
| Render deployment | **live** at https://pact-ai-payment-guardian.onrender.com (free plan; data resets on restart/sleep). Verified: health 200, PayPal Sandbox OAuth OK, Gemini configured, owner routes 401 until sign-in, agent gateway 401 without key, sign-in screen renders | `/api/status?check_paypal=true` |
| Merchant connectors | `MerchantConnector` interface with Channel3 as the live connector (the Northwind Shopify-format demo store was removed in the lean-up; the submitted video still shows it) | `GET /api/connectors` |
| Auto-authorization | **implemented, tested, verified locally**: three outcomes (auto / needs approval / blocked), mandate `authorization_mode` + `max_auto_approve_amount` (default unchanged), per-mandate budget lock with race tests, auto terms in the fingerprint. Scenario run on a scratch DB: $89 auto-authorized → real PayPal Sandbox order `6JR16394Y8779803T` (capture refused until buyer approval); $125 escalated; $299.99 blocked | README → Auto-authorization |
| Channel3 live retailers | **implemented, verified live locally** (scratch DB): search → policy → approval → PayPal Sandbox capture `503249659P3985442` COMPLETED ($31.99, bestbuy.com) → retailer handoff available. Needs `CHANNEL3_API_KEY` on Render (blueprint lists it); not yet deployed | `docs/SPONSORS.md` |
| Channel3 sync script | **implemented, tested, not scheduled**: `scripts/channel3_sync.py` (owner login → sync, 12 mocked tests). Verified locally against a real server: wrong password → 401 `OWNER_LOGIN_FAILED`, no key → 503 `CONNECTOR_NOT_CONFIGURED`, with key → 23 offers created. A Render cron was dropped: Render rejected it with `need_payment_info` (cron jobs have no free plan) and the deployment stays free. `CHANNEL3_API_KEY` is set on the live service | `python scripts/channel3_sync.py` |
| AG Studio analytics | **implemented, verified in browser** on real data; Studio agents built a widget via Gemini proxy. Trial watermark until `VITE_AG_STUDIO_LICENSE_KEY` is set | `/analytics` |
| Automatic payment recording | after PayPal confirms the buyer's approval, the page calls capture automatically (all server checks still run); approving opens PayPal Checkout directly | Authorization page |
| APIMatic Context Plugin | **used**: Orders v2 client reviewed against PayPal Server SDK 2.4.0; `Prefer: return=representation` and the 127-char description cap added with contract tests; live Sandbox order `377700153L957915M` after the change | `docs/SPONSORS.md` |
| Render Workflows | **not implemented** (needs Render API key + workflow service) | `docs/SPONSORS.md` |
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

## Demo video v2 notes (2026-11-12)

- New takes on the same demo database: `app5` (connect "Claude Desktop (MCP)"; the key is replaced in the page before
  any frame is saved, so the video shows only `pact_agent_OL••••`), `app6` (Northwind sync, then a live Gemini
  recommendation of the Northwind cable, blocked by the merchant rule), and `app4` re-recorded so both agents appear.
- New cards: `fingerprint.html` (values and 409/200 responses from a real run on a scratch database; its hash
  `4e312a16…` is that run's, not the video's $89 proposal, and the card says "demo run") and `connectors.html`.
- 11 lines re-voiced: 9 with `gemini-3.8-flash-tts`, `14d`/`14e` with `gemini-3.8-flash-lite-tts` (daily limit).
  All 11 transcribed and match the script. At 2:22 a re-transcription of the final video hears "And" clearly but "Pact" as "practice": listen to that word.
- `demo/tools/pact-demo.db.bak-before-v2` is the database before these takes.
- App scenes are static: the slow push-in zoom was removed because ffmpeg's `zoompan` moved in whole-pixel
  steps and read as shaking. Clips still crossfade into each other.

## Remaining tasks

0. Set `CHANNEL3_API_KEY` (and optionally `VITE_AG_STUDIO_LICENSE_KEY`) in the Render dashboard, then deploy. The demo
   video predates Channel3, AG Studio and automatic capture (it still shows a Capture click).
1. Watch and listen to `demo/pact-hackathon-final.mp4` once, end to end (listen to the word "Pact" at 2:22).
2. Upload the video to YouTube (unlisted) or Vimeo and paste that link into Devpost (`docs/DEVPOST.md` has the
   repository and in-repo video links).
3. Not yet verified on the live site (needs the owner password): a signed-in Gemini recommendation and a PayPal Sandbox payment end to end.
4. An old PACT v1.0.0 server may still be listening on port 8000 on the development machine; stop it before using
   that port.
