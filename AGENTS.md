# AGENTS.md — PACT: The AI Payment Guardian

## Project Overview

PACT is a secure payment authorization layer for AI-powered shopping agents.
It demonstrates the principle: **AI recommends → Deterministic code authorizes → Human approves → PayPal executes.**

## Architecture

```
Frontend (React/Vite/TypeScript)
  └─► FastAPI Backend
        ├─► AI Shopping Assistant (OpenAI API)
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
| AI       | OpenAI API (configurable model)         |
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
│   │   ├── agent.py          # AI shopping assistant (OpenAI)
│   │   ├── policy.py         # Deterministic policy engine
│   │   ├── paypal.py         # PayPal API integration
│   │   ├── routers/          # API route handlers
│   │   │   ├── products.py
│   │   │   ├── mandates.py
│   │   │   ├── proposals.py
│   │   │   ├── payments.py
│   │   │   └── health.py
│   │   └── services/         # Business logic services
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

## Payment Flow

```
User creates spending mandate
  → User sends shopping request to AI
    → AI searches product catalog
      → AI proposes a purchase
        → Policy engine validates against mandate
          → If violations: BLOCKED (returned to user with reasons)
          → If passes: Proposal created with status "pending"
            → User reviews and explicitly approves
              → Backend revalidates mandate + amount
                → Backend creates PayPal order
                  → User completes PayPal checkout
                    → Backend captures payment (with idempotency)
                      → Audit log updated at every step
```

## API Design

- All endpoints under `/api/` prefix
- JSON request/response bodies
- Pydantic validation on all inputs
- Appropriate HTTP status codes
- Error responses include detail messages

## Environment Variables

See `backend/.env.example` for all required configuration. Key variables:
- `OPENAI_API_KEY` — OpenAI API key
- `OPENAI_MODEL` — Model name (default: gpt-4o-mini)
- `PAYPAL_CLIENT_ID` — PayPal Sandbox client ID
- `PAYPAL_CLIENT_SECRET` — PayPal Sandbox secret
- `PAYPAL_BASE_URL` — PayPal API base URL (sandbox)
- `APP_SECRET_KEY` — Application secret for signing

## Testing

- Policy engine tests must be pure unit tests (no database, no network)
- Use pytest fixtures for test data
- Test both passing and failing policy evaluations
- Integration tests should use test database

## AI Model Configuration

- Provider: OpenAI (configurable via env)
- Model: Configurable via `OPENAI_MODEL` env var
- The AI is used for product recommendation, NOT for payment decisions
- AI responses must be validated by the policy engine before any action
