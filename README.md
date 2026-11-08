<div align="center">

# Image to Word

**Turn images and scanned PDFs into editable Word documents with a browser workbench or CLI.**

![Web](https://img.shields.io/badge/Web-FastAPI-2563eb)
![CLI](https://img.shields.io/badge/CLI-Python-111827)
![Extraction](https://img.shields.io/badge/Extraction-MinerU-7c3aed)
![Output](https://img.shields.io/badge/Output-DOCX%20%2B%20Markdown-059669)

`uv run image-to-word serve`

</div>

Upload a scan, inspect the extracted content, and download an editable DOCX. The same conversion pipeline is available from the command line for repeatable file processing.

## Quick Start

Requirements: Python 3.11 or 3.12, uv, and a MinerU OpenAPI token.

```bash
git clone --branch main git@github.com:hhhx-lab/image-to-word.git
cd image-to-word
uv sync
cp .env.example .env
```

Set `MINERU_API_TOKEN` in `.env`, then start the web application:

```bash
uv run image-to-word serve
```

Open `http://127.0.0.1:8000`, upload an image or PDF, inspect the preview, and use the Word or Markdown download controls.

## Capability Matrix

| Capability | Behavior |
|---|---|
| Images | PNG, JPG, JPEG, WEBP, BMP, and TIFF uploads |
| PDF input | Whole-document conversion or selected page ranges |
| Formula and table recognition | Enabled by default; configurable per conversion |
| Editable Word | Requests DOCX output from MinerU and extracts it from the result bundle |
| Review material | Markdown, HTML preview, and the original result ZIP |
| Web and CLI | Interactive uploads and scriptable single-file conversion |

## Workflow

```text
Image or PDF
  |
  v
MinerU OpenAPI task
  |
  v
Poll task and download result bundle
  |
  v
Extract DOCX, Markdown, and preview assets
  |
  v
Inspect content and download editable output
```

## CLI Examples

```bash
uv run image-to-word convert ./input.png --out ./output.docx
uv run image-to-word convert ./paper.pdf --out ./paper.docx --page-ranges 1-3,5
uv run image-to-word convert ./input.png --out ./output.docx --language ch --model-version vlm --interval 5 --timeout 1200
uv run image-to-word convert ./input.png --out ./output.docx --disable-formula
uv run image-to-word convert ./input.png --out ./output.docx --disable-table
```

The web form exposes language, model version, page ranges, OCR, formula recognition, and table recognition. The default language is `ch` and the default model is `vlm`.

## Configuration

Keep credentials in `.env`. The annotated `.env.example` is the configuration template.

| Variable | Purpose |
|---|---|
| `MINERU_API_TOKEN` | Required MinerU OpenAPI token |
| `MINERU_API_BASE` | API base, default `https://mineru.net/api/v4` |
| `MINERU_MODEL_VERSION` | Default model, `vlm` |
| `IMAGE_TO_WORD_DATA_DIR` | Web task storage, default `data/jobs` |
| `IMAGE_TO_WORD_PREVIEW_LIMIT` | Preview size limit |

MinerU API documentation: [MinerU documentation](https://mineru.net/doc/docs).

## Outputs and Storage

Web tasks are stored under `data/jobs/`; CLI work files are stored under `data/cli/`. Uploads, downloaded bundles, generated documents, virtual environments, and caches are excluded from Git. A fresh checkout needs new input files and rebuilt runtime state.

## Repository Layout

```text
.
|-- README.md
|-- .env.example
|-- pyproject.toml
|-- uv.lock
|-- image_to_word/
|   |-- app.py
|   |-- cli.py
|   |-- config.py
|   |-- mineru.py
|   `-- storage.py
|-- static/
|-- tests/
`-- data/
    `-- .gitkeep
```

## Development

```bash
uv run pytest
uv run image-to-word serve --reload
```

Use the project uv environment for Python dependencies. Keep dependency installation separate from system Python and Homebrew Python.

## Troubleshooting and Boundaries

- Missing token: fill in `.env` and restart the service.
- No Word file: the provider may not have returned DOCX. Download the original bundle or Markdown to inspect the result.
- Missing preview images: resource paths can vary across result bundles; inspect the downloaded DOCX and original assets.
- Conversion depends on MinerU availability, supported formats, and account quotas.
- Review extracted text, formulas, tables, and page layout before using a document as a final deliverable. Upload only documents you are authorized to send to the extraction provider.

## Restore a Local Checkout

Clone the SSH repository from the quick start, restore your saved `.env` to the checkout root, and run `uv sync`. Existing credentials should be restored before generating a replacement environment file.
