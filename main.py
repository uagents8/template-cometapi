"""A CometAPI agent behind FastAPI - the uAgents8 "CometAPI" template.

CometAPI is an OpenAI-compatible gateway to 500+ models (OpenAI, Anthropic, Google,
DeepSeek and more) behind one key and one base URL. This template keeps a small, proven
shape - one offline tool, one model call, pinned dependencies - so the footprint stays
small, and it answers even before you add a key.

GET / health - the platform only checks that the port accepts connections
POST /chat {"message": "..."} -> {"message", "reply", "mode"}

Provider: set COMETAPI_KEY (Sensitive on) to call CometAPI; MODEL_NAME picks the model
(default gpt-4o-mini). With no key the template still starts and answers - see
NO_KEY_MESSAGE below, a deliberately better first impression than refusing to boot.

Make it yours: replace the body of respond().
"""

import ast
import operator
import os

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

AGENT_NAME = "template-cometapi"
COMETAPI_BASE_URL = "https://api.cometapi.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"

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


def respond(message: str) -> dict:
    """Answer a non-arithmetic message with a CometAPI model.

    Reads COMETAPI_KEY and MODEL_NAME from the environment. With no key set this returns
    NO_KEY_MESSAGE (offline, deterministic) instead of refusing to answer - the key is read
    from the environment, never from this file.
    """
    key = os.environ.get("COMETAPI_KEY")
    if not key:
        return {"reply": NO_KEY_MESSAGE, "mode": "stub"}
    try:
        from openai import OpenAI  # pinned in requirements.txt
    except ImportError:
        return {"reply": "COMETAPI_KEY is set but the openai package is not in requirements.txt.", "mode": "stub"}
    client = OpenAI(api_key=key, base_url=os.environ.get("COMETAPI_BASE_URL", COMETAPI_BASE_URL))
    completion = client.chat.completions.create(
        model=os.environ.get("MODEL_NAME", DEFAULT_MODEL),
        messages=[{"role": "user", "content": message}],
    )
    return {"reply": completion.choices[0].message.content or "", "mode": "model"}


def answer(message: str) -> dict:
    """Route pure arithmetic to the offline calculator, everything else to the model."""
    if _arithmetic(message):
        return calculate(message)
    return respond(message)


app = FastAPI(title=AGENT_NAME)


class Chat(BaseModel):
    message: str = Field(min_length=1, max_length=500)


@app.get("/")
def index() -> dict[str, str]:
    """A friendly status route. The platform does not call it: its check is that the port accepts connections."""
    return {"status": "ok", "agent": AGENT_NAME}


@app.post("/chat")
def chat(body: Chat) -> dict[str, str]:
    result = answer(body.message)
    return {"message": body.message, "reply": result["reply"], "mode": result["mode"]}


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv()  # load a local .env for `python main.py`; the platform sets real env vars
    except ImportError:
        pass
    # The platform sets PORT; listen on all interfaces, not just localhost.
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
