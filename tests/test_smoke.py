"""Smoke test: the agent answers GET /, and POST /chat works with no key, no provider
choice, and no network - and the "no key" answer doesn't just read [stub: ...] silently."""

import os

from fastapi.testclient import TestClient

from main import NO_KEY_MESSAGE, app

client = TestClient(app)


def test_root_answers_200():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_arithmetic_is_handled_offline_with_no_model():
    body = client.post("/chat", json={"message": "what is 2+3*4?"}).json()
    assert body["reply"] == "2+3*4 = 14"
    assert body["mode"] == "tool"


def test_anything_else_gets_the_no_key_message_by_default():
    body = client.post("/chat", json={"message": "hello"}).json()
    assert body["mode"] == "stub"
    assert body["reply"] == NO_KEY_MESSAGE


def test_a_bad_expression_is_answered_not_crashed():
    for message in ("1/0", "(2+", "2**9999999", "1" + "0" * 400 + "/3"):
        response = client.post("/chat", json={"message": message})
        assert response.status_code == 200, message


def test_rejects_an_empty_or_oversized_message():
    assert client.post("/chat", json={"message": ""}).status_code == 422
    assert client.post("/chat", json={"message": "x" * 501}).status_code == 422


def test_works_without_any_api_key():
    assert "COMETAPI_KEY" not in os.environ
