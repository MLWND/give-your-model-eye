#!/usr/bin/env python3
"""Hook for the image-vision skill: remind the model to use the skill when an image is involved.

Reads hook input JSON from stdin and dispatches by hook_event_name:

- PreToolUse (Read): if the file being read is an image, inject a reminder
  to use the image-vision skill when the image content is not visible.
- PreToolUse (Bash): if the command reads an image file directly (cat/type/
  Get-Content ...), inject a reminder that the output will be binary and the
  skill should be used instead.
- UserPromptSubmit: if the prompt references an image (explicit path,
  "[Unsupported Image]" marker, or image keywords with recent temp images),
  inject a reminder, listing likely pasted-image paths when found.

All other cases pass through untouched. Exit 0 always; stdout is empty for
pass-through, or JSON with hookSpecificOutput.additionalContext otherwise.
"""

import json
import os
import re
import sys
import tempfile
import time

from common import force_utf8_stdio

force_utf8_stdio()

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".bmp", ".svg", ".ico", ".avif", ".tif", ".tiff",
}
IMAGE_REF_RE = re.compile(r"\.(?:png|jpe?g|gif|webp|bmp|svg|ico|avif|tiff?)\b", re.IGNORECASE)
BASH_READ_RE = re.compile(
    r"\b(?:cat|type|more|less|head|tail|Get-Content|Get-Item)\s+[\"']?"
    r"([^\s\"']+\.(?:png|jpe?g|gif|webp|bmp|svg|ico|avif|tiff?))\b",
    re.IGNORECASE,
)
IMAGE_KEYWORDS = ("截图", "图片", "贴图", "粘贴", "screenshot", "pasted", "image", "贴了")

READ_REMINDER = (
    "Note: the file being read is an image. The current model may not be able to view "
    "images directly (the Read result may show [Unsupported Image]). If you cannot see "
    "the image content, invoke the image-vision skill to analyze it."
)
BASH_REMINDER = (
    "Note: this command reads an image file directly; its output will be binary or "
    "unreadable text. Do NOT rely on it to 'see' the image. If you need the image "
    "content, invoke the image-vision skill instead."
)
PROMPT_REMINDER = (
    "Note: the user message references an image (pasted screenshot or image file path). "
    "If you cannot see the image content, invoke the image-vision skill to analyze it "
    "before answering."
)


def inject(message):
    print(json.dumps({"hookSpecificOutput": {"additionalContext": message}}))


def find_recent_images(max_age=600, limit=3):
    """Return recently modified image paths from likely paste locations (shallow scan)."""
    roots = []
    try:
        for e in os.scandir(tempfile.gettempdir()):
            if e.is_dir() and "claude" in e.name.lower():
                roots.append(e.path)
    except OSError:
        pass
    roots += [tempfile.gettempdir(), os.path.expanduser("~/.claude")]

    now = time.time()
    found = []
    seen = set()
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            with os.scandir(root) as it:
                for e in it:
                    if not e.is_file() or e.path in seen:
                        continue
                    if os.path.splitext(e.name)[1].lower() not in IMAGE_EXTENSIONS:
                        continue
                    try:
                        if now - e.stat().st_mtime <= max_age:
                            found.append(e.path)
                            seen.add(e.path)
                    except OSError:
                        continue
        except OSError:
            continue
    found.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return found[:limit]


def handle_pretooluse(data):
    tool = data.get("tool_name")
    tool_input = data.get("tool_input") or {}
    if tool == "Read":
        file_path = tool_input.get("file_path", "")
        if os.path.splitext(file_path)[1].lower() in IMAGE_EXTENSIONS:
            inject(READ_REMINDER)
    elif tool == "Bash":
        command = tool_input.get("command") or ""
        if BASH_READ_RE.search(command):
            inject(BASH_REMINDER)


def handle_userpromptsubmit(data):
    prompt = data.get("user_prompt") or ""
    if "[Unsupported Image]" in prompt or IMAGE_REF_RE.search(prompt):
        inject(PROMPT_REMINDER)
        return
    low = prompt.lower()
    if any(k in low for k in IMAGE_KEYWORDS):
        recent = find_recent_images()
        if recent:
            inject(PROMPT_REMINDER + " Possibly relevant recent image files: " + "; ".join(recent))


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return  # malformed input; pass through

    try:
        event = data.get("hook_event_name")
        if event == "PreToolUse":
            handle_pretooluse(data)
        elif event == "UserPromptSubmit":
            handle_userpromptsubmit(data)
    except Exception:
        # Fail open: a hook bug must never block or alter a tool call.
        return


if __name__ == "__main__":
    main()
