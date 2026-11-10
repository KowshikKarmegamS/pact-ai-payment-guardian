# PACT UI redesign plan

Goal: make PACT read as a premium fintech security product within five seconds, without
changing what is true about it. Every number on screen stays real backend data.

## What is weak today

| Area | Problem |
|---|---|
| Identity | Light slate admin look; nothing says "payment security". |
| Dashboard | Stat tiles and lists; no visual of spending vs. mandate, no clear entry point to the assistant. |
| Assistant | Recommendation, approval, PayPal and receipt are all stacked in one long card. The approval moment has no weight. |
| Approval | No before/after budget impact; blocked rules do not show attempted vs. allowed values side by side. |
| Mandates | No expiry, no revoke, form gives no sense of "what the AI may and may not do". |
| Transactions | Detail opens in a modal on top of a table; statuses are badges only. |
| Audit | Flat list with raw JSON; no per-transaction story. |
| Feedback | No toasts, no skeletons, no confirm dialogs for destructive actions. |
| Demo story | No way to show "the price changed after approval" from the UI. |

## Design system

- Dark-first. Background `#0A0D14` (ink), raised surfaces `#10141D` / `#151A25`, hairline borders `#222A38`.
- Text: `#E8ECF4` primary, `#9AA4B8` secondary, `#667085` muted (warm-neutral greys, not pure blue).
- Accent: one blue-violet (`#6E8BFF` → `#8B7CFF`) used for primary actions, focus rings and the active nav item only.
- Semantic: emerald `#34D399` = authorized/captured, red `#F87171` = blocked/danger, amber `#FBBF24` = waiting on a human,
  sky `#38BDF8` = in PayPal's hands. Each status always uses the same colour everywhere.
- Type: Inter for UI, JetBrains Mono for IDs, fingerprints and amounts in tables (tabular numerals everywhere money appears).
- Radius 10/14 px, 1px borders, almost no shadows; depth comes from surface steps.
- Motion: 150–250 ms fades/slides on mount, a progress sequence while the AI works, a single success pulse on capture.
  Respects `prefers-reduced-motion`.
- Components (`src/components/ui/`): Button, Badge/StatusPill, Card, Stat, Skeleton, Dialog, ConfirmDialog, Toast,
  Field, Tabs/Segmented, Meter, Ring, ProductTile, Timeline, Empty/Error states.

## Screens

1. **Command Center** (`/`): value proposition strip with the four-step pipeline, "Ask PACT" prompt box that jumps into the
   assistant, KPI row (captured spend, remaining budget, purchases evaluated, blocked, PayPal captures), budget ring per mandate,
   14-day decision chart (passed vs. blocked vs. captured), recent activity and security events.
2. **Mandates** (`/mandates`): each mandate as an authorization card: budget meter (spent / committed / remaining),
   "AI may" vs. "AI may not" columns, expiry, status, edit / pause / revoke (confirm dialog). Side-panel editor with validation and a live plain-language summary.
3. **Assistant** (`/assistant`): prompt composer with example prompts, staged processing state, recommendation card
   (product tile, merchant, price, why chosen, how it fits the mandate), alternatives with eligibility, and one action: *Review & authorize*.
4. **Authorization** (`/proposals/:id`): the critical screen. Verdict header, amount, budget impact (before → after),
   rule-by-rule evaluation with attempted vs. allowed values, AI summary, explicit approve/reject, then the PayPal journey
   (order → buyer approval → server verification → capture) and a verified result. PayPal returns land here.
5. **Transactions** (`/transactions`): searchable, filterable ledger with status pills; rows open the Authorization screen.
6. **Audit** (`/audit`): security timeline grouped by day with plain-language explanations, filters, and links to the transaction.
   Described as append-only and redacted; no tamper-proof claims.
7. **Catalog** (`/catalog`): the demo merchant feed. Lets a presenter change a price, which immediately invalidates approvals
   bound to the old price (the "silent change" defence).

## Backend additions required by the UX (small, additive)

- Mandate `expires_at` (policy rule `mandate_not_expired`, part of the fingerprint) and `revoked_at` (permanent, cannot be resumed).
- `PUT /api/products/{id}` price change with audit event and proactive approval invalidation.
- Alternatives: the generate response lists up to three other catalog matches with a deterministic eligibility preview;
  `POST /api/proposals/propose` creates a proposal for a user-selected catalog product (same policy path, no AI).
- PayPal return/cancel URLs point at `/proposals/{id}`.

## Not doing

- No new charting or animation libraries; charts are small hand-written SVG.
- No mock data, no simulated payment success, no stock photos of products (designed category tiles instead).
