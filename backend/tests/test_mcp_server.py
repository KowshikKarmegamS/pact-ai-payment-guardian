"""The MCP server speaks JSON-RPC, exposes no payment tool, and forwards calls to the Agent Gateway."""

import importlib.util
import json
from pathlib import Path

import pytest

SERVER_PATH = Path(__file__).resolve().parents[2] / "integrations" / "mcp" / "pact_mcp_server.py"


@pytest.fixture
def mcp(client, monkeypatch):
    spec = importlib.util.spec_from_file_location("pact_mcp_server", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    key = {}

    def via_testclient(method, path, body=None, query=None):
        res = client.request(method, f"/api/agent/v1{path}", json=body, params=query,
                             headers={"Authorization": f"Bearer {key['k']}"})
        if res.status_code >= 400:
            raise mod.GatewayError(f"PACT refused ({res.status_code}): {res.json()['detail']['message']}")
        return res.json()

    monkeypatch.setattr(mod, "_gateway", via_testclient)
    mod.set_key = lambda k: key.__setitem__("k", k)
    return mod


def _call(mod, name, args):
    return mod.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": name, "arguments": args}})


def test_handshake_and_tool_list_have_no_payment_tool(mcp):
    init = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
    assert init["result"]["protocolVersion"] == "2025-06-18"
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    names = {t["name"] for t in mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]}
    assert names == {"check_spending_authority", "search_catalog", "evaluate_purchase", "request_purchase",
                     "get_purchase_status"}
    assert not any(w in n for n in names for w in ("approve", "capture", "pay"))
    assert mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "capture_payment"})["error"]["code"] == -32601


def test_tools_reach_the_gateway(mcp, client, sample_mandate, sample_product):
    agent = client.post("/api/agents", json={"name": "Claude (MCP)", "mandate_ids": [sample_mandate.id]}).json()
    mcp.set_key(agent["api_key"])
    who = _call(mcp, "check_spending_authority", {})["result"]
    assert who["isError"] is False and who["structuredContent"]["agent_name"] == "Claude (MCP)"
    req = _call(mcp, "request_purchase", {"mandate_id": sample_mandate.id, "product_id": sample_product.id,
                                          "reason": "User asked for a hub"})["result"]
    assert req["structuredContent"]["decision"] == "PENDING_HUMAN"
    status = _call(mcp, "get_purchase_status", {"purchase_id": req["structuredContent"]["purchase_id"]})["result"]
    assert status["structuredContent"]["status"] == "AWAITING_HUMAN_APPROVAL"
    json.dumps(status)  # serializable over stdio


def test_refusals_come_back_as_tool_errors(mcp, client, sample_mandate, sample_product):
    agent = client.post("/api/agents", json={"name": "Agent A", "mandate_ids": [sample_mandate.id]}).json()
    mcp.set_key(agent["api_key"])
    out = _call(mcp, "request_purchase", {"mandate_id": "not-mine", "product_id": sample_product.id, "reason": "x y z"})
    assert out["result"]["isError"] is True and "403" in out["result"]["content"][0]["text"]
