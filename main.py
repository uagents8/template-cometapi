"""A CometAPI agent behind FastAPI - the uAgents8 "CometAPI" template.

CometAPI is an OpenAI-compatible gateway to 500+ models (OpenAI, Anthropic, Google,
DeepSeek and more) behind one key and one base URL. This template keeps a small, proven
shape - one offline tool, one model call, pinned dependencies - so the footprint stays
small, and it answers even before you add a key.

GET  /                      health - the platform only checks that the port accepts connections
POST /chat                  {"message": "...", "model": optional} -> {"message", "reply", "mode", "model"?}
POST /switch-model-demo     {"message": "...", "models": [...]} -> one result per model, same
                             prompt, run concurrently - proof that switching CometAPI models is
                             a one-line change (just the `model` string), not a rewrite.

Provider: set COMETAPI_KEY (Sensitive on) to call CometAPI; MODEL_NAME picks the default model
(default gpt-4o-mini), overridable per-request via /chat's "model" field. With no key the
template still starts and answers - see NO_KEY_MESSAGE below, a deliberately better first
impression than refusing to boot.

Make it yours: replace the body of respond().
"""

import ast
import asyncio
import operator
import os

import uvicorn
from fastapi import FastAPI
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from pydantic import BaseModel, Field

AGENT_NAME = "template-cometapi"
COMETAPI_BASE_URL = "https://api.cometapi.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
MAX_COMPARE_MODELS = 5

NO_KEY_MESSAGE = (
    "I can do simple arithmetic without a key. For anything else, add your CometAPI key: "
    "set COMETAPI_KEY under Environment Variables (Sensitive on) - and optionally MODEL_NAME "
    "to pick one of CometAPI's 500+ models - then redeploy."
)

# --- calculate: a tool, no model involved ------------------------------------

_OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _evaluate(node: ast.AST) -> float:
    """Evaluate + - * / and parentheses on numbers; anything else raises ValueError."""
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_evaluate(node.operand)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_evaluate(node.left), _evaluate(node.right))
    raise ValueError("unsupported expression")


def _arithmetic(message: str) -> str | None:
    """The expression inside `message`, if the whole message is just arithmetic."""
    expression = message.strip().lower().removeprefix("what is").strip().rstrip("?= ")
    if not expression or not any(ch.isdigit() for ch in expression):
        return None
    if any(ch not in "0123456789+-*/(). " for ch in expression):
        return None
    return expression


def calculate(message: str) -> dict:
    expression = _arithmetic(message) or ""
    try:
        result = _evaluate(ast.parse(expression, mode="eval"))
    except (SyntaxError, ValueError, ArithmeticError):
        return {"reply": f"I could not calculate {expression!r}.", "mode": "tool"}
    return {"reply": f"{expression} = {result:g}", "mode": "tool"}


# --- respond: where the CometAPI model goes ----------------------------------


async def respond(message: str, *, model: str | None = None) -> dict:
    """Answer a message with a CometAPI model - the one call site every route in this file
    that talks to CometAPI goes through.

    Reads COMETAPI_KEY from the environment; the model is `model` if given, else MODEL_NAME,
    else DEFAULT_MODEL. With no key set this returns NO_KEY_MESSAGE (offline, deterministic)
    instead of refusing to answer - the key is read from the environment, never from this file.
    A CometAPI failure (timeout, bad model, rate limit, ...) is answered, not crashed: it comes
    back as `mode: "error"`, same as a bad arithmetic expression already does for `calculate()`.
    """
    key = os.environ.get("COMETAPI_KEY")
    if not key:
        return {"reply": NO_KEY_MESSAGE, "mode": "stub"}

    chosen_model = model or os.environ.get("MODEL_NAME", DEFAULT_MODEL)
    client = AsyncOpenAI(api_key=key, base_url=os.environ.get("COMETAPI_BASE_URL", COMETAPI_BASE_URL))
    try:
        completion = await client.chat.completions.create(
            model=chosen_model,
            messages=[{"role": "user", "content": message}],
        )
    except APITimeoutError:
        reply = f"CometAPI timed out calling model {chosen_model!r}. Try again."
        return {"reply": reply, "mode": "error", "model": chosen_model}
    except APIConnectionError:
        reply = "Could not reach CometAPI. Check COMETAPI_BASE_URL and network access."
        return {"reply": reply, "mode": "error", "model": chosen_model}
    except APIStatusError as exc:
        reply = f"CometAPI rejected model {chosen_model!r}: {exc.message}"
        return {"reply": reply, "mode": "error", "model": chosen_model}
    return {"reply": completion.choices[0].message.content or "", "mode": "model", "model": chosen_model}


async def answer(message: str, *, model: str | None = None) -> dict:
    """Route pure arithmetic to the offline calculator, everything else to the model."""
    if _arithmetic(message):
        return calculate(message)
    return await respond(message, model=model)


app = FastAPI(title=AGENT_NAME)


class Chat(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    model: str | None = Field(default=None, description="Override MODEL_NAME for this one request.")


class ModelCompareRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    models: list[str] = Field(min_length=1, max_length=MAX_COMPARE_MODELS)


class ModelResult(BaseModel):
    model: str
    reply: str
    mode: str


@app.get("/")
def index() -> dict[str, str]:
    """A friendly status route. The platform does not call it: its check is that the port accepts connections."""
    return {"status": "ok", "agent": AGENT_NAME}


@app.post("/chat")
async def chat(body: Chat) -> dict[str, str]:
    result = await answer(body.message, model=body.model)
    response = {"message": body.message, "reply": result["reply"], "mode": result["mode"]}
    if "model" in result:
        response["model"] = result["model"]
    return response


@app.post("/switch-model-demo", response_model=list[ModelResult])
async def switch_model_demo(body: ModelCompareRequest) -> list[ModelResult]:
    """The same message, sent to every model in `models`, concurrently - one call to `respond()`
    each, differing only in the `model` string. There is no per-provider branch anywhere in
    this file: CometAPI's one OpenAI-compatible endpoint is what makes that possible."""

    async def run_one(model: str) -> ModelResult:
        result = await respond(body.message, model=model)
        return ModelResult(model=model, reply=result["reply"], mode=result["mode"])

    return list(await asyncio.gather(*(run_one(model) for model in body.models)))


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv()  # load a local .env for `python main.py`; the platform sets real env vars
    except ImportError:
        pass
    # The platform sets PORT; listen on all interfaces, not just localhost.
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
