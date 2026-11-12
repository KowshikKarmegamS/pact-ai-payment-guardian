#!/usr/bin/env python3
"""PACT MCP server: lets any MCP-capable AI agent (Claude Desktop, Claude Code, ChatGPT connectors,
custom agents) ask PACT for spending authority.

Standard library only. Speaks MCP over stdio (newline-delimited JSON-RPC 2.0) and forwards each tool
call to the PACT Agent Gateway (/api/agent/v1) with the agent's own key.

  PACT_URL=http://localhost:8001  PACT_AGENT_KEY=pact_agent_...  python pact_mcp_server.py

Tools exposed to the model:
  search_catalog, check_spending_authority, evaluate_purchase, request_purchase, get_purchase_status

There is deliberately no approve, pay or capture tool. The model can ask; PACT's policy engine decides;
a human approves the exact purchase in the PACT Control Center; PayPal executes.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SERVER_INFO = {"name": "pact-payment-authorization", "version": "1.2.0"}
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")

INSTRUCTIONS = (
    "PACT is the payment authorization gateway between you and the user's money. You can look up the user's "
    "spending authority, search the catalog, dry-run a purchase and request one. You cannot approve or pay: "
    "every purchase needs the human's explicit approval in the PACT Control Center, and PayPal executes only "
    "after that. If PACT blocks a purchase, explain the reason to the user instead of retrying it."
)

TOOLS = [
    {
        "name": "check_spending_authority",
        "description": "Show the spending mandates this agent may use: remaining budget, per-item limit, "
                       "allowed categories and merchants, and expiry. Call this before proposing a purchase.",
        "inputSchema": {"type": "object", "properties": {
            "mandate_id": {"type": "string", "description": "Optional: one mandate. Omit to list all granted mandates."}},
            "additionalProperties": False},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "search_catalog",
        "description": "Search for products: PACT's catalog plus live retailer offers from Channel3 (100M+ products, "
                       "25k+ retailers). Each result has a PACT product_id; the merchant is the retailer's domain. "
                       "Prices come from the catalog or the retailer; you cannot set a price, and you cannot buy "
                       "directly: request_purchase is the only way to buy.",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What the user wants, e.g. 'wireless headphones'"},
            "category": {"type": "string"},
            "live": {"type": "boolean", "description": "Include live retailer offers via Channel3 (default true)"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            "required": ["query"], "additionalProperties": False},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "evaluate_purchase",
        "description": "Dry run: would PACT's deterministic policy engine allow this purchase? Creates nothing.",
        "inputSchema": {"type": "object", "properties": {
            "mandate_id": {"type": "string"}, "product_id": {"type": "integer"},
            "quantity": {"type": "integer", "minimum": 1, "maximum": 20}},
            "required": ["mandate_id", "product_id"], "additionalProperties": False},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "request_purchase",
        "description": "Request a purchase. PACT's deterministic policy engine decides: AUTO_APPROVE (within the "
                       "owner's auto-authorization limit), REQUIRES_APPROVAL (waits for the owner in the PACT Control "
                       "Center) or BLOCKED (explain the reason; do not retry). Authorization is NOT payment: "
                       "payment_status stays NOT_STARTED until the owner completes PayPal Checkout. Give the user the "
                       "approval link from the result.",
        "inputSchema": {"type": "object", "properties": {
            "mandate_id": {"type": "string"}, "product_id": {"type": "integer"},
            "quantity": {"type": "integer", "minimum": 1, "maximum": 20},
            "reason": {"type": "string", "description": "One sentence for the human: why this item"},
            "request_id": {"type": "string", "description": "Optional idempotency key so a retry does not duplicate"}},
            "required": ["mandate_id", "product_id", "reason"], "additionalProperties": False},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "get_purchase_status",
        "description": "Status of a purchase request this agent made: blocked, waiting for the human, paid "
                       "(with the PayPal capture id), declined or voided. Omit purchase_id to list recent requests.",
        "inputSchema": {"type": "object", "properties": {"purchase_id": {"type": "string"}},
                        "additionalProperties": False},
        "annotations": {"readOnlyHint": True},
    },
]


class GatewayError(Exception):
    pass


def _gateway(method: str, path: str, body=None, query=None):
    base = os.environ.get("PACT_URL", "http://localhost:8001").rstrip("/")
    key = os.environ.get("PACT_AGENT_KEY", "")
    if not key:
        raise GatewayError("PACT_AGENT_KEY is not set. Register this agent in the PACT Control Center (Agents page).")
    url = f"{base}/api/agent/v1{path}"
    if query:
        url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v not in (None, "")})
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "pact-mcp-server/1.2"})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read().decode() or "null")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode()).get("detail")
        except Exception:
            detail = None
        msg = detail.get("message") if isinstance(detail, dict) else str(detail or exc.reason)
        raise GatewayError(f"PACT refused ({exc.code}): {msg}") from None
    except urllib.error.URLError as exc:
        raise GatewayError(f"Cannot reach PACT at {base}: {exc.reason}") from None


def call_tool(name: str, args: dict):
    if name == "check_spending_authority":
        if args.get("mandate_id"):
            return _gateway("GET", f"/mandates/{urllib.parse.quote(args['mandate_id'])}/authority")
        return _gateway("GET", "/whoami")
    if name == "search_catalog":
        live = args.get("live", True)
        return _gateway("GET", "/catalog", query={"q": args.get("query"), "category": args.get("category"),
                                                  "limit": args.get("limit", 8),
                                                  "live": "true" if live else "false"})
    if name == "evaluate_purchase":
        return _gateway("POST", "/purchases/evaluate", {"mandate_id": args["mandate_id"],
                                                       "product_id": args["product_id"],
                                                       "quantity": args.get("quantity", 1)})
    if name == "request_purchase":
        return _gateway("POST", "/purchases", {k: args[k] for k in
                                               ("mandate_id", "product_id", "quantity", "reason", "request_id")
                                               if k in args})
    if name == "get_purchase_status":
        if args.get("purchase_id"):
            return _gateway("GET", f"/purchases/{urllib.parse.quote(args['purchase_id'])}")
        return _gateway("GET", "/purchases", query={"limit": 10})
    raise GatewayError(f"Unknown tool: {name}")


def handle(msg: dict):
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification (e.g. notifications/initialized): no reply
        return None
    if method == "initialize":
        asked = (msg.get("params") or {}).get("protocolVersion")
        version = asked if asked in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
        result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = msg.get("params") or {}
        try:
            data = call_tool(params.get("name", ""), params.get("arguments") or {})
            result = {"content": [{"type": "text", "text": json.dumps(data, indent=2)}],
                      "structuredContent": data if isinstance(data, dict) else {"items": data}, "isError": False}
        except (GatewayError, KeyError) as exc:
            text = str(exc) if isinstance(exc, GatewayError) else f"Missing argument: {exc}"
            result = {"content": [{"type": "text", "text": text}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            reply = handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
