# Sponsor integrations: what is real, how to verify it, what is not done

Last updated 2026-11-12. Only integrations that were actually built and run are claimed.

## Eligibility matrix

| Sponsor prize | Status | Tested | Claim it? |
|---|---|---|---|
| **Best Use of Channel3** | Implemented: live search, catalog normalization, Agent Gateway and MCP search, policy enforcement, fingerprint binding, live re-checks, retailer handoff | 11 automated tests (mocked Channel3) plus live runs against `api.trychannel3.com`, including a real PayPal Sandbox capture of a Channel3 offer | **Yes** |
| **Best Use of AG Grid (AG Studio)** | Implemented: AG Studio dashboard on real PACT data, custom theme, cross-filtering, Filters panel, edit mode, Studio Agent Framework wired to Gemini through a server-side proxy | 5 automated tests (dataset and proxy) plus a browser run in which Studio's agents built a new widget | **Yes**. The 45-day trial license is set locally (`VITE_AG_STUDIO_LICENSE_KEY`; verified: no license notice, no watermark). Set the same variable on Render for the live site |
| **Best Use of APIMatic** | Context Plugin for PayPal installed and used: PACT's Orders v2 client reviewed against the PayPal Server SDK 2.4.0 contract; two mismatches fixed (Prefer header, description length), five areas confirmed | 3 contract tests; live Sandbox order after the change | **Yes**, for using the plugin to validate and improve the PayPal integration. PACT does not run the SDK itself |
| **Best Use of Render** | PACT is deployed on Render (web service + blueprint). **Render Workflows is not implemented.** | Deployment verified earlier (health 200, Sandbox OAuth OK) | **No.** The prize asks for Render Workflows, which needs a Render API key and a separately deployed workflow service that this session cannot create or verify |

## Channel3 (https://docs.trychannel3.com)

**What it does in PACT**
- **Natural-language search.** `POST /v1/search` is called from the running app in three places: the Catalog page's live search box, the reference agent's **Live retailers · Channel3** mode, and the Agent Gateway / MCP `search_catalog` tool. The MCP tool searches live retailers by default.
- **Normalization.** Each retailer offer on a Channel3 product becomes one PACT catalog item:
  - The merchant is the retailer's domain (for example `bestbuy.com`).
  - The price and currency come from the offer. Only USD offers are kept; other currencies are skipped and reported.
  - Availability (`InStock` or `OutOfStock`) becomes the in-stock flag.
  - The offer's buy link, the brand, the top-level category and the Channel3 product id (`external_id = <product id>:<domain>`) are stored too.
- **Same controls as every item.** Offers go through the deterministic policy engine, so mandate merchant allowlists, categories, per-item limits, quantity and budget all apply. A seeded mandate, *Live retailers (Channel3): desk tech under $100*, allows five retailer domains. Any other retailer is blocked.
- **Fingerprint binding.** For connector offers, the approval fingerprint also covers the offer: source, external id and the buy link's stable part (host + path; Channel3 adds per-request tracking ids to the query string).
- **Stale offers.** PACT re-reads the offer with `GET /v1/products/{id}` before human approval, before PayPal order creation and before capture.
  - If the price, availability, retailer, name, category or listing changed, the approval is voided (`APPROVAL_EXPIRED`) and nothing is charged.
  - If Channel3 cannot be reached, the step is refused with `OFFER_UNVERIFIED` (fails closed).
- **Retailer handoff.** After a verified PayPal Sandbox capture, the buyer can continue to the retailer's own checkout through the stored buy link (`POST /api/payments/{id}/retailer-handoff`). This is recorded as `RETAILER_HANDOFF_OPENED` and never marks anything as paid at the retailer. It is refused before capture and for catalog items.
- **Keys and links stay on the server.** `CHANNEL3_API_KEY` is sent only in the `x-api-key` header. The Agent Gateway never returns buy links to agents, so they cannot route around PACT.

**Files:**
- `backend/app/connectors/channel3.py`: client and normalization.
- `backend/app/services/connector_sync.py`: upsert, search import, live re-check.
- `backend/app/routers/connectors.py`: `POST /api/connectors/channel3/search`, sync.
- `backend/app/routers/gateway.py`: live agent search.
- `backend/app/routers/proposals.py`: `source: "channel3"`, approval re-check.
- `backend/app/routers/payments.py`: order and capture re-checks, handoff.
- `backend/app/services/authorization.py`: offer in the fingerprint, link drift.
- `integrations/mcp/pact_mcp_server.py`.
- Frontend: `frontend/src/pages/Catalog.tsx`, `ShoppingAssistant.tsx`, `Authorization.tsx` (retailer panel).
- Tests: `backend/tests/test_channel3.py`.

