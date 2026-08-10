---
name: image-vision
description: This skill should be used when the user asks to "analyze this image", "看看这张图", "图片里有什么", "分析这张图片", "识别图片内容", or when the current model cannot read or view an image file (image reading fails, or the model lacks vision capability). Provides image understanding via a vision model API (OpenAI-compatible; configured in config.json).
---

# Image Vision (看图)

## Purpose

Analyze images that the current model cannot read itself. Sends the image to a vision model via its OpenAI-compatible Chat Completions API (endpoint, model, and key configured in `config.json`), receives the analysis as text, and uses it to answer the user.

## When to Use

- The user asks to analyze/describe/read an image (local path, pasted screenshot, or URL).
- The current model fails to read an image file or lacks vision.
- A hook reminder (see Companion Hook) flags that an image read may fail.

## How to Use

1. **Locate the image source.** Local file path (pasted screenshots live in temp dirs; the hook lists likely paths) or http(s) URL.

2. **Craft the prompt** for what the user wants:
   - General description: omit `--prompt` (script default).
   - Extract text: `--prompt "Extract all text verbatim, preserving layout order."`
   - UI/screenshot: `--prompt "Identify main UI elements, layout, and any issues."`
   - Specific question: pass the user's question; answer only what it asks.
   - Multiple images: repeat `--image`; reference "image 1", "image 2" in the prompt.

3. **Run the script** from this skill's base directory (shown in the skill header):

   ```bash
   python scripts/analyze_image.py --image "<path-or-url>" --prompt "<question>"
   ```

   Local files are base64-encoded automatically; URLs pass through. Add `--verbose` for the model's reasoning; adjust `--max-tokens` if a response is truncated.

4. **Follow-up questions (multi-turn):** pass the previous analysis so the vision model has context:
   `--prev "<previous output>"` — the follow-up question goes in `--prompt`.

5. **Relay the result** as the image's actual content, in the user's language. On script failure, report the error.

## Modes

- **Text (default):** free-form analysis.
- **Structured (`--format json`):** returns validated JSON: `{summary, elements:[{type, content, bbox, conf}]}` with bbox normalized 0-1000. Use when the answer needs element-level detail (UI analysis, element positions, text extraction with layout). Note: bbox is approximate — treat as rough locations, not pixel-accurate.
- **Downscaling:** local images with a longer side > 2048px are auto-downscaled (Pillow) to avoid API rejection; `--max-size 0` disables.

## Notes

- API config: `~/.claude/image-vision.json` (recommended) or `config.json` in the skill directory (`api_url`, `api_key`, `model`); env vars `IMAGE_VISION_API_URL` / `IMAGE_VISION_API_KEY` / `IMAGE_VISION_MODEL` override both.
- Reasoning models: `max_tokens` 4096 covers reasoning + answer; network/API 5xx errors retry once.
- Formats: png, jpg/jpeg, gif, webp, bmp, svg, ico, avif, tif/tiff; mime guessed from extension. HEIC fails with a clear error (unsupported).
- **Privacy**: images are sent to the configured API endpoint (third-party service).

## Companion Hook

One script (`scripts/read_image_hook.py`) covers three cases; registered automatically when installed as a plugin (`hooks/hooks.json`), or manually via `~/.claude/settings.json` for direct installs:
- **PreToolUse (Read)** — image file read → reminder.
- **PreToolUse (Bash)** — command reads an image directly (cat/type/Get-Content) → reminder not to rely on binary output.
- **UserPromptSubmit** — prompt references an image (path, `[Unsupported Image]`, or image keywords) → reminder, listing recent temp image paths when found.

Loaded at session start — restart Claude Code after changes.

## Additional Resources

- **`README.md`** — project overview, config, CLI usage, and API reference.
