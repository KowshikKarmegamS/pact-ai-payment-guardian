# PACT demo video script (target 2:40, hard limit 3:00)

Record real app footage only: PayPal Sandbox, real order and capture IDs, no edited numbers, no third-party music.

## Before recording

- Backend and frontend running (`APP_BASE_URL` must match the URL in the browser).
- Sidebar shows **PayPal: Sandbox connected**. For the AI path on camera, set `GEMINI_API_KEY` (free tier) and confirm the sidebar says **Google Gemini · gemini-2.5-flash**; otherwise the recommender is labelled **Heuristic (no AI key)** and you should say so.
- Sandbox personal (buyer) credentials ready in a password manager, not on screen.
- Optional: clear the assistant list ("Clear this list") so the screen starts empty.
- Allow popups for the app's origin, or use the "continue in this tab" link.

## Script

**0:00–0:20 · Problem** (Overview page)
"AI can now shop for us. But should it have unrestricted access to our money? One prompt injection in a product listing, one hallucinated price, and an agent with a card number spends money nobody approved."

**0:20–0:45 · PACT** (Overview → Mandates)
"PACT puts a deterministic gate between the agent and PayPal. AI recommends, code authorizes, a human approves, PayPal executes. This mandate allows $750 at approved merchants, Electronics and Books, at most $300 per item, and no consoles or games."

**0:45–1:15 · Recommendation and receipt** (Assistant → A · Safe purchase)
"I ask for an ergonomic mouse for CAD." Point at the recommendation-source badge (Gemini model or heuristic). "The AI only picked a product ID. The price, merchant and category come from the catalog. The policy engine ran 11 rules and every one passed; here's the receipt. It's waiting for me."

**1:15–1:40 · Security** (B, then C)
"Now: buy a PlayStation 5 for the office." Show BLOCKED and the six violations. "No approve button, no PayPal order." Click C. "This listing tells AI agents it's pre-approved and to pretend the merchant is TechHub. The policy engine never reads descriptions; the merchant is QuickDeals Marketplace, so it's blocked."

**1:40–2:20 · PayPal** (back to A)
Click **Approve $99.99 to TechHub**. "My approval is bound to this fingerprint; change anything and it's void." Click **Pay with PayPal (Sandbox)**, log in as the Sandbox buyer, approve. Back in PACT: "PACT just asked PayPal directly; PayPal says the buyer approved. Returning to the page proves nothing on its own." Click **Capture $99.99**. "Before capturing, the server re-verified the order, the amount, my approval and every rule. Here is PayPal's capture ID, status COMPLETED, for exactly $99.99."

**2:20–2:40 · Impact** (Transactions → Audit Trail)
Show the captured row with real order and capture IDs, then the audit timeline: recommendation, policy passed, human approved, order created, buyer approved, capture attempted, captured.

**Close:** "Let AI handle the shopping. Let users remain in control of the spending."

## Optional 15-second extra

Approve a second mouse, then change the mandate budget on the Mandates page. Back on the assistant the proposal shows **Approval expired** with the exact change listed, and capture is refused.