**Evidence (2026-11-12, local scratch database, live Channel3 and PayPal Sandbox)**
- **Search.** "Anker 7-in-1 USB-C hub" returned 12 real offers from bestbuy.com, newegg.com, bhphotovideo.com, cdw.com and anker.com.
- **Blocked.** The bhphotovideo.com offer was blocked: "Merchant 'bhphotovideo.com' is not permitted by mandate".
- **Allowed and paid.** The bestbuy.com offer at $31.99 passed 9/9 rules. It was approved after a live re-check, then:
  - PayPal Sandbox order `0KD45697U0846634K` was created after a second re-check.
  - The buyer approved in PayPal Checkout.
  - It was captured after a third re-check: capture `503249659P3985442`, **COMPLETED**.
- **Reference agent.** In live mode, Gemini picked the cheapest Logitech MX Master 3S offer (newegg.com, $62.99) out of 26 retailer offers.
- **Bug found by the live run, then fixed.** Channel3 buy links change their query string on every read. The first live approval was therefore voided as "buy link changed". Links are now compared by host and path, with a regression test.

**Verify it yourself**
1. Set `CHANNEL3_API_KEY` in `backend/.env` and start the backend.
2. Go to **Catalog → Channel3 → Search**, for example "logitech mx master 3s".
3. In **Reference agent → Live retailers · Channel3**, pick the *Live retailers* mandate and ask for a product.
4. Approve it, pay in PayPal Sandbox, then click **Continue to <retailer>**.
5. Run `cd backend && pytest -q tests/test_channel3.py`.

## AG Grid: AG Studio (`ag-studio-react` / `ag-studio` 3.1.0)

**What it does in PACT:** a new **Analytics** page in the Control Center (`/analytics`).
- **Data.** `GET /api/analytics/dataset` returns one row per persisted purchase request: agent, merchant, source (PACT catalog, Channel3 or Northwind), mandate, outcome, policy decision, requested, paid and blocked amounts. Paid counts only verified PayPal captures. Nothing is sample or generated data.
- **Shipped report.** It has:
  - KPI tiles: paid through PayPal, requested by agents, stopped by the policy engine, number of requests.
  - Charts: outcome donut, amount by AI agent, paid by merchant, requests per day, amount by product source.
  - Mandate and policy-decision list filters, and a full purchase grid.
- **Interaction.** Charts cross-filter each other. Field names and USD currency formats are declared. A custom dark theme matches PACT, using `studioTheme.withParams` with Studio's dark mode activated on the container. **Edit dashboard** switches Studio to edit mode.
- **Studio Agent Framework.** `AgStudioAiModule` and `createAiHarness` use Studio's built-in Lead, Planning, Data, Page and Widget agents, with PACT prompt starters.
  - The `AgLlmAdapter` posts each model turn to `POST /api/analytics/agent-turn`.
  - That endpoint translates Studio's conversation items and JSON-schema tools into Gemini function calling and maps the answer back, including Gemini's thought signatures.
  - The Gemini key never reaches the browser.
  - The dashboard agents have only Studio's tools: they can query data and change widgets, but cannot approve, pay or touch mandates.

**Files:**
- `frontend/src/pages/Analytics.tsx`, `backend/app/routers/analytics.py`, `backend/app/services/studio_llm.py`.
- `frontend/src/App.tsx` and `Layout.tsx` (route and nav).
- Tests: `backend/tests/test_analytics.py`.

**Evidence (2026-11-12):**
- The dashboard rendered 15 real requests: $31.99 paid, $1,858.35 requested, $966.92 stopped by policy.
- In the AI panel, the prompt starter "Where did the guardrail save money?" ran a multi-agent session through the proxy (Gemini `gemini-3.5-flash-lite`). The Lead delegated to the Page and Widget agents, which read the schema and configured a new grouped bar chart: blocked amount by merchant, split by agent, filtered to blocked outcomes.

**License.**
- AG Studio is commercial. Without a key it runs with all features and an "AG Studio Pro with AI" trial watermark plus console notices; that is how it was tested.
- To remove the watermark, request the free 45-day trial key (hackathon page: https://paypalaihackathon.devpost.com/details/aggrid). Set it as `VITE_AG_STUDIO_LICENSE_KEY` at build time (frontend `.env`, or the Render env var of the same name; the Dockerfile passes it to the build).
- Like every AG license key, it ends up in the browser bundle.

**Limitations.**
- The AG Studio chunk is large (about 1.9 MB gzipped). It is lazy-loaded, so only the Analytics page pays for it.
- Agent runs take tens of seconds on Gemini free-tier models, and stop when the daily quota is exhausted (the turn then fails with a message).
- No custom widget type was built. The dashboard uses Studio's built-in widgets.

## APIMatic: Context Plugin used to validate and tighten the PayPal integration

**How it was used (2026-11-12).** The APIMatic Context Plugin for PayPal was installed from
`https://github.com/paypaldev/server-sdk-context-plugin-preview` (it adds the `paypal:*` skills to Claude Code). Its
`paypal:python-getting-started` skill identifies the PayPal Server SDK (`paypal-server-sdk` 2.4.0, APIMatic-generated) and
tells the coding agent to treat that SDK's source and generated docs as the authoritative contract. Following it, the SDK
was cloned at tag `2.4.0` (read-only, outside the repo), and PACT's hand-written Orders v2 client (`backend/app/paypal.py`,
plain `httpx`) was reviewed against `doc/controllers/orders.md` and the request/enum models.

