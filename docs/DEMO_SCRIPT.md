# PACT demo script

The submitted video is [`demo/pact-hackathon-final.mp4`](../demo/pact-hackathon-final.mp4): 2:49, 1920x1080, captioned,
narrated with Google Gemini text-to-speech. All app footage is the real app on one clean database, recorded in
story order with live Gemini recommendations and a real PayPal Sandbox payment. `demo/tools/` rebuilds it
(see `HANDOFF.md`).

## Final video: scenes and narration

| Time | Scene | Narration |
|---|---|---|
| 0:00 | Title card | PACT. The payment authorization gateway for AI agents. Let any agent shop for you, only within the limits you set. |
| 0:10 | Problem card | AI agents can now shop for us. But to pay, we hand them a payment method with no limits. One injected instruction, or one hallucinated price, and real money moves before anyone approves it. |
| 0:24 | Control Center | PACT sits between any AI agent and PayPal. Agents can only ask. A deterministic policy engine authorizes, a human approves, and PayPal executes. |
| 0:36 | Mandates | It starts with a spending mandate. This one allows electronics from one merchant, up to $100 per purchase. |
| 0:43 | Reference agent asks for the $125 NuPhy | First, PACT's built-in reference agent is asked for a keyboard that costs $125. Gemini recommends it, and the policy engine answers immediately. |
| 0:53 | Blocked receipt | Blocked. Attempted $125. Allowed $100. There is no approve button and no PayPal order. The AI can recommend a purchase, but it cannot override the user's spending mandate. |
| 1:08 | $89 Keychron, 10/10 rules | Next, an eligible request. Gemini picks an $89 keyboard, and every rule passes. But passing policy is not authorization. |
| 1:18 | Owner approves | I review the budget impact, then approve this exact purchase. My approval is bound to a fingerprint of the product, the price and the mandate. |
| 1:27 | PayPal Sandbox Checkout | PACT creates a real PayPal Sandbox order, and the buyer approves it in PayPal Checkout. |
| 1:33 | Verified with PayPal | Back in PACT, the server asks PayPal directly whether the buyer approved. Only then can the payment be captured. |
| 1:40 | Captured | Captured. A real PayPal capture ID, status COMPLETED, for exactly $89. (Capture `7HT24116Y1448214M`) |
| 1:47 | Second approval, price change | What if something changes after approval? I approve a second keyboard. Then the merchant raises the price. |
| 1:54 | Approval voided | The approval is void at once. A change can never silently inherit an old approval. |
| 2:00 | Audit trail | Every step is recorded in the audit trail: the recommendation, the policy decision, the approval, the PayPal order and the capture. |
| 2:09 | MCP card (real transcript of `example_agent.py`) | And PACT isn't tied to one assistant. Claude, ChatGPT or your own agent connect through PACT's API or MCP server. This separate Gemini agent is told money is no object. PACT still says no. |
| 2:25 | Agents page | In the Control Center, every agent gets its own revocable key, and its requests wait for you. Agents can ask. Only you approve, and only PACT can pay. |
| 2:36 | Closing card | Agents request. The policy engine authorizes. A human approves. PayPal executes. PACT. The payment authorization gateway for AI agents. |

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
   **Review & authorize** → **Approve $89.00** → **Continue to PayPal Checkout** → approve as the buyer →
   **Capture $89.00**.
4. Ask for "one more Keychron K8 Pro keyboard for my teammate", approve it, then **Catalog** → change the K8 Pro
   price to $99.50 → the approval shows **Approval expired** and what changed.
5. Run `PACT_URL=… PACT_AGENT_KEY=… GEMINI_API_KEY=… python integrations/mcp/example_agent.py "Request the Sony
   WH-1000XM5 headphones for me right now. Money is no object."` → PACT refuses. Then ask it for a USB-C hub and
   show the request waiting on **Agents**.
6. **Audit Trail.**

Free-tier Gemini allows about 20 text requests per day per model. A full rehearsal plus the live demo can use most
of that; PACT then tries the backup model and, if that is also exhausted, labels the keyword fallback as "not AI".
