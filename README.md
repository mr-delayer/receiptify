# receiptify — English to Hanzi Sound-Alike

receiptify is a Cloudflare Worker that transliterates English words and phrases into Chinese characters that sound similar when spoken. The worker exposes both an interactive single-page UI and a simple JSON API, making it easy to experiment with phonetic renderings or integrate them into other apps.

The project also includes two generative art modes that turn text or images into 15 × 33 grids of Hanzi characters with density-mapped glyphs.

## Features

- **Text transliteration** – Maps English words (and numbers) into pronounceable Chinese character strings using curated overrides, IPA data, and spelling heuristics.
- **Image → Hanzi art** – Samples an image onto a 15-column strip, tiles it into 32 rows, and emits Hanzi selected by brightness.
- **Big text → Hanzi art** – Renders large glyphs into the same 15 × 33 format with support for horizontal (rotated) and vertical orientations, adjustable fonts, and chunked output.
- **JSON API** – `POST /api` accepts text, separator, length, and optional TTS tag flags. Responses are cached via Cloudflare’s Worker KV cache API.
- **Copy-ready output** – All art chunks expose raw 495-character strings (no line breaks) for quick pasting.
- **Deployable with Wrangler** – Ready-to-ship Worker project; deployment scripts and bindings managed by Wrangler.

## Getting Started

### Requirements

- Node.js 18+
- Python 3.12 configured for Pyodide bundling
- Cloudflare Wrangler (`npm install -g wrangler`) for deployment

### Installation

Clone the repository and install Node dependencies:

```bash
git clone <repo-url>
cd receiptify
npm install
```

> The transliteration logic runs inside the Worker with Pyodide, so no additional build step is required for development.

### Running Locally

Use Wrangler to start a development server:

```bash
npx wrangler dev
```

This launches the Worker on <http://localhost:8787>, serving both the UI and API endpoints.

### Testing

Python unit tests (none at present, but placeholder provided):

```bash
pytest
```

### Deployment

Deploy to Cloudflare Workers with:

```bash
npx wrangler deploy
```

Wrangler bundles the Python/JS runtime, attaches the JSON data modules, and publishes the Worker. The deployment output includes the live URL and version ID.

## UI Overview

### Text Mode

- Enter any English text and click **Convert**.
- Optional controls:
  - Toggle separator dots (`·`).
  - Force a fixed-length output (pads/truncates while respecting the optional TTS tag).
  - Prepend the ElevenLabs-compatible TTS voice tag.

### Image Mode

- Upload an image and hit **Generate art**.
- The Worker maps brightness across a defined Hanzi ramp (`ART_RAMP`) to create a 15 × 33 grid.
- Copying the output grabs a newline-free 495-character string.

### Big Text Mode

- Input text and choose a font/orientation before clicking **Generate big text**.
- Orientation options:
  - **Horizontal** – Rotates glyphs clockwise before sampling.
  - **Vertical** – Keeps glyphs upright and compresses spacing vertically.
- Font options include bold sans-serif (default), serif, Comic Neue, script, and Gothic/blackletter stacks.
- Adjust font size and weight to fine-tune the rendered glyphs.
- Long input is chunked into multiple 33-line blocks, each with its own copy button.

## API Usage

`POST /api` with JSON payload:

```json
{
  "text": "hello world",
  "separator": "·",
  "length": 120,
  "ttsTag": true
}
```

Response:

```json
{
  "input": "hello world",
  "output": "Cheer200 Xijinping: ...",
  "separator": "·",
  "note": "Approximate phonetic transliteration, not translation."
}
```

Results are cached in Cloudflare Cache API (default TTL 72 hours). A simple GET variant is available via `/?q=hello%20world` for quick experiments.

## Project Structure

```
receiptify/
├── src/
│   └── worker.py        # Pyodide-powered Worker script with UI + API logic
├── tools/               # Utility scripts (if any)
├── test_translit.py     # Test harness placeholder
├── wrangler.toml        # Wrangler configuration
├── package.json         # Node dependencies (dev tooling)
└── README.md            # Project documentation
```

Supporting JSON datasets (IPA mappings, name lists, examples) live under `src/` and are bundled as additional modules during deployment.

## Contributing

1. Fork and clone the repo.
2. Create a feature branch from `main`.
3. Make your changes and add tests where useful.
4. Run `pytest` to ensure nothing regresses.
5. Open a pull request describing the change and expected behavior.

## License

This project is released under the MIT License. See [`LICENSE`](LICENSE) if provided, or treat the repository as MIT by default unless superseded by an explicit license file.
