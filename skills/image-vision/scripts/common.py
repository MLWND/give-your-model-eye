#!/usr/bin/env python3
"""Shared helpers for the image-vision skill scripts.

Lives in the same directory as the scripts, so every installed copy of the
skill (install.js copies the whole skill directory) can import it.
"""

import os
import sys

API_ENDPOINT = "/chat/completions"

# Written by scripts/setup.py, read by scripts/analyze_image.py. Lives in the
# user home directory so it survives plugin cache updates.
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".claude", "image-vision.json")


def complete_api_url(url):
    """Return the request URL for the OpenAI-compatible Chat Completions API.

    Base URLs (with or without a path prefix, e.g. https://api.example.com/v1)
    get /chat/completions appended. URLs that already carry the endpoint
    (case-insensitive) pass through unchanged, as do URLs with a query string:
    appending a path after a query would corrupt them (e.g. Azure OpenAI's
    .../chat/completions?api-version=... endpoints).
    """
    url = url.strip()
    if "?" in url:
        return url
    url = url.rstrip("/")
    if url.lower().endswith(API_ENDPOINT):
        return url
    return url + API_ENDPOINT


def force_utf8_stdio():
    """Windows default stdio is the console codepage (GBK); use UTF-8 for paths/messages."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError, ValueError):
            pass
