from fastapi.testclient import TestClient

import app as app_module


client = TestClient(app_module.app)


def test_health_endpoint():
    assert client.get("/health").json() == {"ok": True}


def test_run_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(app_module, "verify_signature", lambda *_args: False)

    response = client.post("/run", json={"task": {"title": "Test"}})

    assert response.status_code == 401
    assert response.json() == {"error": "bad signature"}


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
