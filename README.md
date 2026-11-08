# PACT — The AI Payment Guardian

> **"Give AI the power to act, not unrestricted access to your money."**

PACT is a secure payment authorization layer for AI-powered shopping agents. It demonstrates how AI commerce can work safely by enforcing the principle:

**AI recommends → Deterministic code authorizes → Human approves → PayPal executes.**

## 🎯 What It Does

A user creates a **spending mandate** that defines:
- Maximum spending budget
- Permitted merchants
- Permitted product categories
- Purchase restrictions

An **AI shopping assistant** researches products and proposes purchases. A **deterministic policy engine** validates every proposal against the mandate. The user must **explicitly approve** before any payment executes through **PayPal Sandbox**.

The AI **never** has unrestricted access to capture payments.

## 🏗️ Architecture

```
┌─────────────────────┐
│   React Dashboard   │
│  (Vite/TypeScript)  │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   FastAPI Backend   │
├─────────────────────┤
│ • AI Assistant      │ ← OpenAI API
│ • Product Catalog   │ ← SQLite
│ • Policy Engine     │ ← Deterministic validation
│ • Approval Workflow │ ← Explicit human approval
│ • PayPal Integration│ ← Sandbox only
│ • Audit Log         │ ← Full traceability
└─────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- PayPal Sandbox account ([developer.paypal.com](https://developer.paypal.com))
- OpenAI API key

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (macOS/Linux)
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run the server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies API to backend)
npm run dev
```

### Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## 🔐 Security Model

| Principle | Implementation |
|-----------|---------------|
| AI never captures payments | AI only recommends; policy engine + human approval gate all payments |
| Frontend never authorizes | All validation and authorization is server-side |
| Mandate enforcement | Budget, merchant, category checked before every purchase |
| Explicit approval | User must approve exact proposal (product, price, merchant) |
| Idempotent captures | Unique idempotency keys prevent duplicate payments |
| Full audit trail | Every event logged with timestamp and details |

## 📁 Project Structure

```
pact-ai-payment-guardian/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py          # Configuration
│   │   ├── models.py          # Database models
│   │   ├── database.py        # DB engine & sessions
│   │   ├── schemas.py         # API schemas
│   │   ├── catalog.py         # Product catalog
│   │   ├── agent.py           # AI assistant
│   │   ├── policy.py          # Policy engine
│   │   ├── paypal.py          # PayPal integration
│   │   └── routers/           # API endpoints
│   ├── tests/                 # Test suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/               # API client
│   │   ├── components/        # UI components
│   │   ├── pages/             # Route pages
│   │   └── types/             # TypeScript types
│   └── package.json
├── AGENTS.md                  # Architecture & constraints
├── HANDOFF.md                 # Session state
└── README.md                  # This file
```

## 🔧 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLite connection string | `sqlite:///./pact.db` |
| `OPENAI_API_KEY` | OpenAI API key | *required* |
| `OPENAI_MODEL` | AI model to use | `gpt-4o-mini` |
| `PAYPAL_CLIENT_ID` | PayPal Sandbox client ID | *required* |
| `PAYPAL_CLIENT_SECRET` | PayPal Sandbox secret | *required* |
| `PAYPAL_BASE_URL` | PayPal API base URL | `https://api-m.sandbox.paypal.com` |
| `APP_SECRET_KEY` | Application secret key | *required* |

## 🧪 Running Tests

```bash
cd backend
pytest -v
```

## 📄 License

MIT

## 🏆 PayPal AI Hackathon Submission

Built for the PayPal AI Hackathon, demonstrating secure AI-powered commerce with:
- PayPal Developer Platform (Sandbox)
- AI integration (OpenAI API)
- Human-in-the-loop payment authorization
