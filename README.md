# image-vision

Claude Code 插件：让无法直接读图的模型（文本模型 / 视觉能力受限）获得图像理解能力。

图片会发送到你配置的 OpenAI 兼容视觉模型 API，分析结果以文本返回给当前模型。

## 安装

```bash
claude plugin marketplace add <owner>/image-vision-plugin
claude plugin install image-vision@image-vision
```

本地测试：`claude --plugin-dir <本仓库路径>`

## 配置

安装后复制配置模板并填写你的 API 信息：

```bash
cp skills/image-vision/config.example.json ~/.claude/image-vision.json
# 编辑 ~/.claude/image-vision.json：api_key / api_url / model
```

然后重启 Claude Code。

## 功能

- **skill**：模型读不了图时自动分析图片（本地文件、URL、粘贴截图），支持文本/JSON 结构化输出、多轮追问、大图自动压缩
- **hooks**：Read 图片文件、Bash 直接读图、用户消息含图时，自动提醒模型调用 skill

## 隐私

图片会发送到所配置的 API 端点（第三方服务）。敏感截图请先评估。
