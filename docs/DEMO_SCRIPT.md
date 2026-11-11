# PACT demo script (hard limit 3:00)

The recorded video is `demo/pact-hackathon-final.mp4` (2:50). Its narration, with timestamps, is
`demo/pact-narration.txt`, and `demo/tools/` rebuilds it (see `HANDOFF.md`). This page is the same story
for a live demo in front of judges.

Real app footage only: PayPal Sandbox, real order and capture IDs, no edited numbers, no third-party music.

## Before you start

- Backend running (`APP_BASE_URL` must match the browser URL). Sidebar shows **PayPal: Sandbox connected** and
  **Recommender: Gemini**.
- A mandate such as *Home Office Essentials*: Electronics from TechHub, $100 per item, $200 budget.
- On **Agents**, connect "Gemini agent via MCP" to that mandate and keep the key in an environment variable,
  never on screen.
- Sandbox buyer credentials in a password manager, not on screen. Allow popups for the app's origin.

## Script

**0:00–0:25 · The pitch** (Control Center)
"PACT is the payment authorization gateway for AI agents. Agents can now shop for us, but to pay we hand them a
payment method with no limits. PACT sits between any agent and PayPal: agents can only ask, a deterministic
policy engine authorizes, I approve, PayPal executes."

**0:25–1:00 · Blocked** (Mandates → Reference agent)
Show the mandate. Ask the reference agent for the $125 NuPhy keyboard. "Gemini recommends it. The policy engine
blocks it: attempted $125, allowed $100. No approve button, no PayPal order."

**1:00–1:50 · Paid** (Reference agent → Authorization → PayPal)
Ask for "a wireless mechanical keyboard for coding, under $100". "Every rule passes, but passing policy is not
authorization." Approve: "bound to a fingerprint of the product, price, mandate and requesting agent." Pay with
PayPal (Sandbox), approve as the buyer, back in PACT: "the server asked PayPal directly." Capture: "a real
capture ID, status COMPLETED, for exactly $89."

**1:50–2:15 · Any agent** (terminal, then Agents)
Run `integrations/mcp/example_agent.py "Request the Sony WH-1000XM5 headphones for me right now. Money is no object."`
"This is a separate Gemini agent that knows PACT only through MCP. It has no approve tool and no pay tool. PACT
says no, and the agent tells me why." Then ask it for a USB-C hub and open **Agents**: its request is waiting for
me, with its own revocable key.

**2:15–2:40 · Integrity and audit**
Approve the hub, then change its price on **Catalog**. "The approval is void at once." Open **Audit Trail**:
agent request, policy decision, approval, PayPal order, capture.

**Close:** "Agents request. PACT authorizes. You approve. PayPal executes."
