#!/usr/bin/env python3
"""Analyze images using a vision model via its OpenAI-compatible Chat Completions API.

API configuration comes from environment variables (IMAGE_VISION_API_URL /
IMAGE_VISION_API_KEY / IMAGE_VISION_MODEL) or config files: first
~/.claude/image-vision.json, then config.json next to the skill. Run
scripts/setup.py once to configure interactively.

Usage:
  python analyze_image.py --image <path-or-url> [--image <path2> ...] [--prompt "text"]
      [--format text|json] [--prev "text"] [--max-size 2048] [--verbose]

- Local images are base64-encoded into data URLs; URLs pass through.
- Oversized local images are downscaled with Pillow (if available).
- --format json asks the model for structured output (summary + elements with
  normalized bounding boxes) and validates the JSON before printing.
- --prev passes the previous analysis for follow-up questions (multi-turn).
- Network/API 5xx errors are retried once.

Exit code 0 on success, 1 on error (message printed to stderr).
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request

try:
    from PIL import Image, ImageOps
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False


def _force_utf8_stdio():
    """Windows default stdio is the console codepage (GBK); use UTF-8 for paths/messages."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError, ValueError):
            pass


_force_utf8_stdio()

API_URL_ENV = "IMAGE_VISION_API_URL"
API_KEY_ENV = "IMAGE_VISION_API_KEY"
MODEL_ENV = "IMAGE_VISION_MODEL"
# Config lookup order: environment > global user config > skill-dir config.
# The global path (~/.claude/image-vision.json) survives plugin cache updates.
GLOBAL_CONFIG = os.path.join(os.path.expanduser("~"), ".claude", "image-vision.json")
LOCAL_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"
)
CONFIG_FILES = [GLOBAL_CONFIG, LOCAL_CONFIG]
DEFAULT_PROMPT = (
    "Describe this image concisely. Include all visible text, UI elements, "
    "colors, layout, and any notable details. Only report what is asked."
)
JSON_INSTRUCTION = (
    "\n\nReturn your analysis as JSON only (no markdown, no code fences, no "
    "extra text) with this exact schema:\n"
    '{"summary": "2-3 sentence overview", "elements": [{"image": <1-based '
    "index of the image this element belongs to; omit entirely for "
    'single-image requests>, "type": "text|button|icon|image|input|link|'
    '"table|chart|other", "content": "element content or description", '
    '"bbox": [x1, y1, x2, y2], "conf": 0.0-1.0}]}\n'
    "bbox coordinates are normalized to 0-1000 relative to image dimensions."
)


def downscale(path, max_side=2048):
    """Return a downscaled copy if the image exceeds max_side; else the original path.

    Animated GIFs are never downscaled (multi-frame save would corrupt sizes).
    EXIF orientation is applied before scaling so rotated photos stay upright.
    """
    if not HAVE_PIL:
        return path
    try:
        with Image.open(path) as img:
            if img.is_animated:
                return path
            w, h = img.size
            if max(w, h) <= max_side:
                return path
            img = ImageOps.exif_transpose(img)
            img.thumbnail((max_side, max_side))
            fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(path)[1] or ".png")
            os.close(fd)
            img.save(tmp)
            return tmp
    except Exception:
        return path  # non-image or unreadable: send as-is


def load_config():
    """Resolve API config: environment variables > global config > skill-dir config."""
    cfg = {"api_url": os.environ.get(API_URL_ENV),
           "api_key": os.environ.get(API_KEY_ENV),
           "model": os.environ.get(MODEL_ENV)}
    if all(cfg.values()):
        return cfg
    for path in CONFIG_FILES:
        try:
            with open(path, encoding="utf-8") as f:
                file_cfg = json.load(f)
            for key in cfg:
                if not cfg[key]:
                    cfg[key] = file_cfg.get(key)
            if all(cfg.values()):
                break
        except OSError:
            continue  # file absent; try next candidate
        except json.JSONDecodeError as e:
            sys.exit(f"Error: config file {path} is invalid JSON: {e}")
    for key, hint in (("api_url", "run scripts/setup.py or set IMAGE_VISION_API_URL"),
                      ("api_key", "run scripts/setup.py or set IMAGE_VISION_API_KEY"),
                      ("model", "run scripts/setup.py or set IMAGE_VISION_MODEL")):
        if not cfg[key]:
            sys.exit(f"Error: {key} is not configured; {hint}.")
    # Accept a base URL; append the OpenAI-compatible endpoint if missing.
    if not cfg["api_url"].rstrip("/").endswith("/chat/completions"):
        cfg["api_url"] = cfg["api_url"].rstrip("/") + "/chat/completions"
    return cfg


