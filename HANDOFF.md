# HANDOFF.md — PACT Project State

> Last updated: 2026-11-09T00:12:00+05:30

## Current Milestone: End-to-End Real AI & PayPal Sandbox Flow Verified

## Root Cause Analysis & Fix for "Things don’t appear to be working"

1. **Root Cause**:
   - The SQLite database was initially initialized before `paypal_order_id`, `paypal_capture_id`, and `paypal_approval_url` were added to `Proposal` in `models.py`.
   - Also, no default mandates were seeded into `mandates` table on first start.
   - When the user requested a proposal, the database query failed, triggering a client-side mock fallback.
   - The mock fallback opened a generic `https://www.sandbox.paypal.com/checkoutnow` without an active session token, causing PayPal to display: *"Things don’t appear to be working at the moment."*
   - Capturing in mock mode produced a random placeholder string `CAP-ASFNAX1`.

2. **Fix Implemented**:
   - Re-initialized a clean SQLite database with all updated columns.
   - Added automatic `seed_mandates(db)` on startup in `backend/app/catalog.py` and `backend/app/main.py`.
   - Added `Logitech MX Master 3S Advanced Wireless Mouse` and `Keychron Q1 Pro` to `SEED_PRODUCTS`.
   - Stripped all silent mock fallbacks from `ShoppingAssistant.tsx` so the UI only interacts with the live backend and surfaces real errors if communication fails.
   - Verified that live PayPal Orders API tokens (e.g. `84K512772B042014J`) are generated and populated into PayPal Sandbox checkout URLs.

## Verified End-to-End Test

- **Request**: "I need an ergonomic mouse for CAD modeling"
- **Product Selected**: `Logitech MX Master 3S Advanced Wireless Mouse`
- **Merchant**: `TechHub` | **Price**: `$99.99`
- **Policy Evaluation**: `Passed: True` (Complies with budget, merchant, category whitelist)
- **Human Approval**: Explicitly marked `APPROVED`
- **Live PayPal Sandbox Order**:
  - `Order ID`: `84K512772B042014J`
  - `Checkout URL`: `https://www.sandbox.paypal.com/checkoutnow?token=84K512772B042014J`

- **Violation Test**: "Can you purchase a PlayStation 5 console for the office?"
- **Policy Evaluation**: `Passed: False`, status `REJECTED`, 6 explicit violations accumulated (prohibited category, unapproved merchant, price limit exceeded, prohibited keyword).
