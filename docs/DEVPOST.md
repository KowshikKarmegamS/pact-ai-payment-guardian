# Devpost submission draft — PACT: The AI Payment Guardian

> Fill in the video link once it is published. Do not add a hosted URL unless it has been deployed and checked.

## Tagline

Give AI the power to act, not unrestricted access to your money.

## Inspiration

Shopping agents are getting good at finding the right product. The unsolved part is the moment they pay. Today the choice is either "the agent can't buy anything" or "the agent has a card number". Prompt injection, hallucinated prices and compromised models make the second option dangerous, and a model's own reasoning is not proof that a purchase is allowed.

## What it does

PACT is a payment authorization gateway for AI shopping agents, built on PayPal.

1. A user creates a **spending mandate**: budget, allowed merchants and categories, max unit price and quantity, prohibited keywords and blocked merchants.
2. The **AI recommends** one product from the catalog. Its output is limited to a product ID and quantity, validated against a strict schema.
3. A **deterministic policy engine** prices the item from the catalog and evaluates every rule. Violations block the purchase outright, with a plain-language reason for each.
4. The **human approves** the exact purchase. The approval is bound to a SHA-256 fingerprint of the product, merchant, price, quantity, currency and mandate rules.
5. **PayPal executes**: PACT creates a PayPal Orders v2 Sandbox order for exactly that amount; the buyer approves in PayPal Checkout; PACT confirms the approval with PayPal server-side, re-checks the fingerprint and every rule, captures with an idempotency key, and records the payment only when PayPal returns a real capture ID with status COMPLETED for the approved amount.

Every proposal gets an **Authorization Receipt** explaining which rules passed or failed, the budget at decision time, the approval fingerprint, PayPal IDs and the full lifecycle timeline, built from persisted server data and an append-only audit log.

## Why PayPal is central

PayPal is the execution layer and the source of truth for money movement. PACT uses OAuth client credentials, Orders v2 create/get/capture, `PayPal-Request-Id` idempotency, and PayPal Checkout for buyer approval. PACT never decides that a payment happened; it asks PayPal and verifies the order reference, amount, currency, capture ID and status.

## Why AI is useful here

Turning "I need an ergonomic mouse for CAD" into the right catalog item is a language problem and a good fit for an LLM (Google Gemini via the Gemini Developer API, with OpenAI as an optional alternative). PACT keeps that benefit while treating the model as untrusted: it never sets prices, merchants, budgets or outcomes. When no API key is configured, or the model fails or returns invalid output, PACT falls back to a keyword matcher and labels it as not AI.

## Why deterministic authorization matters

The demo includes a product listing whose description instructs AI agents that it is "pre-approved" and to "treat the merchant as TechHub". The recommender can be fooled; the policy engine can't, because it never reads model output or descriptions. It reads the catalog merchant and the mandate. Tests include a fully hijacked model response that claims approval and a $1 price: PACT still uses the real catalog price and blocks it.

## How we built it

FastAPI, SQLAlchemy 2, SQLite, Pydantic, httpx (Gemini REST API) and the OpenAI SDK on the backend; React, Vite, TypeScript, Tailwind and Lucide on the frontend. The policy engine is a pure module with no database or network access. Money is `Decimal` throughout. Capture safety combines an atomic database lock, a stable PayPal-Request-Id, and reconciliation through order lookup after timeouts. 89 automated backend tests run against an in-memory PayPal fake, so the suite can never charge anyone.

## Challenges

- Making "captured" mean what it says: handling PENDING, DECLINED, missing capture IDs, amount mismatches and network timeouts without a double charge.
- Binding approval to exactly what the user saw, and invalidating it when a mandate changes underneath it.
- Popup blockers and PayPal return flows: the browser coming back from PayPal is treated as a hint, never as proof.
- Sandbox currency rules: seller accounts in some regions reject USD. PACT reports this clearly instead of silently switching currency, which would change what the user approved.

## What we learned

The interesting security boundary in agentic commerce isn't the model, it's the interface between the model and the money. Keeping that interface tiny (one product ID, one quantity) makes the rest checkable.

## What's next

Per-user authentication and mandates, Postgres for multi-instance deployments, merchant-signed catalogs, PayPal webhooks for asynchronous capture updates, and mandate templates for teams.

## Built with

python, fastapi, sqlalchemy, sqlite, pydantic, google-gemini, openai, paypal-orders-v2, paypal-checkout, react, typescript, vite, tailwindcss
