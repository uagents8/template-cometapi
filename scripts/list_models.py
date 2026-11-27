#!/usr/bin/env python3
"""Print CometAPI's current text-model catalog, so MODEL_NAME is never a guess.

Calls the public, unauthenticated catalog endpoint (GET https://api.cometapi.com/api/models -
not under /v1, and distinct from the OpenAI-compatible /v1/chat/completions used by main.py).

Usage: python scripts/list_models.py [provider-substring]
  python scripts/list_models.py            # every text model
  python scripts/list_models.py anthropic  # only models whose provider contains "anthropic"
"""
import json
import sys
import urllib.request

CATALOG_URL = "https://api.cometapi.com/api/models"


def main() -> int:
    needle = sys.argv[1].lower() if len(sys.argv) > 1 else None
    with urllib.request.urlopen(CATALOG_URL, timeout=30) as resp:
        payload = json.loads(resp.read())

    models = [m for m in payload.get("data", []) if m.get("model_type") == "text"]
    if needle:
        models = [m for m in models if needle in str(m.get("provider", "")).lower()]

    for model in sorted(models, key=lambda m: (m.get("provider", ""), m.get("id", ""))):
        print(f"{model.get('provider', '?'):12} {model.get('id')}")
    print(f"\n{len(models)} text model(s) shown, of {payload.get('total', '?')} total in the catalog.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
