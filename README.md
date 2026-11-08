# PACT — The AI Payment Guardian

> **"Give AI the power to act, not unrestricted access to your money."**

PACT is a secure payment authorization layer for autonomous AI-powered shopping agents. Built for the **PayPal AI Hackathon**, it demonstrates how AI commerce can work safely in the real world by enforcing a strict four-step lifecycle:

$$\text{AI Recommends} \longrightarrow \text{Deterministic Code Authorizes} \longrightarrow \text{Human Approves} \longrightarrow \text{PayPal Executes}$$

---

## 🎯 Executive Summary & Problem Solved

Autonomous AI shopping agents promise seamless commerce, but giving an LLM direct API access to capture funds or debit cards is an existential security flaw. Prompt injections, hallucinations, or compromised models could drain bank accounts.

**PACT introduces a deterministic barrier:**
1. A user establishes a **Spending Mandate** (budget envelope, merchant whitelist, category whitelist, max unit price, and keyword bans).
2. The **AI Shopping Assistant** researches products and proposes purchases with structured justifications.
3. The **Deterministic Policy Engine** evaluates the proposal against the mandate rules. Violations are instantly blocked with human-readable error reasons.
4. If the proposal passes, the user must give **Explicit Human Approval**.
5. The backend revalidates all rules server-side before initiating a **PayPal Sandbox Orders API v2** checkout.
6. The payment is captured only with an explicit human-in-the-loop confirmation and strict idempotency keys.

---

## 🏗️ Architecture

```text
┌────────────────────────────────────────────────────────┐
│                   React Dashboard                      │
│            (Vite / TypeScript / Tailwind CSS)          │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP JSON / REST
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Backend                     │
├────────────────────────────────────────────────────────┤
│ • AI Shopping Agent (OpenAI API + Heuristic Fallback)  │
│ • Deterministic Policy Engine (Pure Logic Validation)  │
│ • Mandates & Spending Envelopes Service                │
│ • PayPal Orders API v2 Client (OAuth2 + Capture)       │
│ • SQLite Database & Audit Trail Engine                 │
└────────────────────────────────────────────────────────┘
```

---

## 🔐 Security Invariants (Non-Negotiable)

- **AI Never Captures**: The AI model only formulates recommendations. It has no credentials or endpoints to capture payments directly.
- **Frontend Never Authorizes**: All mandate rules, budgets, item pricing, and merchant checks are computed and enforced server-side.
- **Server Revalidation**: The backend revalidates the mandate, budget, merchant, and category both *before* creating a PayPal order and *before* executing capture.
- **Idempotency Guarantees**: Every proposal has a unique UUID idempotency key passed to `PayPal-Request-Id` to prevent duplicate charges.
- **Immutable Audit Trail**: Every policy check, mandate change, approval, and capture is logged with sanitized details (credentials scrubbed).

---

## 🚀 Quick Start Guide (For Developers)

### Prerequisites

