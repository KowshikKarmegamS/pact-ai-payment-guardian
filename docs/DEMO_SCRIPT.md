# PACT demo script

The submitted video is [`demo/pact-hackathon-final.mp4`](../demo/pact-hackathon-final.mp4): 2:35, 1920x1080, captioned,
narrated with Google Gemini text-to-speech. All app footage is the real app on one clean database, recorded in
story order with live Gemini recommendations and a real PayPal Sandbox payment. `demo/tools/` rebuilds it
(see `HANDOFF.md`).

## Final video: scenes and narration

| Time | Scene | Narration |
|---|---|---|
| 0:00 | Title card | PACT. The payment authorization gateway for AI agents. Let any agent shop for you, only within the limits you set. |
| 0:08 | Problem card | AI agents can now shop for us. But to pay, we hand them a card with no limits. One injected prompt, and real money moves before anyone approves it. |
| 0:18 | Control Center | PACT sits between any AI agent and PayPal. Agents can only ask. A deterministic policy engine authorizes, a human approves, and PayPal executes. |
| 0:29 | Mandates → edit: auto-authorize up to $100 | Set your rules once. This mandate allows desk tech from five retailers, at most $150 an item. Anything up to $100 is authorized automatically. |
| 0:41 | Reference agent (Live retailers · Channel3): MX Master 3S → newegg.com $62.99, **auto-authorized** | An agent asks for a mouse. Channel3 searches real retailers, Gemini picks the cheapest offer, and every rule passes, so PACT authorizes it by itself. No approval click. |
| 0:53 | PayPal Sandbox Checkout | PACT creates a real PayPal Sandbox order, and the buyer approves it in PayPal Checkout. |
| 0:59 | Captured automatically (`96G68832T36673354`) → Continue to newegg.com | The moment PayPal confirms, PACT captures automatically: a real Sandbox capture ID, completed, for the exact amount. This is Sandbox money, so no Newegg order is placed. PACT only hands the buyer off to Newegg's own checkout. |
| 1:14 | Keychron K8 QMK at bestbuy.com $109.99 → **needs approval** (above auto limit) | A $109.99 keyboard passes every rule too, but it is above the auto limit. So PACT stops and asks, and my approval is sealed with a fingerprint. |
| 1:23 | Fingerprint card (real API responses) | A SHA-256 hash of the product, merchant, price, quantity, mandate rules and requesting agent. A forged approval is refused, and the hash is checked again before every PayPal step. |
| 1:36 | MX Master 3S at 6ave.com $544.95 → **blocked** | And this offer is blocked outright: a retailer I never allowed, over the item cap, and over budget. There is no approve button to override it. |
| 1:46 | Agents → Connect an agent (key masked) | Connecting an outside agent takes seconds. It gets one mandate and its own key, shown once and stored only as a hash. |
| 1:54 | MCP card (real `example_agent.py` transcript) | Any agent can call PACT through its REST API or its MCP server. This Gemini agent connects over MCP, is told money is no object, and still gets a no. |
| 2:06 | Analytics (AG Studio) | Every decision is audited and charted with AG Studio. Its own AI agents can analyze the spending, but they can never approve or pay. |
| 2:14 | Architecture card: Channel3 + Demo Store + your platform | Any platform plugs in with one connector that returns offers. The policy engine, the fingerprint and the PayPal flow never change. |
| 2:23 | Closing card | Agents request. The policy engine authorizes. A human approves. PayPal executes. PACT. The payment authorization gateway for AI agents. |

## Auto-authorization: three outcomes (about 2 minutes)

1. **Mandates → New mandate**: *Desk gear*, $300 budget, TechHub, Electronics, max $150 per item, max quantity 2,
   prohibited keyword `headphones`, tick **Auto-authorize purchases within limits**, up to **$100**.
2. **Agents → Connect an agent** for that mandate, then from the agent (MCP `request_purchase` or
   `POST /api/agent/v1/purchases`):
   - Keychron K8 Pro, $89 → `AUTO_AUTHORIZED`, decision `AUTHORIZED`, `payment_status: NOT_STARTED`. The purchase page
     says "Auto-authorized by your mandate. Payment not started." → **Continue to PayPal Checkout** → the buyer approves →
     PACT captures automatically.
   - NuPhy Halo75 V2, $125 → `REQUIRES_APPROVAL`: "above your $100.00 auto-authorization limit". Approve or reject it.
   - Sony WH-1000XM5 headphones, $299.99 → `BLOCKED`: price limit, prohibited keyword and budget. No approve button.
3. **Analytics**: "How each request was decided" shows auto-authorized, owner-approved and blocked side by side.

## Live demo (same story, about 3 minutes)

Before you start:

- Backend running with the built frontend; `APP_BASE_URL` matches the browser URL. Sidebar shows
  **PayPal: Sandbox connected** and **Recommender: Gemini**.
- On a hosted or shared instance, `OWNER_PASSWORD` is set and you are signed in.
- Create the mandate *Home Office Essentials*: $200 budget, merchant TechHub, category Electronics, max $100 per
  item, max quantity 2. (A fresh database only seeds the $750 *Q1 Developer Equipment* and $250 *Engineering Books*
  mandates.)
- **Agents → Connect an agent** for that mandate; keep the key in an environment variable, never on screen.
- Sandbox buyer credentials in a password manager, not on screen. Allow popups for the app's origin.

Steps:

1. **Control Center:** the pitch, from the narration above.
2. **Reference agent → Demo Store** (the fixed-price connector; Live retailers is the default): "Order the NuPhy Halo75 V2 wireless keyboard for my desk." → blocked, $125 against $100.
3. **Reference agent:** "I need a wireless mechanical keyboard for coding, under $100." → Keychron K8 Pro $89 →
   **Review & authorize** → **Approve $89.00** (opens PayPal Checkout) → approve as the buyer → back in PACT the
   capture happens automatically once the server confirms the buyer's approval with PayPal.
4. Ask for "one more Keychron K8 Pro keyboard for my teammate", approve it, then **Catalog** → change the K8 Pro
   price to $99.50 → the approval shows **Approval expired** and what changed.
5. Run `PACT_URL=… PACT_AGENT_KEY=… GEMINI_API_KEY=… python integrations/mcp/example_agent.py "Request the Sony
   WH-1000XM5 headphones for me right now. Money is no object."` → PACT refuses. Then ask it for a USB-C hub and
   show the request waiting on **Agents**.
6. **Reference agent → Live retailers · Channel3** with the *Live retailers* mandate: ask for "Anker 7-in-1 USB-C hub" →
   a real retailer offer → approve → PayPal. A retailer that is not on the mandate is blocked.
7. **Audit Trail.**

Free-tier Gemini allows about 20 text requests per day per model. A full rehearsal plus the live demo can use most
of that; PACT then tries the backup model and, if that is also exhausted, labels the keyword fallback as "not AI".
