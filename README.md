# AI Digest

> A daily arXiv digest built for developers learning AI and building AI-powered products.

Every day at **7:00 AM IST**, this pipeline:
1. Pulls the latest papers from arXiv across 5 categories (ML, NLP, IR, AI, HCI)
2. Filters for topics relevant to building with LLMs, AI agents, search, and AI products
3. Scores each paper using GPT-4o-mini across 4 criteria tailored for a developer audience
4. Pushes a structured digest to your Notion database — summaries written without jargon

---

## Who this is for

This digest is designed for someone with a **web development background** (JS, frontend, backend) who is learning AI and wants to integrate it into real products. Every summary is written to answer: *can I use this, and how do I start?*

---

## How papers are scored

Each paper is scored out of **10** across four criteria:

| Criterion | Max | What it measures |
|---|---|---|
| **Builder Relevance** | 3 | Can you build something with this today? |
| **Understandability** | 3 | Can a developer new to AI follow the core idea? |
| **Real World Grounding** | 2 | Is it tested on real problems, not toy datasets? |
| **Novelty & Timing** | 2 | Is this a new idea worth knowing about early? |

Only papers scoring **7 or higher** make it into the digest.

Each paper also includes:
- **Builder Takeaway** — the single most useful thing you can take away as a developer
- **Before reading** — what concept to understand first before diving in

---

## What you get in Notion

Each day's digest is a single Notion page with:
- **Run stats** — papers fetched, papers that passed the 7/10 threshold, top score
- **Cluster summary** — how many papers landed in each topic group today
- **One toggle per paper** — score breakdown, problem, approach, results, builder takeaway, and a learning path pointer
- **Status** — `Complete` if papers were found, `Empty` if nothing matched that day

---

## Topics covered

| Group | Sample keywords |
|---|---|
| **Building with LLMs** | RAG, prompt engineering, in-context learning, function calling, hallucination, grounding |
| **AI Agents and Automation** | AI agent, agentic, multi-agent, code generation, copilot, workflow automation |
| **Practical AI Systems** | semantic search, vector database, embedding, recommendation system, question answering |
| **AI Product and UX** | chatbot, conversational AI, human-AI interaction, explainability, AI safety |
| **Multimodal and Emerging** | multimodal, vision language, text to image, document AI, speech recognition |

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
- `daily_papers/raw_YYYY_MM_DD.json` — raw fetcher output
- `daily_papers/digest_YYYY_MM_DD.md` — scored digest with summaries
- `logs/run_YYYY_MM_DD.log` — run summary with counts and Notion URL

---

## Automated daily runs (GitHub Actions)

The workflow runs automatically at **7:00 AM IST (01:30 UTC)** every day and commits the digest files back to the repo.

To enable it, add these three **repository secrets** under Settings → Secrets and variables → Actions:

- `OPENAI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`

You can also trigger a run on demand from the **Actions** tab → **Daily arXiv Digest** → **Run workflow**.