PACT kept its own `httpx` client instead of switching to the SDK. It was already working, tested and verified with
real Sandbox captures, and swapping libraries would have been a cosmetic rewrite. The plugin context was used to check
the integration and fix what did not match the documented contract.

| Checked against the SDK 2.4.0 docs | Finding | Change |
|---|---|---|
| `OrdersController.create_order` / `capture_order`: `prefer` header, "**Default**: `return=minimal`", which returns only id, status and HATEOAS links | PACT marks a payment CAPTURED from `purchase_units[].payments.captures` (capture id, status, amount). It worked live only because PayPal returned more than the documented minimum | **Fixed**: create and capture send `Prefer: return=representation` (`PREFER_FULL` in `paypal.py`) |
| `PurchaseUnitRequest.description`: "content beyond 127 characters … will be truncated" | PACT's description could reach ~152 characters, so PayPal would cut it mid-word | **Fixed**: `order_description()` caps it at 127 and shortens the product name with an ellipsis |
| `paypal_request_id` header (max 108 characters; stored 6 hours) | `order-<uuid>` / `cap-<uuid>` are 42 and 40 characters, distinct per step | Confirmed, test added |
| `PaypalWalletExperienceContext` (`brand_name` ≤ 127, `user_action` `PAY_NOW`, `shipping_preference` `NO_SHIPPING`, `return_url`, `cancel_url`); deprecated `application_context` | PACT already uses `payment_source.paypal.experience_context` | Confirmed, test added |
| `ItemRequest` (`name` ≤ 127, `quantity` pattern `^[1-9][0-9]{0,9}$`, `category` `PHYSICAL_GOODS`) | Matches | Confirmed, test added |
| `OrderStatus` (`CREATED`, `SAVED`, `APPROVED`, `VOIDED`, `COMPLETED`, `PAYER_ACTION_REQUIRED`) and `CaptureStatus` (`COMPLETED`, `DECLINED`, `PARTIALLY_REFUNDED`, `PENDING`, `REFUNDED`, `FAILED`) | PACT captures only from `APPROVED`, marks CAPTURED only for `COMPLETED` capture + `COMPLETED` order, keeps `PENDING` as pending, and treats every other value as failed | Confirmed |
| Approval link `rel` for the `payment_source` flow | PACT accepts `payer-action` (and `approve`) | Confirmed |

**Files:** `backend/app/paypal.py` (`PREFER_FULL`, `order_description`, `prefer` on `_authed`) and
`backend/tests/test_paypal_contract.py`. The contract tests check the Prefer header, the Request-Id length, the body
constraints and that `application_context` is absent.

**Evidence:**
- All tests pass (191 at the time of the change).
- Live Sandbox check after the change: PACT created order `377700153L957915M` (PAYER_ACTION_REQUIRED, 125.00 USD, `reference_id` bound to the proposal). The description PayPal stored is the 83-character string PACT sent.
- Not yet run live: a capture with the new header, because that needs the Sandbox buyer to approve in PayPal. The capture path is covered by the contract test and the existing payment tests.

**Limitations:** PACT does not use the APIMatic-generated SDK at runtime; the plugin served as the reference for
reviewing and correcting the existing integration. The APIMatic sponsor page offers free subscriptions to participants
who used the plugin: claim it with the form linked there.

## Render: deployed, Workflows not implemented

PACT runs on Render: `render.yaml` + `Dockerfile`, at https://pact-ai-payment-guardian.onrender.com. The Render prize asks for **Render Workflows** (the Python SDK `render`, with tasks defined as functions). That was not built, because:
- It needs a Render API key (`RENDER_API_KEY`) and a workflow service created in your Render workspace. This session cannot create or verify either, and free-plan support for Workflows is not confirmed in Render's docs.
- Workflow runs execute on their own instances and cannot write to the web service's SQLite in `/tmp`. A correct design would have the workflow call Channel3 and push validated offers to a PACT ingest endpoint, or move PACT to Render Postgres.

A simulated workflow (a thread or a cron job presented as Workflows) was deliberately not built.

**If you want it:**
1. Add the Render plugin to Claude Code (the Anthropic plugin directory lists "Render", with a `render-workflows` skill and the Render MCP server).
2. Create a Render API key.
3. Ask for a Channel3 catalog-sync workflow that calls PACT's existing `POST /api/connectors/channel3/sync` path with retries.
