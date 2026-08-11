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
 * On first run (no usable ~/.claude/image-vision.json yet) it launches the
 * interactive config wizard (model id / API key / URL); pass --setup to
 * re-open the wizard even when a config already exists.
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

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

// Files that define a skill version; an installed copy is current when none
// of them is newer in the source.
const MARKER_FILES = [
  "SKILL.md",
  "config.example.json",
  "scripts/analyze_image.py",
  "scripts/read_image_hook.py",
  "scripts/setup.py",
  "scripts/common.py",
];

if (!fs.existsSync(SRC)) {
  console.error(`Error: skill not found at ${SRC}`);
  process.exit(1);
}

function isUpToDate(dest) {
  for (const rel of MARKER_FILES) {
    try {
      const srcStat = fs.statSync(path.join(SRC, rel));
      const destStat = fs.statSync(path.join(dest, rel));
      if (srcStat.mtimeMs > destStat.mtimeMs || srcStat.size !== destStat.size) return false;
    } catch {
      return false; // missing on either side → refresh
    }
  }
  return true;
}

const installed = [];
for (const [label, ...parts] of TARGETS) {
  const dest = path.join(home, ...parts, "image-vision");
  if (fs.existsSync(dest) && isUpToDate(dest)) {
    installed.push([label, dest, false, false]);
    continue; // nothing changed; leave the existing copy alone
  }
  const tmp = `${dest}.new`;
  const backup = `${dest}.old`;
  try {
    // Copy to a temp sibling first so the existing install stays intact if
    // the copy fails; swap only once the new copy is fully in place.
    fs.rmSync(tmp, { recursive: true, force: true });
    fs.cpSync(SRC, tmp, {
      recursive: true,
      filter: (src) => !src.split(path.sep).includes("__pycache__"),
    });
    const existed = fs.existsSync(dest);
    if (existed) {
      fs.rmSync(backup, { recursive: true, force: true });
      fs.renameSync(dest, backup);
    }
    fs.renameSync(tmp, dest);
    try {
      fs.rmSync(backup, { recursive: true, force: true }); // stale .old is harmless
    } catch {}
    installed.push([label, dest, existed, true]);
  } catch (err) {
    // If the swap failed midway, restore the previous install.
    if (!fs.existsSync(dest) && fs.existsSync(backup)) fs.renameSync(backup, dest);
    console.warn(`  ! ${label}: 安装失败 (${err.message})`);
  }
}

if (!installed.length) {
  console.error("\nError: 未安装到任何 agent 目录。请检查目录权限；Node 需 >= 16.7（fs.cpSync 依赖）。");
  process.exit(1);
}

console.log("image-vision skill 已安装到:");
for (const [label, dest, existed] of installed) {
  console.log(`  ${label}: ${dest}${existed ? " (已更新)" : ""}`);
}

const changed = installed.some(([, , , copied]) => copied);
if (changed && installed.some(([label]) => label === "Claude Code")) {
  console.log("\n提示: 此安装只装 skill，不含 Claude Code 的自动提醒 hook。需要 hook 时：");
  console.log("  ① 插件方式: /plugin marketplace add MLWND/give-your-model-eye 后 /plugin install image-vision@image-vision");
  console.log("  ② 手动注册: 在 ~/.claude/settings.json 注册 scripts/read_image_hook.py（见安装副本 README.md 的 Hook 一节）");
  console.log("若同时使用插件方式，本地副本与插件会重复注册，请二选一。");
}

// Config wizard: run when no usable config exists, or on explicit --setup.
const cfgPath = path.join(home, ".claude", "image-vision.json");

// Placeholder values from the shipped template; not real configuration.
function placeholderMarkers() {
  try {
    const ex = JSON.parse(fs.readFileSync(path.join(SRC, "config.example.json"), "utf8"));
    let host = "";
    try { host = new URL(ex.api_url).hostname; } catch {}
    return [host, ex.api_key || "", ex.model || ""];
  } catch {
    return ["", "", ""];
  }
}

function configReady() {
  let cfg = null;
  try {
    cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
  } catch {
    return false; // missing, unreadable, or invalid JSON → needs the wizard
  }
  if (!cfg || typeof cfg !== "object") return false;
  const url = String(cfg.api_url || "");
  const key = String(cfg.api_key || "");
  const model = String(cfg.model || "");
  if (!url || !key || !model) return false;
  if (!/^https?:\/\//i.test(url)) return false;
  const [phHost, phKey, phModel] = placeholderMarkers();
  if ((phHost && url.includes(phHost)) || (phKey && key.includes(phKey)) || (phModel && model.includes(phModel))) {
    return false;
  }
  return true;
}

const forceSetup = process.argv.slice(2).includes("--setup");
if (configReady() && !forceSetup) {
  console.log(`\n配置已存在 (${cfgPath})，直接可用。`);
  console.log("如需修改配置: npx github:MLWND/give-your-model-eye --setup");
} else {
  const setup = path.join(installed[0][1], "scripts", "setup.py");
  console.log("\n配置视觉模型 API（模型 id / API key / URL）。已配置过可回车保留现有值。");
  const wizardRan = [["python", []], ["python3", []], ["py", ["-3"]]].some(([launcher, launcherArgs]) => {
    const r = spawnSync(launcher, [...launcherArgs, setup], { stdio: "inherit" });
    // The launcher itself was not found (missing binary, or Windows' store
    // stub for python); try the next candidate. Any other outcome means the
    // wizard ran (or failed on its own) and retrying won't help.
    const notFound = (r.error && r.error.code === "ENOENT") ||
                     (process.platform === "win32" && r.status === 9009);
    return !notFound;
  });
  if (!wizardRan) {
    console.log("(未找到可用的 python（python / python3 / py），跳过配置向导。请安装 Python 3 后运行 python scripts/setup.py)");
  }
}