- **Python**: 3.12+
- **Node.js**: 18+ (tested on Node v22)
- **PayPal Developer Account**: Sandbox account from [developer.paypal.com](https://developer.paypal.com)
- **OpenAI API Key** *(Optional)*: Configurable model (defaults to `gpt-4o-mini`). If omitted, the built-in intelligent heuristic matcher runs seamlessly.

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/KowshikKarmegamS/pact-ai-payment-guardian.git
cd pact-ai-payment-guardian
```

---

### Step 2: Backend Setup (FastAPI)

1. Open a terminal and navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   # Windows
   copy .env.example .env
   # macOS / Linux
   cp .env.example .env
   ```

5. Edit `backend/.env` with your PayPal Sandbox credentials:
   ```env
   # Database
   DATABASE_URL=sqlite:///./pact.db

   # OpenAI (Optional - leave blank to use built-in heuristic agent)
   OPENAI_API_KEY=your-openai-api-key-here
   OPENAI_MODEL=gpt-4o-mini

   # PayPal Sandbox Credentials (from developer.paypal.com)
   PAYPAL_CLIENT_ID=your-sandbox-client-id
   PAYPAL_CLIENT_SECRET=your-sandbox-client-secret
   PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com

   # Security
   APP_SECRET_KEY=pact-secure-secret-key-2026
   CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173
   ```

6. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   - API will be live at: [http://localhost:8000](http://localhost:8000)
   - Interactive Swagger API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
   - *Note: On startup, the database automatically initializes tables and seeds the product catalog and default spending mandates!*

---

### Step 3: Frontend Setup (React / Vite)

1. Open a **new terminal tab** and navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install npm dependencies:
   ```bash
   npm install
   ```

3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   - Open your browser at: **[http://localhost:5173](http://localhost:5173)**

---

## 💳 Important PayPal Sandbox Configuration Note

If you receive the error:
> *"We’re sorry. This seller doesn’t accept payments in your currency."*

This is standard PayPal Sandbox behavior when an account is registered in a non-US region (such as India) where incoming foreign currency (USD) is blocked by default.

### Quick Fix (Takes 60 seconds):
1. Log in to [sandbox.paypal.com](https://www.sandbox.paypal.com) with your sandbox **Business/Seller** credentials.
2. Click the **Settings Gear** (top right) $\rightarrow$ **Account Settings** $\rightarrow$ **Payment Preferences** (or *Block Payments*).
3. Under **Block Payments**, find: *"Allow payments sent to me in a currency I do not hold"*.
4. Select: **"Yes, accept and convert them to USD"** (or primary currency).
5. Alternatively, create a US Sandbox Personal Buyer account under [developer.paypal.com $\rightarrow$ Sandbox Accounts](https://developer.paypal.com/dashboard/accounts).

---

## 🧪 Demo Script: Testing PACT End-to-End

### Scenario A: Successful Guarded Purchase (Policy Passes)
1. Open [http://localhost:5173/assistant](http://localhost:5173/assistant).
2. Select the active mandate: **"Q1 Developer Equipment & Workstation Peripherals"** ($750.00 budget).
3. Click the preset prompt: **"Ergonomic Mouse (Passes Policy)"** (or type *"I need an ergonomic mouse for CAD modeling"*).
4. **AI Reasoning**: Identifies the *Logitech MX Master 3S Advanced Wireless Mouse* ($99.99) from merchant *TechHub*.
5. **Guardian Evaluation**: Green **PASSED** banner confirming merchant whitelist, category, and budget envelope satisfied.
6. Click **"Human Approve & Authorize via PayPal Sandbox"**.
7. Click the **"PayPal Checkout"** button $\rightarrow$ log in with your sandbox personal buyer account and approve the payment.
8. Click **"Complete & Capture Payment via PayPal Sandbox"** $\rightarrow$ returns confirmed **Capture ID** with funds settled.

### Scenario B: Autonomous Violation Blocked (Policy Fails)
1. In the assistant, click **"PlayStation 5 (Fails Policy)"** (or type *"Can you purchase a PlayStation 5 console for the office?"*).
2. The AI identifies the *Sony PlayStation 5 Pro* ($699.99 from *Sony Direct*).
3. **Guardian Policy Engine**: Instantly triggers a red **BLOCKED** banner accumulating all rule violations:
   - ❌ *Merchant 'Sony Direct' is not on whitelist.*
   - ❌ *Category 'Gaming Consoles' is not permitted.*
   - ❌ *Item unit price $699.99 exceeds $300.00 limit.*
   - ❌ *Prohibited keyword: 'playstation'.*
4. Checkout is hard-disabled. No payment order can be generated.

---

## 📊 Running Automated Tests

Run the backend pytest suite covering policy evaluations, edge cases, and API routers:
```bash
cd backend
pytest -v
```
*Expected: 17 passed tests in < 0.5s.*

Verify the frontend build and TypeScript types:
```bash
cd frontend
npm run build
```
*Expected: Vite production build completes with 0 errors.*

---

## 📁 Repository Structure

```text
pact-ai-payment-guardian/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app & lifespan initialization
│   │   ├── config.py             # Pydantic Settings & credential masking
│   │   ├── database.py           # SQLAlchemy SQLite engine & session
│   │   ├── models.py             # ORM models (Product, Mandate, Proposal, AuditLog)
│   │   ├── schemas.py            # Pydantic request/response schemas
│   │   ├── catalog.py            # Seeded catalog & default mandates
│   │   ├── agent.py              # AI Shopping Assistant (OpenAI + heuristic fallback)
│   │   ├── policy.py             # Deterministic Policy Evaluation Engine
│   │   ├── paypal.py             # PayPal Orders API v2 integration
│   │   ├── routers/
│   │   │   ├── health.py         # Health check endpoint
│   │   │   ├── products.py       # Catalog query and filter endpoints
│   │   │   ├── mandates.py       # Mandate lifecycle & budget tracking
│   │   │   ├── proposals.py      # Proposal generation & human approval
│   │   │   ├── payments.py       # PayPal order creation & capture
│   │   │   └── audit.py          # Audit log retrieval
│   │   └── services/
│   │       ├── audit.py          # Audit event sanitization and persistence
│   │       └── mandate_service.py # Spent vs remaining budget math
│   ├── tests/
│   │   ├── conftest.py           # Test fixtures & test DB session
│   │   ├── test_policy.py        # Isolated deterministic policy engine unit tests
│   │   └── test_api.py           # Integration tests for proposals, approvals, & mandates
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts         # Generic fetch client with typed helpers
│   │   │   └── pact.ts           # Domain API service methods
│   │   ├── components/
│   │   │   └── Layout.tsx        # Navigation sidebar & responsive layout
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx     # Overview metrics & budget progress
│   │   │   ├── Mandates.tsx      # Spending mandates manager
│   │   │   ├── ShoppingAssistant.tsx # Chat UI with Guardian policy verification
│   │   │   ├── Transactions.tsx  # Proposal and payment ledger
│   │   │   └── AuditTrail.tsx    # Chronological compliance log
│   │   └── types/
│   │       └── index.ts          # TypeScript domain interfaces
│   ├── package.json
│   └── vite.config.ts
├── AGENTS.md                     # Architectural constraints for AI assistants
├── HANDOFF.md                    # State tracking between development sessions
└── README.md                     # This file
```

---

## 📄 License

This project is licensed under the MIT License.
