"""AG Studio dashboard data and the Studio Agent Framework proxy (Gemini replaced by a mock transport)."""

import json

import httpx
import pytest

from app.config import get_settings
from app.services import studio_llm


def test_dataset_reflects_real_proposals(client, sample_mandate, sample_product, sample_out_of_stock_product):
    assert client.get("/api/analytics/dataset").json() == {"purchases": []}
    ok = client.post("/api/proposals/propose", json={"mandate_id": sample_mandate.id, "product_id": sample_product.id}).json()
    blocked = client.post("/api/proposals/propose", json={"mandate_id": sample_mandate.id,
                                                          "product_id": sample_out_of_stock_product.id}).json()
    client.post(f"/api/proposals/{ok['proposal']['id']}/reject")
    rows = {r["purchase_id"]: r for r in client.get("/api/analytics/dataset").json()["purchases"]}
    assert len(rows) == 2
    r_ok, r_bad = rows[ok["proposal"]["id"]], rows[blocked["proposal"]["id"]]
    assert (r_ok["outcome"], r_ok["requested_amount"], r_ok["paid_amount"], r_ok["blocked_amount"]) == \
        ("Rejected by owner", 34.99, 0.0, 0.0)
    assert (r_bad["outcome"], r_bad["decided_by_policy"], r_bad["blocked_amount"]) == ("Blocked by policy", "Blocked", 79.99)
    assert r_ok["agent"] == "PACT reference agent" and r_ok["mandate"] == sample_mandate.name
    assert r_ok["source"] == "PACT catalog" and len(r_ok["day"]) == 10


def test_paid_amount_only_counts_verified_captures(client, sample_mandate, sample_product, fake_paypal):
    p = client.post("/api/proposals/generate", json={"prompt": "USB-C hub adapter from TechHub",
                                                     "mandate_id": sample_mandate.id}).json()["proposal"]
    client.post(f"/api/proposals/{p['id']}/approve", json={"expected_fingerprint": p["proposal_fingerprint"]})
    order = client.post(f"/api/payments/{p['id']}/create-order").json()
    row = client.get("/api/analytics/dataset").json()["purchases"][0]
    assert row["paid_amount"] == 0.0 and row["outcome"] == "Approved, in checkout"
    fake_paypal.buyer_approves(order["order_id"])
    assert client.post(f"/api/payments/{p['id']}/capture").status_code == 200
    row = client.get("/api/analytics/dataset").json()["purchases"][0]
    assert row["paid_amount"] == 34.99 and row["outcome"] == "Paid"


STUDIO_REQUEST = {
    "instructions": "You are the data agent.",
    "input": [
        {"id": "u1", "kind": "input", "type": "message", "role": "user", "status": "completed",
         "content": [{"type": "text", "text": "Total paid by merchant?"}]},
        {"id": "fc1", "kind": "output", "type": "function_call", "callId": "call_A", "name": "execute_query",
         "arguments": json.dumps({"fields": ["purchases.merchant"]})},
        {"type": "function_call_output", "callId": "call_A", "output": "[{\"merchant\":\"bestbuy.com\"}]",
         "status": "completed"},
    ],
    "tools": [{"name": "execute_query", "description": "Run a query", "kind": "client",
               "parameters": {"type": "object", "properties": {"fields": {"type": "array"}}}},
              {"name": "web_search", "kind": "provided", "provider": {"type": "web_search"}}],
    "toolChoice": "auto",
    "responseFormat": {"type": "text"},
}


def test_studio_request_translates_to_gemini_function_calling():
    body, names = studio_llm.to_gemini(STUDIO_REQUEST)
    assert names == {"call_A": "execute_query"}
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    assert body["contents"][1]["parts"][0]["functionCall"] == {"name": "execute_query", "args": {"fields": ["purchases.merchant"]}}
    assert body["contents"][2]["parts"][0]["functionResponse"]["name"] == "execute_query"
    decls = body["tools"][0]["functionDeclarations"]
    assert [d["name"] for d in decls] == ["execute_query"]  # provider-hosted tools are not forwarded
    assert body["toolConfig"]["functionCallingConfig"]["mode"] == "AUTO"
    system = body["systemInstruction"]["parts"][0]["text"]
    assert "cannot create, approve, pay" in system and "You are the data agent." in system


def test_gemini_answer_maps_back_and_key_stays_server_side(client, monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"modelVersion": "gemini-test", "candidates": [{"finishReason": "STOP", "content": {
            "role": "model", "parts": [{"text": "Querying."},
                                       {"functionCall": {"name": "execute_query", "args": {"fields": ["x"]}},
                                        "thoughtSignature": "sig-1"}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15}})

    monkeypatch.setattr(get_settings(), "GEMINI_API_KEY", "gem-test-key")
    real = httpx.AsyncClient

    class Patched(real):
        def __init__(self, *a, **k):
            k["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **k)

    monkeypatch.setattr(studio_llm.httpx, "AsyncClient", Patched)
    res = client.post("/api/analytics/agent-turn", json=STUDIO_REQUEST)
    assert res.status_code == 200
    out = res.json()
    assert out["status"] == "completed" and out["model"] == "gemini-test"
    msg, call = out["output"]
    assert msg["type"] == "message" and msg["content"][0]["text"] == "Querying."
    assert call["type"] == "function_call" and call["name"] == "execute_query" and json.loads(call["arguments"]) == {"fields": ["x"]}
    assert seen[0].headers["x-goog-api-key"] == "gem-test-key" and "gem-test-key" not in str(seen[0].url)
    assert "gem-test-key" not in res.text

    # The thought signature is replayed on the next turn for that call.
    nxt = dict(STUDIO_REQUEST, input=STUDIO_REQUEST["input"][:1] + [
        {"id": "fc2", "kind": "output", "type": "function_call", "callId": call["callId"], "name": "execute_query",
         "arguments": call["arguments"]}])
    body, _ = studio_llm.to_gemini(nxt)
    assert body["contents"][1]["parts"][0]["thoughtSignature"] == "sig-1"


def test_agent_turn_reports_failures_without_raising(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "GEMINI_API_KEY", "")
    out = client.post("/api/analytics/agent-turn", json=STUDIO_REQUEST).json()
    assert out["status"] == "failed" and out["error"]["code"] == "NOT_CONFIGURED"
