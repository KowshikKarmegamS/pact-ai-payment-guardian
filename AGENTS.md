# AGENTS.md — PACT: The AI Payment Guardian

## Project Overview

PACT is a secure payment authorization layer for AI-powered shopping agents.
It demonstrates the principle: **AI recommends → Deterministic code authorizes → Human approves → PayPal executes.**

## Architecture

```
Frontend (React/Vite/TypeScript)
  └─► FastAPI Backend
        ├─► AI Shopping Assistant (Google Gemini API or OpenAI API)
        ├─► Product Catalog (SQLite)
        ├─► Deterministic Policy Engine
        ├─► Approval Workflow
        ├─► PayPal Integration (Sandbox)
        └─► Database & Audit Log
```

## Technology Stack

| Layer    | Technology                              |
|----------|-----------------------------------------|
| Backend  | Python, FastAPI, Pydantic, SQLAlchemy   |
| Database | SQLite                                  |
| Frontend | React, Vite, TypeScript, Tailwind CSS   |
| AI       | Google Gemini Developer API (default) or OpenAI |
| Payment  | PayPal REST API v2 (Sandbox)            |
| Icons    | Lucide React                            |

## Directory Structure

```
pact-ai-payment-guardian/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI application entry
│   │   ├── config.py         # Pydantic Settings, env loading
│   │   ├── models.py         # SQLAlchemy ORM models
│   │   ├── database.py       # Database engine & session
│   │   ├── schemas.py        # Pydantic request/response schemas
│   │   ├── catalog.py        # Product catalog seeding
│   │   ├── agent.py          # AI shopping assistant (Gemini / OpenAI)
│   │   ├── policy.py         # Deterministic policy engine (pure)
│   │   ├── money.py          # Decimal helpers
│   │   ├── paypal.py         # PayPal API integration (Sandbox only)
│   │   ├── routers/          # API route handlers
│   │   │   ├── products.py
│   │   │   ├── mandates.py
│   │   │   ├── proposals.py
│   │   │   ├── payments.py
│   │   │   └── health.py
│   │   └── services/         # audit, mandate budgets, authorization (fingerprint/revalidation)
│   ├── tests/                # Pytest test suite
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/              # API client
│   │   ├── components/       # Shared components
│   │   ├── pages/            # Route pages
│   │   └── types/            # TypeScript interfaces
│   ├── package.json
│   └── vite.config.ts
├── AGENTS.md                 # This file
├── README.md
├── HANDOFF.md
└── .gitignore
```

## Security Constraints (NON-NEGOTIABLE)

These rules must be followed in ALL code changes:

1. **AI must NEVER directly call PayPal capture.** The AI produces recommendations only. A deterministic policy engine and explicit human approval gate every payment.

2. **Frontend must NEVER be trusted to authorize a payment.** All authorization decisions happen server-side.

3. **Backend must revalidate** the mandate, amount, merchant, category, and product before both approval and capture.

4. **Budget enforcement is mandatory.** A purchase exceeding the mandate budget MUST be blocked.

5. **User approval must be explicit** and tied to the exact proposal (product, price, merchant, quantity). If any of these change, the approval is invalidated.

6. **Idempotency keys** must be used to prevent duplicate PayPal captures.

7. **Never commit** API keys, secrets, or `.env` files.

8. **Never log** credentials or sensitive payment data (card numbers, tokens, etc.).

9. **Audit everything.** All significant events (mandate creation, policy evaluation, approval, capture, rejection) must be recorded in the audit log.

10. **PayPal Sandbox only.** Never use production PayPal endpoints.

## Payment Flow and State Machine

Persisted `ProposalStatus` values (see `backend/app/models.py`):

```
AWAITING_HUMAN_APPROVAL -> HUMAN_APPROVED -> AWAITING_PAYPAL_BUYER_APPROVAL
  -> PAYPAL_BUYER_APPROVED -> CAPTURE_PENDING -> CAPTURED
Side exits: POLICY_REJECTED, HUMAN_REJECTED, PAYPAL_CANCELLED, PAYMENT_FAILED, APPROVAL_EXPIRED
```

1. `POST /api/proposals/generate` — AI picks `{product_id, quantity}`; catalog sets price/merchant;
   `PolicyEngine` evaluates; proposal fingerprint (SHA-256, `services/authorization.py`) stored.
2. `POST /api/proposals/{id}/approve` with `{expected_fingerprint}` — must match; policy re-run.
3. `POST /api/payments/{id}/create-order` — fingerprint + policy re-verified; one PayPal order per proposal.
4. `POST /api/payments/{id}/verify` — server asks PayPal; never captures.
5. `POST /api/payments/{id}/capture` — atomic lock, PayPal order verified (id, reference, amount,
   currency, status APPROVED), fingerprint + policy re-verified, capture with `PayPal-Request-Id`,
   CAPTURED only on a real capture ID with status COMPLETED and matching amount/currency.
6. `PUT /api/mandates/{id}` — re-verifies every in-flight approval; mismatches become APPROVAL_EXPIRED.
7. `GET /api/proposals/{id}/receipt` — Authorization Receipt from persisted data.

Rules for changes:
- Never set CAPTURED, a capture ID, or a capture status that PayPal did not return.
- Any new field that affects what the user approved must be added to `canonical_snapshot()`.
- Money is `Decimal` (`app/money.py`); never float.
- Schema changes must be additive and listed in `_ADDITIVE_COLUMNS` (`app/database.py`).

## API Design

- All endpoints under `/api/` prefix
- JSON request/response bodies
- Pydantic validation on all inputs
- Appropriate HTTP status codes
- Error responses include detail messages

## Environment Variables

See `backend/.env.example` for all required configuration. Key variables:
- `AI_PROVIDER` — `auto` (default), `gemini` or `openai`
- `GEMINI_API_KEY` / `GEMINI_MODEL` — Google Gemini Developer API (default model gemini-3.5-flash)
- `OPENAI_API_KEY` / `OPENAI_MODEL` — optional OpenAI alternative (default gpt-4o-mini)
- `PAYPAL_CLIENT_ID` — PayPal Sandbox client ID
- `PAYPAL_CLIENT_SECRET` — PayPal Sandbox secret
- `PAYPAL_BASE_URL` — PayPal API base URL (sandbox)
- `APP_SECRET_KEY` — Application secret for signing

## Testing

- Policy engine tests must be pure unit tests (no database, no network)
- Tests must never reach PayPal, Gemini or OpenAI: use the `fake_paypal` fixture; `conftest.py` pins env vars
  and blocks real PayPal HTTP for every test
- Use pytest fixtures for test data
- Test both passing and failing policy evaluations
- Integration tests should use test database

## AI Model Configuration

- Provider: Google Gemini (default) or OpenAI, selected by `AI_PROVIDER`
- Model: `GEMINI_MODEL` / `OPENAI_MODEL`
- API keys go in request headers, never in URLs or logs
- The AI is used for product recommendation, NOT for payment decisions
- AI responses must be validated by the policy engine before any action
