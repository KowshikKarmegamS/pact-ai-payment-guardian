# PACT demo script

The submitted video is [`demo/pact-hackathon-final.mp4`](../demo/pact-hackathon-final.mp4): 2:54, 1920x1080, captioned,
narrated with Google Gemini text-to-speech. All app footage is the real app on one clean database, recorded in
story order with live Gemini recommendations and a real PayPal Sandbox payment. `demo/tools/` rebuilds it
(see `HANDOFF.md`).

## Final video: scenes and narration

| Time | Scene | Narration |
|---|---|---|
| 0:00 | Title card | PACT. The payment authorization gateway for AI agents. Let any agent shop for you, only within the limits you set. |
| 0:08 | Problem card | AI agents can now shop for us. But to pay, we hand them a card with no limits. One injected prompt, and real money moves before anyone approves it. |
| 0:18 | Control Center | PACT sits between any AI agent and PayPal. Agents can only ask. A deterministic policy engine authorizes, a human approves, and PayPal executes. |
| 0:29 | Mandates | It starts with a spending mandate. This one allows electronics from one merchant, up to $100 per purchase. |
| 0:37 | Reference agent asks for the $125 NuPhy | First, the built-in reference agent is asked for a keyboard that costs $125. Gemini recommends it. |
| 0:44 | Blocked receipt | Blocked. Attempted $125. Allowed $100. No approve button, no PayPal order. The AI cannot override the mandate. |
| 0:54 | $89 Keychron, 10/10 rules | Next, an $89 keyboard passes all ten rules. But passing policy is not authorization. |
| 1:02 | Owner approves | I review the budget impact and approve this exact purchase. My approval is sealed with a fingerprint. |
| 1:08 | Fingerprint card (real API responses: forged approval → 409) | A SHA-256 hash of the product, merchant, price, quantity, mandate rules and requesting agent. A forged approval is refused, and the hash is checked again before every PayPal step. |
| 1:21 | PayPal Sandbox Checkout | PACT creates a real PayPal Sandbox order, and the buyer approves it in PayPal Checkout. |
| 1:27 | Verified with PayPal | Back in PACT, the server asks PayPal directly whether the buyer approved. Only then can the payment be captured. |
| 1:34 | Captured | Captured. A real PayPal capture ID, status COMPLETED, for exactly $89. |
| 1:41 | Second approval, price change | What if something changes after approval? I approve a second keyboard. Then the merchant raises the price. |
| 1:48 | Approval voided | The approval is void at once. A change can never silently inherit an old approval. |
| 1:54 | Agents → Connect an agent (key masked) | Connecting an outside agent takes seconds. It gets one mandate and its own key, shown once and stored only as a hash. |
| 2:02 | MCP card (real transcript of `example_agent.py`) | Claude, ChatGPT or your own agent use PACT's API or MCP server. Told money is no object, this Gemini agent still gets a no. |
| 2:14 | Agents page | In-policy requests wait for you, and every step lands in the audit trail. Agents can ask. Only you approve. |
| 2:22 | Catalog → Sync Northwind Supply (Shopify format) → Northwind cable blocked | And PACT isn't tied to one catalog. A Shopify-format store syncs in, and its offers face the same rules. This cable is blocked, because that store isn't on my mandate. |
| 2:34 | Architecture card: any agent, any store, one gateway | Any platform plugs in with one connector that returns offers. The policy engine, the fingerprint and the PayPal flow never change. |
| 2:42 | Closing card | Agents request. The policy engine authorizes. A human approves. PayPal executes. PACT. The payment authorization gateway for AI agents. |

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
2. **Reference agent:** "Order the NuPhy Halo75 V2 wireless keyboard for my desk." → blocked, $125 against $100.
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
