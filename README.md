# template-cometapi

[![Deploy to uagents8](https://img.shields.io/badge/Deploy%20to-uagents8-6366f1?style=for-the-badge)](https://app.uagents8.com)

A small CometAPI agent behind FastAPI, ready to deploy on uAgents8 and to point at your own models. CometAPI is an OpenAI-compatible gateway to 500+ models (OpenAI, Anthropic, Google, DeepSeek and more) behind one key and one base URL. One of several one-click framework and provider templates for uAgents8.

> **Use it one click**: the deploy wizard's **Source** step has a **Templates** card next to
> GitHub/GitLab/Bitbucket - pick **CometAPI starter** there and the wizard handles everything
> below for you. The badge above also just opens the dashboard - from there, the same
> Templates card is the fastest path.

Use this as a GitHub template. Click **Use this template** above to create your own copy in your GitHub account - it never writes back to this repository. Or download the code and redeploy through Code Archive.

## What this is

A plain FastAPI service with one offline tool and one model call:

| Route | What it does |
| --- | --- |
| `GET /` | A friendly status answer: `{"status": "ok", "agent": "template-cometapi"}`. |
| `POST /chat` | Body `{"message": "what is 2+3*4?"}`. Answers `{"message", "reply", "mode"}`: arithmetic runs plain Python (`mode: "tool"`), everything else goes to CometAPI (`mode: "model"` once a key is set, `mode: "stub"` otherwise). |

```
curl -X POST https://<your-agent>.uagents8.app/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "what is 2+3*4?"}'
```

## Add your CometAPI key - or don't

It needs no API key and no network to start. Set `COMETAPI_KEY` under **Environment Variables** (Sensitive on) to call CometAPI, and optionally `MODEL_NAME` to choose any of its 500+ models (default `gpt-4o-mini`). With no key set, `POST /chat` still answers - with a message that says exactly what to add - instead of refusing to start (see `uagents8.json`'s `env_vars`).

Get a free CometAPI key at [cometapi.com](https://cometapi.com) (Partner promo / referral link: [COMETAPI_PROMO_LINK]).

The place you change to make it your own is `respond()` in `main.py`.

## Run it on your machine

```
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PORT=8000 python main.py
```

In a second terminal:

```
curl http://localhost:8000/
curl -X POST http://localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"message": "what is 2+3*4?"}'
```

Checks: `pip install -r requirements-dev.txt && ruff check . && pytest`.

## What the platform needs, and where this template does it

- Listen on the `PORT` environment variable, on `0.0.0.0`. The last lines of `main.py`.
- A `main.py` at the top level that starts the server itself. The platform runs `python main.py`.
- A `requirements.txt` at the top level with every package pinned (`==`). The build uses Python 3.12 and has no compiler, so every pin needs a ready-made wheel.
- No Dockerfile needed. The platform writes one from your code.
- Open the port quickly - within about 150 seconds of the container starting.

## Deploy it from uAgents8

1. Press **+ Deploy Agent**.
2. **Details**: give it a name.
3. **Source**: pick **Templates**, then the CometAPI starter - or, by hand, either **GitHub** (this repository, branch `main`) or **Code Archive**: from this folder run `zip template-cometapi.zip main.py requirements.txt` and upload the file.
4. **Configure**: paste your `COMETAPI_KEY` if you have one (Sensitive on); resource size **T** (256 MB) is plenty.
5. **Confirm**, then **Deploy agent**.

When the status screen says **Running**, open the agent's URL and call it the same way as on your machine.

## Use a real model

CometAPI is a drop-in for the OpenAI SDK: `respond()` in `main.py` creates an `OpenAI` client with `base_url=https://api.cometapi.com/v1` and your `COMETAPI_KEY`, then calls `chat.completions.create`. Set `MODEL_NAME` to any CometAPI model ID (for example `gpt-4o-mini`, `gpt-5-mini`, `claude-3-5-haiku-latest` or `deepseek-chat`), set the key under **Environment Variables** with Sensitive on, and redeploy. A changed variable is only picked up on the next deploy.

## About this repository

Maintained by the uAgents8 team. CI lints, runs the smoke tests and calls the running server on every push and once a week (`.github/workflows/ci.yml`); a separate weekly job (`.github/workflows/deploy-check.yml`) deploys this exact template to the platform's own e2e sandbox, calls `POST /chat`, and deletes it.
