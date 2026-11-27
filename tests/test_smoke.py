"""Smoke test: the agent answers GET /, and POST /chat works with no key, no provider
choice, and no network - and the "no key" answer doesn't just read [stub: ...] silently.

The model-override and /switch-model-demo tests monkeypatch main.AsyncOpenAI with a fake
client, so they too run with no real CometAPI key and no network."""

import os

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError

import main
from main import NO_KEY_MESSAGE, app

client = TestClient(app)


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [type("Choice", (), {"message": _FakeMessage(content)})()]


class _FakeCompletions:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error

    async def create(self, *, model: str, messages: list) -> _FakeCompletion:
        if self._error is not None:
            raise self._error
        return _FakeCompletion(f"echo({model}): {messages[0]['content']}")


class _FakeAsyncOpenAI:
    def __init__(self, *, error: Exception | None = None, **_kwargs) -> None:
        self.chat = type("Chat", (), {"completions": _FakeCompletions(error=error)})()


@pytest.fixture
def fake_key(monkeypatch):
    monkeypatch.setenv("COMETAPI_KEY", "sk-test-fake-key")


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


def test_chat_model_override_changes_only_the_model_string(fake_key, monkeypatch):
    monkeypatch.setattr(main, "AsyncOpenAI", _FakeAsyncOpenAI)
    body = client.post("/chat", json={"message": "hi", "model": "claude-haiku-5-5"}).json()
    assert body["model"] == "claude-haiku-5-5"
    assert body["reply"] == "echo(claude-haiku-5-5): hi"
    assert body["mode"] == "model"


def test_chat_falls_back_to_model_name_env_var(fake_key, monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "deepseek-chat")
    monkeypatch.setattr(main, "AsyncOpenAI", _FakeAsyncOpenAI)
    body = client.post("/chat", json={"message": "hi"}).json()
    assert body["model"] == "deepseek-chat"


def test_chat_answers_not_crashes_on_an_upstream_error(fake_key, monkeypatch):
    request = httpx.Request("POST", "https://api.cometapi.com/v1/chat/completions")
    monkeypatch.setattr(
        main, "AsyncOpenAI", lambda **kw: _FakeAsyncOpenAI(error=APIConnectionError(request=request), **kw)
    )
    response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 200
    assert response.json()["mode"] == "error"


def test_switch_model_demo_runs_every_model_on_the_same_message(fake_key, monkeypatch):
    monkeypatch.setattr(main, "AsyncOpenAI", _FakeAsyncOpenAI)
    response = client.post(
        "/switch-model-demo",
        json={"message": "2+2?", "models": ["gpt-5-mini", "claude-haiku-5-5", "deepseek-chat"]},
    )
    assert response.status_code == 200
    results = response.json()
    assert [r["model"] for r in results] == ["gpt-5-mini", "claude-haiku-5-5", "deepseek-chat"]
    assert all(r["reply"] == f"echo({r['model']}): 2+2?" for r in results)


def test_switch_model_demo_without_a_key_still_answers_every_model():
    response = client.post("/switch-model-demo", json={"message": "hi", "models": ["gpt-5-mini", "deepseek-chat"]})
    assert response.status_code == 200
    assert all(r["mode"] == "stub" for r in response.json())


def test_rejects_too_many_models():
    response = client.post("/switch-model-demo", json={"message": "hi", "models": ["a", "b", "c", "d", "e", "f"]})
    assert response.status_code == 422
