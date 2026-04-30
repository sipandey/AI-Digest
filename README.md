# AI Digest

> Your daily briefing on the latest arXiv research — automatically fetched, scored, and delivered to Notion every morning.

Every day at **7:00 AM IST**, this pipeline:
1. Pulls the latest papers from arXiv across Machine Learning, NLP, and Information Retrieval
2. Filters for topics relevant to production ML — RAG, recommendations, LLM serving, AI agents, search ranking
3. Scores each paper 1–10 using GPT-4o-mini (novelty, practical applicability, evaluation quality)
4. Pushes a structured digest to your Notion database with summaries and production takeaways

---

## What you get in Notion

Each day's digest is a single Notion page with:
- **Run stats** — papers fetched, papers that passed the 7/10 threshold, top score
- **One toggle per paper** — score, cluster, problem, approach, results, and a one-line production takeaway
- **Status** — `Complete` if papers were found, `Empty` if nothing matched that day

---

## Setup

### Prerequisites
- Python 3.9+
- An OpenAI account (GPT-4o-mini access)
- A Notion account with an integration created at [notion.so/my-integrations](https://www.notion.so/my-integrations)

### 1. Clone and install

```bash
git clone https://github.com/sipandey/AI-Digest.git
cd AI-Digest
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up your Notion database

Create a new **full-page database** in Notion and add these columns:

| Column name | Type |
|---|---|
| `Name` | Title (default) |
| `Run Date` | Date |
| `Papers Fetched` | Number |
| `Papers Passed` | Number |
| `Top Score` | Number |
| `Status` | Select → add options: `Complete`, `Empty` |

Then share the database with your integration: open the database → `...` → **Connections** → select your integration.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:

| Variable | Where to find it |
|---|---|
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) → API keys |
| `NOTION_TOKEN` | [notion.so/my-integrations](https://www.notion.so/my-integrations) → your integration → Internal Integration Token |
| `NOTION_DATABASE_ID` | Your database URL — the 32-char ID **before** the `?v=` part |

> **Tip:** If your database URL is `https://notion.so/abc123...?v=xyz`, the ID is `abc123...`

---

## Running locally

Activate the venv first (once per terminal session):

```bash
source .venv/bin/activate
```

| Command | What it does | API keys needed |
|---|---|---|
| `python -m src.test_pipeline` | Run all unit tests | None |
| `python -m src.fetcher` | Fetch from arXiv and save raw JSON | None |
| `python -m src.ranker` | Score and summarize papers | `OPENAI_API_KEY` |
| `python -m src.notion_client` | Push sample papers to Notion | `NOTION_TOKEN`, `NOTION_DATABASE_ID` |
| `python -m src.pipeline` | Full end-to-end run | All three |

Output files:
- `daily_papers/raw_YYYY_MM_DD.json` — raw fetcher results
- `daily_papers/digest_YYYY_MM_DD.md` — scored digest (markdown)
- `logs/run_YYYY_MM_DD.log` — run summary with counts and Notion URL

---

## Automated daily runs (GitHub Actions)

The workflow runs automatically at **7:00 AM IST (01:30 UTC)** every day and commits the digest files back to the repo.

To enable it, add these three **repository secrets** under Settings → Secrets and variables → Actions:

- `OPENAI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`

You can also trigger a run on demand from the **Actions** tab → **Daily arXiv Digest** → **Run workflow**.

---

## Topics covered

| Cluster | Keywords |
|---|---|
| RAG | RAG, retrieval-augmented generation |
| Recommendation | collaborative filtering, cold-start, session-based |
| LLM Serving | vLLM, KV cache, quantization, inference optimization |
| AI Agents | AI agent, agentic, tool use, function calling |
| Search & Ranking | search ranking, learning to rank, neural ranking |
