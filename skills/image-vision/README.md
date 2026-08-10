# image-vision (看图)

让无法直接读图的文本模型获得图像理解能力：把图片发给 OpenAI 兼容的视觉模型 API，把分析结果以文本形式返回给调用方。

## 安装

**方式一：GitHub marketplace（推荐，一键安装/更新）**

```bash
claude plugin marketplace add <owner>/image-vision-plugin
claude plugin install image-vision@image-vision
```

**方式二：本地插件目录（测试用，无需发布）**

```bash
claude --plugin-dir /path/to/image-vision-plugin
```

**方式三：手动复制（不打包）**

把 `skills/image-vision/` 复制到 `~/.claude/skills/`，并在 `~/.claude/settings.json` 手动注册 hook（见下文 Hook）。

安装后 **配置 API 并重启 Claude Code**（hook 在会话启动时加载）。

## 配置

**把 `config.example.json` 复制为 `~/.claude/image-vision.json` 并填入你的密钥**（放用户目录是为了避免插件更新覆盖配置）。

优先级：环境变量 > `~/.claude/image-vision.json` > skill 目录 `config.json`（本地开发用）。

| 配置项 | 环境变量 | 配置字段 |
|---|---|---|
| API 端点 | `IMAGE_VISION_API_URL` | `api_url` |
| API 密钥 | `IMAGE_VISION_API_KEY` | `api_key` |
| 模型名 | `IMAGE_VISION_MODEL` | `model` |

任何 OpenAI 兼容 Chat Completions 服务均可。缺配置时脚本会报清晰错误。

> 注意：同时安装本地版（`~/.claude/skills/image-vision/`）和插件版会重复注册 hook、重复提醒。二选一；改用插件版时删除本地目录和 `~/.claude/settings.json` 里手动注册的 hook 条目。

## 目录结构

```
image-vision/
├── SKILL.md              — skill 定义（触发条件 + 使用流程）
├── config.example.json   — 配置模板（复制为 ~/.claude/image-vision.json 并填写）
├── README.md             — 本文档
└── scripts/
    ├── analyze_image.py  — 核心脚本（图片 → 视觉模型 → 文本分析）
    └── read_image_hook.py— 配套 hook（Read/Bash 读图、用户消息含图时提醒调用 skill）
```

## 用法

```bash
python scripts/analyze_image.py --image "<path-or-url>" [--image <更多图>] \
  [--prompt "问题"] [--format text|json] [--prev "前一轮分析"] \
  [--max-size 2048] [--max-tokens N] [--verbose]
```

- **`--format json`**：结构化输出 `{summary, elements:[{image, type, content, bbox, conf}]}`，bbox 归一化 0-1000（近似值）。适合 UI 分析、元素定位。
- **`--prev`**：多轮追问，把上一轮分析传入，第二轮会重复携带图像。
- 本地图片自动 base64 编码；超过 `--max-size` 自动压缩（Pillow，动画 GIF 除外）；HEIC/SVG 明确报错。

## Hook

安装为插件时，hook 通过插件的 `hooks/hooks.json` 自动注册（`${CLAUDE_PLUGIN_ROOT}` 指向插件目录，无需手动配置）。手动安装时需在 `~/.claude/settings.json` 注册 `read_image_hook.py`。三种注入"调用 image-vision skill"提醒的场景：
- **PreToolUse(Read)**：读取图片文件时
- **PreToolUse(Bash)**：命令直接读图（cat/type/Get-Content）时
- **UserPromptSubmit**：用户消息含图片路径、`[Unsupported Image]` 标记或图片关键词（附 temp 最近图片路径）时

Hook 配置改动需重启 Claude Code 生效。

## API 参考

OpenAI 兼容 Chat Completions API（`POST <api_url>`，`Authorization: Bearer <api_key>`）。

### 请求体

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `model` | string | 是 | 来自配置 |
| `messages` | array | 是 | `system` / `user` / `assistant` |
| `messages[].content` | string / array | 是 | 文本，或 `text` + `image_url` 块数组 |
| `max_tokens` | number | 否 | 推理模型需覆盖 reasoning + 回答（脚本默认文本 4096 / JSON 8192） |
| `temperature` | number | 否 | 越低越确定 |
| `stream` | boolean | 否 | 流式 |
| `tools` / `tool_choice` | array / object | 否 | 函数调用 |

### 图像输入

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Describe the content of this image."},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
  ]
}
```

`image_url.url` 接受公开 URL 或 base64 data URL（均已验证可用）；多图重复 `image_url` 块。

### 响应

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "生成的回答",
      "reasoning_content": "可选的内部推理"
    },
    "finish_reason": "stop"
  }]
}
```

- 答案在 `choices[0].message.content`；`reasoning_content` 为推理模型的内部思考（可选）。
- 推理模型 `max_tokens` 不足时 `finish_reason` 为 `length`，脚本会输出诊断提示。
- 网络错误和 HTTP 5xx/429 自动重试一次；4xx（密钥无效等）快速失败并输出 API 错误体。

## 隐私

图片会发送到所配置的 API 端点（第三方服务）。敏感截图请先评估。
