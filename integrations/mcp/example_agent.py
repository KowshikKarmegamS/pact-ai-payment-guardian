#!/usr/bin/env python3
"""A third-party AI agent that knows PACT only through MCP.

It starts pact_mcp_server.py as a normal MCP stdio server, gives the server's tools to a Gemini model
with function calling, and lets the model shop. Nothing is scripted: the model decides which tools
to call, and PACT decides what it is allowed to do.

  PACT_URL=http://localhost:8001 PACT_AGENT_KEY=pact_agent_... GEMINI_API_KEY=... \
      python example_agent.py "Buy me noise-cancelling headphones"

Standard library only. The Gemini key is sent in a header and never printed.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
SERVER = Path(__file__).with_name("pact_mcp_server.py")


class MCPClient:
    def __init__(self):
        self.proc = subprocess.Popen([sys.executable, str(SERVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     text=True, env=os.environ.copy())
        self.next_id = 0

    def request(self, method, params=None):
        self.next_id += 1
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.next_id, "method": method,
                                          "params": params or {}}) + "\n")
        self.proc.stdin.flush()
        reply = json.loads(self.proc.stdout.readline())
        if "error" in reply:
            raise RuntimeError(reply["error"]["message"])
        return reply["result"]

    def notify(self, method):
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


def gemini(contents, tools, system):
    """One model turn. On a rate limit or overload, waits and falls back to the lite model."""
    body = json.dumps({"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                       "tools": [{"functionDeclarations": tools}]}).encode()
    last = None
    for model in (MODEL, MODEL, FALLBACK_MODEL):
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", data=body, method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                return json.loads(res.read())["candidates"][0]["content"]
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 503):
                raise SystemExit(f"Gemini error {exc.code}: {exc.read().decode()[:300]}")
            last = f"{model}: HTTP {exc.code}"
            time.sleep(6)
    raise SystemExit(f"Gemini is unavailable right now ({last}). Try again in a minute.")


def main():
    task = " ".join(sys.argv[1:]) or "Buy me a pair of noise-cancelling headphones."
    mcp = MCPClient()
    init = mcp.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "example-gemini-agent", "version": "1.0"}})
    mcp.notify("notifications/initialized")
    tools = mcp.request("tools/list")["tools"]
    print(f"Connected to MCP server '{init['serverInfo']['name']}' with tools: {', '.join(t['name'] for t in tools)}\n")
    declarations = [{"name": t["name"], "description": t["description"], "parametersJsonSchema": t["inputSchema"]}
                    for t in tools]
    system = (init.get("instructions", "") + " You are a shopping agent acting for the user. Check authority, "
              "search, then request one purchase. Report the outcome and the approval link in two sentences.")

    contents = [{"role": "user", "parts": [{"text": task}]}]
    print(f"USER: {task}")
    for _ in range(8):
        content = gemini(contents, declarations, system)
        contents.append(content)
        calls = [p["functionCall"] for p in content.get("parts", []) if "functionCall" in p]
        if not calls:
            print("\nAGENT: " + "".join(p.get("text", "") for p in content.get("parts", [])).strip())
            break
        responses = []
        for call in calls:
            args = call.get("args") or {}
            print(f"  -> {call['name']}({json.dumps(args)})")
            result = mcp.request("tools/call", {"name": call["name"], "arguments": args})
            payload = result.get("structuredContent") or {"text": result["content"][0]["text"]}
            if result.get("isError"):
                print(f"     PACT: {result['content'][0]['text']}")
            elif call["name"] in ("request_purchase", "evaluate_purchase"):
                print(f"     PACT: {payload.get('decision') or ('allowed' if payload.get('allowed') else 'not allowed')}"
                      f" | {payload.get('next_step') or payload.get('summary')}")
            responses.append({"functionResponse": {"name": call["name"], "response": payload}})
        contents.append({"role": "user", "parts": responses})
    mcp.close()


if __name__ == "__main__":
    main()
