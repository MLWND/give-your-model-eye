#!/usr/bin/env python3
"""One-time API configuration for the image-vision skill.

Run from the skill base directory:
    python scripts/setup.py

Answer the three prompts (model id, api key, url). The values are written to
~/.claude/image-vision.json, which scripts/analyze_image.py reads. No other
configuration is needed.

The url may be a base URL (e.g. https://api.example.com/v1) — "/chat/completions"
is appended automatically — or the full endpoint URL.

Non-interactive use (e.g. CI):
    python scripts/setup.py --url <url> --api-key <key> --model <model>

Re-running keeps existing values as defaults; blank input keeps the current one.
"""

import argparse
import json
import os
import sys
from urllib.parse import urlparse

from common import CONFIG_PATH, complete_api_url, force_utf8_stdio

force_utf8_stdio()

FIELDS = [("model", "Model ID", True),
          ("api_key", "API Key", False),
          ("api_url", "API URL", True)]

# The shipped config template; its values are the placeholders a real config
# must not keep (the single source of truth for both this wizard and install.js).
EXAMPLE_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.example.json"
)


def ask(label, current, visible):
    if current:
        hint = f" [{current}]" if visible else " [keep current, Enter to keep]"
        prompt = f"{label}{hint}: "
    else:
        prompt = f"{label}: "
    try:
        value = input(prompt).strip()
    except EOFError:
        print()
        sys.exit("Error: no input available (stdin closed). Use --url/--api-key/--model "
                 "for non-interactive setup.")
    except KeyboardInterrupt:
        print()
        sys.exit("Setup cancelled.")
    return value or current


def main():
    parser = argparse.ArgumentParser(
        description="Configure the image-vision skill API (model id, api key, url)")
    parser.add_argument("--url", help="API URL (base URL or full /chat/completions endpoint)")
    parser.add_argument("--api-key", help="API key")
    parser.add_argument("--model", help="Model ID")
    args = parser.parse_args()

    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            cfg = {}  # e.g. "null" or an array left over from hand-editing
    except (OSError, json.JSONDecodeError):
        cfg = {}

    values = {"model": args.model, "api_key": args.api_key, "api_url": args.url}

    if not any(values.values()):
        print("image-vision skill setup — existing values are shown as defaults.\n")
        for key, label, visible in FIELDS:
            values[key] = ask(label, cfg.get(key, ""), visible)
    else:
        for key in values:
            if not values[key]:
                values[key] = cfg.get(key, "")

    url = values["api_url"]
    if not isinstance(url, str):
        sys.exit("Error: api_url in the existing config must be a string.")
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        sys.exit("Error: API URL must start with http:// or https://")
    values["api_url"] = complete_api_url(url)

    # Placeholder markers come from the shipped template itself.
    try:
        with open(EXAMPLE_CONFIG, encoding="utf-8") as f:
            example = json.load(f)
        if not isinstance(example, dict):
            example = {}
    except (OSError, json.JSONDecodeError):
        example = {}
    markers = {"model": example.get("model", ""),
               "api_key": example.get("api_key", ""),
               "api_url": urlparse(example.get("api_url", "")).netloc}

    for key in ("model", "api_key", "api_url"):
        if not values[key]:
            sys.exit(f"Error: {key} is not set. Run setup again and provide it.")
        marker = markers[key]
        if marker and marker in values[key]:
            sys.exit(f"Error: {key} still contains the config template placeholder "
                     f"({marker}); provide a real value.")

    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(values, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {CONFIG_PATH}")
    print(f"Model: {values['model']}")
    print(f"URL:   {values['api_url']}")


if __name__ == "__main__":
    main()
