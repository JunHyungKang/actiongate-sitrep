import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

import app as app_module
import sitrep_agent.sdk as sdk


client = TestClient(app_module.app)


def test_health_endpoint():
    assert client.get("/health").json() == {"ok": True}


def test_run_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(app_module, "verify_signature", lambda *_args: False)

    response = client.post("/run", json={"task": {"title": "Test"}})

    assert response.status_code == 401
    assert response.json() == {"error": "bad signature"}


def test_run_accepts_fresh_hmac_signature(monkeypatch):
    secret = "test-signing-secret"
    timestamp = str(int(time.time()))
    body = json.dumps(
        {"task": {"title": "Test"}, "summary": "", "attendees": [], "agent": {}},
        separators=(",", ":"),
    ).encode()
    signature = "sha256=" + hmac.new(
        secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()

    async def fake_handler(_input, ctx):
        ctx.log("signed request accepted")
        return {"artifacts": []}

    monkeypatch.setattr(sdk, "SITREP_AGENT_SECRET", secret)
    monkeypatch.setattr(app_module, "handler", fake_handler)
    response = client.post(
        "/run",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-SitRep-Timestamp": timestamp,
            "X-SitRep-Signature": signature,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"artifacts": [], "logs": ["signed request accepted"]}


def test_test_endpoint_preserves_artifact_contract(monkeypatch):
    monkeypatch.setattr(app_module, "verify_signature", lambda *_args: True)

    async def fake_handler(_input, ctx):
        ctx.log("complete")
        return {"artifacts": [{"type": "markdown", "title": "Packet", "content": "Ready"}]}

    monkeypatch.setattr(app_module, "handler", fake_handler)
    response = client.post(
        "/test",
        json={"task": {"title": "Test"}, "summary": "", "attendees": [], "agent": {}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "artifacts": [{"type": "markdown", "title": "Packet", "content": "Ready"}],
        "logs": ["complete"],
    }


def test_run_rejects_malformed_json(monkeypatch):
    monkeypatch.setattr(app_module, "verify_signature", lambda *_args: True)

    response = client.post("/run", content=b"{not-json", headers={"Content-Type": "application/json"})

    assert response.status_code == 400
    assert response.json() == {"error": "invalid JSON body"}


def test_run_rejects_non_object_payload(monkeypatch):
    monkeypatch.setattr(app_module, "verify_signature", lambda *_args: True)

    response = client.post("/run", json=[])

    assert response.status_code == 400
    assert response.json() == {"error": "JSON body must be an object"}
