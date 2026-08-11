#!/usr/bin/env node
/**
 * Universal installer for the image-vision skill.
 *
 * Copies skills/image-vision/ into every AI agent's skill directory:
 *   Claude Code, Codex CLI, opencode, Gemini CLI, Copilot CLI
 * (plus the cross-agent ~/.agents/skills/ directory).
 *
 * Run via:  npx github:MLWND/give-your-model-eye
 * or locally:  node install.js
 *
 * On first run (no ~/.claude/image-vision.json yet) it launches the
 * interactive config wizard (model id / API key / URL).
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execSync } = require("child_process");

const SRC = path.join(__dirname, "skills", "image-vision");
const home = os.homedir();

// [label, ...path parts under home]
const TARGETS = [
  ["Claude Code", ".claude", "skills"],
  ["Codex CLI", ".codex", "skills"],
  ["opencode", ".config", "opencode", "skills"],
  ["Gemini CLI", ".gemini", "skills"],
  ["Copilot CLI", ".copilot", "skills"],
  ["通用 (~/.agents/skills)", ".agents", "skills"],
];

if (!fs.existsSync(SRC)) {
  console.error(`Error: skill not found at ${SRC}`);
  process.exit(1);
}

const installed = [];
for (const [label, ...parts] of TARGETS) {
  const dest = path.join(home, ...parts, "image-vision");
  try {
    fs.rmSync(dest, { recursive: true, force: true });
    fs.cpSync(SRC, dest, { recursive: true });
    installed.push([label, dest]);
  } catch (err) {
    console.warn(`  ! ${label}: 安装失败 (${err.message})`);
  }
}

console.log("image-vision skill 已安装到:");
for (const [label, dest] of installed) console.log(`  ${label}: ${dest}`);

// First run: launch the config wizard if no config exists yet.
const cfgPath = path.join(home, ".claude", "image-vision.json");
if (fs.existsSync(cfgPath)) {
  console.log(`\n配置已存在 (${cfgPath})，直接可用。`);
} else if (installed.length) {
  const setup = path.join(installed[0][1], "scripts", "setup.py");
  console.log("\n首次使用：配置视觉模型 API（模型 id / API key / URL）。");
  try {
    execSync(`python "${setup}"`, { stdio: "inherit" });
  } catch (err) {
    console.log("(跳过：未能运行 python，之后可手动运行 python scripts/setup.py)");
  }
}