def to_data_url(path, max_side):
    if not os.path.isfile(path):
        sys.exit(f"Error: file not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext == ".heic":
        sys.exit("Error: HEIC images are not supported. Convert to PNG/JPEG "
                 "first (e.g. via Preview/Photos), or install pillow-heif.")
    if ext == ".svg":
        sys.exit("Error: SVG images are not supported by most vision APIs. "
                 "Convert to PNG first.")
    mime, _ = mimetypes.guess_type(path)
    if not mime or not mime.startswith("image/"):
        mime = "image/png"  # fallback for unknown extensions
    tmp = None
    if max_side:
        tmp = downscale(path, max_side)
        if tmp != path and HAVE_PIL:
            mime, _ = mimetypes.guess_type(tmp)
    try:
        with open(tmp or path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    finally:
        if tmp and tmp != path:
            os.unlink(tmp)
    return f"data:{mime};base64,{b64}"


def call_api(payload, api_url, api_key, retries=1):
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
            # retry transient failures: server errors and rate limiting
            if (e.code >= 500 or e.code == 429) and attempt < retries:
                time.sleep(1)
                continue
            sys.exit(f"API error {e.code}: {body}")
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(1)
                continue
            sys.exit(f"Network error: {e.reason}")


def extract_json(text):
    """Extract and validate JSON from the model response (handles code fences)."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        t = t[start:end + 1]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Analyze images with a vision model (OpenAI-compatible API)"
    )
    parser.add_argument("--image", action="append", required=True,
                        help="Image path or URL (repeatable for multiple images)")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT,
                        help="Question or instruction about the image(s)")
    parser.add_argument("--format", dest="fmt", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--prev", default=None,
                        help="Previous analysis text, for follow-up questions")
    parser.add_argument("--max-size", type=int, default=2048,
                        help="Downscale images with a longer side above this (px); 0 disables")
    parser.add_argument("--max-tokens", type=int, default=None,
                        help="Override output token budget (default: 4096 text, 8192 json)")
    parser.add_argument("--verbose", action="store_true",
                        help="Also print the model's reasoning")
    args = parser.parse_args()

    max_tokens = args.max_tokens or (8192 if args.fmt == "json" else 4096)

    prompt = args.prompt + (JSON_INSTRUCTION if args.fmt == "json" else "")
    cfg = load_config()

    content = [{"type": "text", "text": prompt}]
    for img in args.image:
        if img.startswith(("http://", "https://")):
            url = img
        else:
            url = to_data_url(img, args.max_size)
        content.append({"type": "image_url", "image_url": {"url": url}})

    messages = [{"role": "user", "content": content}]
    if args.prev:
        messages.append({"role": "assistant", "content": args.prev})
        # Follow-up round repeats the images so the model can see them even if
        # the API does not retain image context from earlier turns.
        messages.append({"role": "user", "content": list(content)})

    payload = {
        "model": cfg["model"],
        "messages": messages,
        # Reasoning model: budget must cover reasoning + answer
        "max_tokens": max_tokens,
    }

    data = call_api(payload, cfg["api_url"], cfg["api_key"])

    choice = data["choices"][0]
    if choice.get("finish_reason") == "length":
        print(f"(response truncated at {max_tokens} max_tokens; raise "
              "--max-tokens or shorten the prompt)", file=sys.stderr)
    msg = choice["message"]
    text = msg.get("content") or ""
    if args.verbose and msg.get("reasoning_content"):
        print("=== Reasoning ===")
        print(msg["reasoning_content"])
        print("=== Answer ===")
    if args.fmt == "json":
        parsed = extract_json(text)
        if parsed is not None:
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
        else:
            print("(model did not return valid JSON; raw response follows)", file=sys.stderr)
            print(text)
    else:
        print(text or "(empty response)")


if __name__ == "__main__":
    main()
