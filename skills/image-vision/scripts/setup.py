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

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".claude", "image-vision.json")
FIELDS = [("model", "Model ID", True),
          ("api_key", "API Key", False),
          ("api_url", "API URL", True)]


def _force_utf8_stdio():
    """Windows default stdio is the console codepage (GBK); use UTF-8 for prompts."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError, ValueError):
            pass


_force_utf8_stdio()


def ask(label, current, visible):
    if current:
        hint = f" [{current}]" if visible else " [keep current, Enter to keep]"
        prompt = f"{label}{hint}: "
    else:
        prompt = f"{label}: "
    value = input(prompt).strip()
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

    url = values["api_url"].strip()
    if not url.startswith(("http://", "https://")):
        sys.exit("Error: API URL must start with http:// or https://")
    url = url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    values["api_url"] = url

    for key in ("model", "api_key", "api_url"):
        if not values[key]:
            sys.exit(f"Error: {key} is not set. Run setup again and provide it.")

    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(values, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {CONFIG_PATH}")
    print(f"Model: {values['model']}")
    print(f"URL:   {values['api_url']}")


if __name__ == "__main__":
    main()
