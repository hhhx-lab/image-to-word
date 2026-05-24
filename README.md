# Image to Word

把图片、扫描 PDF 转成可编辑的 Word 文档。项目提供两种入口：

- Web 前端：上传文件、查看 MinerU 生成结果、下载 `.docx` / Markdown。
- CLI 命令：适合批处理或脚本调用。

底层使用 MinerU OpenAPI。真实的 MinerU Key 只通过本地 `.env` 读取，不会进入仓库。

## 功能

- 支持常见图片格式：PNG、JPG、JPEG、WEBP、BMP、TIFF。
- 支持 PDF 上传，可按页码范围转换。
- 默认开启公式识别和表格识别。
- 优先从 MinerU 结果包中提取可编辑 `.docx`。
- 同时保留 Markdown、HTML 预览和原始结果 zip，便于核对。

## 环境要求

- Python 3.11 或 3.12
- uv
- MinerU OpenAPI Token

不要把 MinerU Token 写进代码或提交到 Git。项目已忽略 `.env`、本地上传和转换产物。

## 快速开始

1. 安装依赖

```bash
uv sync
```

2. 配置 MinerU Key

```bash
cp .env.example .env
```

编辑 `.env`：

```bash
MINERU_API_TOKEN=你的_MinerU_Key
MINERU_API_BASE=https://mineru.net/api/v4
```

3. 启动前端

```bash
uv run image-to-word serve
```

浏览器打开：

```text
http://127.0.0.1:8000
```

4. 上传图片或 PDF

转换完成后，页面右上角会出现：

- `导出 Word`
- `导出 Markdown`

## 命令行用法

单文件转换：

```bash
uv run image-to-word convert ./input.png --out ./output.docx
```

PDF 指定页码：

```bash
uv run image-to-word convert ./paper.pdf --out ./paper.docx --page-ranges 1-3,5
```

常用选项：

```bash
uv run image-to-word convert ./input.png --out ./output.docx \
  --language ch \
  --model-version vlm \
  --interval 5 \
  --timeout 1200
```

关闭公式或表格识别：

```bash
uv run image-to-word convert ./input.png --out ./output.docx --disable-formula
uv run image-to-word convert ./input.png --out ./output.docx --disable-table
```

## Web 参数

- `语言`：默认中文 `ch`，也可选择英文或自动。
- `模型`：默认 `vlm`。
- `页码`：可填写 `1-3,5`，留空表示全量转换。
- `公式`：开启 MinerU 公式识别。
- `表格`：开启 MinerU 表格识别。
- `OCR`：扫描图片和扫描 PDF 通常保持开启。

## 目录结构

```text
image_to_word/
  app.py          # FastAPI Web 服务
  cli.py          # 命令行入口
  config.py       # 环境变量配置
  mineru.py       # MinerU API 封装、结果包提取
  storage.py      # 本地任务状态
static/
  index.html
  styles.css
  app.js
tests/
  test_mineru.py
data/
  .gitkeep        # 本地任务目录占位，转换结果不会提交
```

## MinerU 配置

`.env` 支持以下变量：

```bash
MINERU_API_TOKEN=        # 必填
MINERU_API_BASE=         # 默认 https://mineru.net/api/v4
MINERU_MODEL_VERSION=vlm # 默认 vlm
IMAGE_TO_WORD_DATA_DIR=data/jobs
IMAGE_TO_WORD_PREVIEW_LIMIT=200000
```

MinerU API 参考：<https://mineru.net/doc/docs>

## 本地数据与安全

本地上传和转换结果默认放在：

```text
data/jobs/
```

命令行转换的临时结果默认放在：

```text
data/cli/
```

这些目录已写入 `.gitignore`。如需清理：

```bash
rm -rf data/jobs data/cli
```

## 开发

运行测试：

```bash
uv run pytest
```

开发模式启动：

```bash
uv run image-to-word serve --reload
```

## 常见问题

### 页面提示缺少 MinerU Key

确认已经创建 `.env`，并填写：

```bash
MINERU_API_TOKEN=你的_MinerU_Key
```

修改 `.env` 后重启服务。

### 转换完成但没有 Word 文件

项目提交任务时会向 MinerU 请求 `docx` 额外格式。如果结果包没有 `.docx`，通常是 MinerU 任务返回异常或该文件类型暂未产出 Word。可以先下载原始 zip 或 Markdown 核对内容。

### 预览中图片不显示

优先使用 MinerU 返回的 HTML 预览。不同 MinerU 结果包的资源路径可能略有差异；Word 文件仍以下载的 `.docx` 为准。

### 不想提交本地结果

默认不会提交 `.env`、`data/jobs/`、`data/cli/`、`*.docx`、`*.zip`、`*.pdf`。提交前可运行：

```bash
git status --short
```
