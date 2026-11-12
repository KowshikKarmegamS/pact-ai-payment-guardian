# Devpost submission draft — PACT: The AI Payment Authorization Gateway

## Links

- **Repository:** https://github.com/KowshikKarmegamS/pact-ai-payment-guardian
- **Demo video (2:24, in the repository):** https://github.com/KowshikKarmegamS/pact-ai-payment-guardian/blob/main/demo/pact-hackathon-final.mp4
  (direct file: https://github.com/KowshikKarmegamS/pact-ai-payment-guardian/raw/main/demo/pact-hackathon-final.mp4).
  Devpost's video field expects YouTube, Vimeo or Youku: upload this same file there and paste that link.
- **Live app:** https://pact-ai-payment-guardian.onrender.com (Render free plan, PayPal Sandbox). The Control Center requires the owner password; share it with judges privately, never in the repository. The instance sleeps when idle (first load can take about a minute) and its data resets on restart.

## Tagline

The payment authorization gateway for AI agents: let any agent shop for you, only within the limits you set.

## Inspiration

Shopping agents are getting good at finding the right product. The unsolved part is the moment they pay. Today the choice is either "the agent can't buy anything" or "the agent has a card number". Prompt injection, hallucinated prices and compromised models make the second option dangerous, and a model's own reasoning is not proof that a purchase is allowed.

## What it does

PACT is a payment authorization gateway that lets AI agents transact within user-defined financial boundaries, regardless of which AI agent is making the request. It is middleware, not another shopping chatbot: Claude, ChatGPT, a custom agent or PACT's own reference assistant all connect through the same **Agent Gateway** (a REST API or an MCP server), and the human manages everything in the **PACT Control Center**.

1. A user creates a **spending mandate**: budget, allowed merchants and categories, max unit price and quantity, prohibited keywords and blocked merchants, optional expiry.
2. The user **connects an agent** and grants it specific mandates. The agent gets its own revocable key (only its hash is stored).
3. The **agent requests** one product from the catalog through the API or MCP tools (`check_spending_authority`, `search_catalog`, `evaluate_purchase`, `request_purchase`, `get_purchase_status`). There is no approve tool and no pay tool. The built-in Gemini assistant is the reference agent and uses the same path.
4. A **deterministic policy engine** prices the item from the catalog and evaluates every rule. Violations block the purchase outright, with a plain-language reason for each.
5. The **human approves** the exact purchase in the Control Center. The approval is bound to a SHA-256 fingerprint of the product, merchant, price, quantity, currency, mandate rules and requesting agent.
6. **PayPal executes**: PACT creates a PayPal Orders v2 Sandbox order for exactly that amount; the buyer approves in PayPal Checkout; PACT confirms the approval with PayPal server-side, re-checks the fingerprint and every rule, captures with an idempotency key, and records the payment only when PayPal returns a real capture ID with status COMPLETED for the approved amount.

**Live retailers through Channel3.** Agents (and the built-in reference agent) search 100M+ real products across 25,000+ retailers via Channel3. Every retailer offer becomes a catalog item with the retailer's domain as merchant and its real price, availability and buy link, then faces the same mandate, fingerprint-bound approval and PayPal flow. PACT re-reads the offer from Channel3 before approval, PayPal order creation and capture, voids the approval if anything changed, and after a verified capture hands the buyer to the retailer's checkout without ever recording that as a retailer payment.

**Spending analytics in AG Studio.** The Control Center has an AG Studio dashboard over every real purchase request (paid, requested and stopped-by-policy totals, outcomes, agents, merchants, sources), with cross-filtering and Studio's AI agents, which run on Gemini through PACT's server so no key reaches the browser.

**Any store, not just one catalog.** Merchant platforms plug in through connectors: one `fetch_offers()` method per platform, with Channel3 as the live example. Synced offers face the same policy engine, fingerprint and PayPal flow, a store not on the mandate is blocked, and a sync that changes a price voids any approval that no longer matches.

Every proposal gets an **Authorization Receipt** explaining which rules passed or failed, the budget at decision time, the approval fingerprint, PayPal IDs and the full lifecycle timeline, built from persisted server data and an append-only audit log.

## Why middleware

Every company building an agent will hit the same question: how much may this agent spend, on what, and who signs off? Solving it inside each agent means trusting each agent. PACT solves it once, outside the model, for every agent: one policy engine, one approval flow, one audit trail, and PayPal as the single place money moves. It complements PayPal's payment security rather than replacing it. In the demo, a separate Gemini agent that knows PACT only through MCP is told "money is no object"; PACT still holds it to the $100 limit, and the agent explains the refusal to the user.

## Why PayPal is central

PayPal is the execution layer and the source of truth for money movement. PACT uses OAuth client credentials, Orders v2 create/get/capture, `PayPal-Request-Id` idempotency, and PayPal Checkout for buyer approval. PACT never decides that a payment happened; it asks PayPal and verifies the order reference, amount, currency, capture ID and status.

## Why AI is useful here

Turning "I need an ergonomic mouse for CAD" into the right catalog item is a language problem and a good fit for an LLM (Google Gemini via the Gemini Developer API). PACT keeps that benefit while treating the model as untrusted: it never sets prices, merchants, budgets or outcomes. When no API key is configured, or the model fails or returns invalid output, PACT falls back to a keyword matcher and labels it as not AI.

## Why deterministic authorization matters

The demo includes a product listing whose description instructs AI agents that it is "pre-approved" and to "treat the merchant as TechHub". The recommender can be fooled; the policy engine can't, because it never reads model output or descriptions. It reads the catalog merchant and the mandate. Tests include a fully hijacked model response that claims approval and a $1 price: PACT still uses the real catalog price and blocks it.

## How we built it

An Agent Gateway API with per-agent scoped keys, and a dependency-free MCP server (JSON-RPC over stdio). FastAPI, SQLAlchemy 2, SQLite, Pydantic, httpx (Gemini, PayPal and Channel3 REST APIs) on the backend; React, Vite, TypeScript, Tailwind and Lucide on the frontend. The policy engine is a pure module with no database or network access. Money is `Decimal` throughout. Capture safety combines an atomic database lock, a stable PayPal-Request-Id, and reconciliation through order lookup after timeouts. 156 automated backend tests (all passing) run against an in-memory PayPal fake, so the suite can never charge anyone. The Control Center is protected by owner sign-in (`OWNER_PASSWORD`, signed HttpOnly cookie), and deployments fail closed without it.

## Challenges

- Making "captured" mean what it says: handling PENDING, DECLINED, missing capture IDs, amount mismatches and network timeouts without a double charge.
- Binding approval to exactly what the user saw, and invalidating it when a mandate changes underneath it.
- Popup blockers and PayPal return flows: the browser coming back from PayPal is treated as a hint, never as proof.
- Sandbox currency rules: seller accounts in some regions reject USD. PACT reports this clearly instead of silently switching currency, which would change what the user approved.

## What we learned

The interesting security boundary in agentic commerce isn't the model, it's the interface between the model and the money. Keeping that interface tiny (one product ID, one quantity) makes the rest checkable.

## What's next

Live store connectors (Shopify Admin API, WooCommerce) with scheduled syncs, multi-user accounts and 2FA for the Control Center, per-agent budgets and rate limits, published MCP server package, per-user mandates, Postgres for multi-instance deployments, merchant-signed catalogs, PayPal webhooks for asynchronous capture updates, and mandate templates for teams.

## Built with

python, mcp, fastapi, sqlalchemy, sqlite, pydantic, google-gemini, paypal-orders-v2, paypal-checkout, channel3, ag-grid, ag-studio, react, typescript, vite, tailwindcss
