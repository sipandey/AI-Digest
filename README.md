# arXiv Daily Digest

Automated pipeline that fetches new arXiv papers each morning, ranks them by relevance, generates plain-language summaries via OpenAI, and pushes the digest to a Notion database.

## Architecture

```
fetcher.py      — pulls papers from arXiv for configured categories
ranker.py       — scores and filters to the top N papers
summarizer.py   — calls OpenAI to produce a short summary per paper
notion_client.py — writes each paper as a Notion database entry
pipeline.py     — ties all stages together; entry point
```

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd AIDigest
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Where to get it |
|---|---|
| `OPENAI_API_KEY` | platform.openai.com → API keys |
| `NOTION_TOKEN` | notion.so → Settings → Connections → Develop integrations |
| `NOTION_DATABASE_ID` | The 32-char ID in your Notion database URL |

### 3. Run locally

Activate the venv first (once per terminal session):

```bash
source .venv/bin/activate
```

Then run individual stages or the full pipeline:

```bash
# Unit tests — no API keys needed
python -m src.test_pipeline

# Fetcher only — hits arXiv, no API key needed
python -m src.fetcher

# Ranker only — requires OPENAI_API_KEY
python -m src.ranker

# Notion client only — requires NOTION_TOKEN + NOTION_DATABASE_ID
python -m src.notion_client

# Full end-to-end pipeline
python -m src.pipeline
```

Outputs are written to `daily_papers/` and a run log is appended to `logs/`.

## Automated runs

The GitHub Actions workflow (`.github/workflows/daily_digest.yml`) triggers at **08:00 UTC** every day.

Add the three environment variables as **repository secrets** under Settings → Secrets and variables → Actions:

- `OPENAI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`

You can also trigger a run manually from the Actions tab via **workflow_dispatch**.
