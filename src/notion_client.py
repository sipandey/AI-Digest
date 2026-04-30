"""Writes each daily digest run as a single Notion database page."""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _get(token: str, path: str) -> dict:
    r = requests.get(f"{NOTION_API}/{path}", headers=_headers(token))
    r.raise_for_status()
    return r.json()


def _post(token: str, path: str, body: dict) -> dict:
    r = requests.post(f"{NOTION_API}/{path}", headers=_headers(token), json=body)
    r.raise_for_status()
    return r.json()


def _patch(token: str, path: str, body: dict) -> dict:
    r = requests.patch(f"{NOTION_API}/{path}", headers=_headers(token), json=body)
    r.raise_for_status()
    return r.json()


def _delete(token: str, path: str) -> dict:
    r = requests.delete(f"{NOTION_API}/{path}", headers=_headers(token))
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Notion block builders
# ---------------------------------------------------------------------------

def _rich_text(content: str) -> list:
    return [{"type": "text", "text": {"content": content[:2000]}}]


def _heading_1(text: str) -> dict:
    return {"object": "block", "type": "heading_1", "heading_1": {"rich_text": _rich_text(text)}}


def _callout(text: str) -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": _rich_text(text),
            "icon": {"type": "emoji", "emoji": "📋"},
        },
    }


def _paragraph(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(text)}}


def _toggle(label: str, children: list) -> dict:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": _rich_text(label),
            "children": children,
        },
    }


def _paper_toggle(paper: dict) -> dict:
    children = [
        _paragraph(f"Score: {paper.get('score', '?')}/10  |  Cluster: {paper.get('cluster', '?')}  |  arXiv: {paper.get('id', '?')}"),
        _paragraph(f"PDF: {paper.get('pdf_url', '')}"),
        _paragraph(f"Problem: {paper.get('problem', '')}"),
        _paragraph(f"Approach: {paper.get('approach', '')}"),
        _paragraph(f"Results: {paper.get('results', '')}"),
        _paragraph(f"Production Takeaway: {paper.get('takeaway', '')}"),
    ]
    return _toggle(paper["title"], children)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _page_title(date_str: str) -> str:
    return f"arXiv Digest — {date_str}"


def _find_existing_page(token: str, database_id: str, title: str) -> Optional[str]:
    """Return the page ID of an existing page with the given title, or None."""
    response = _post(token, f"databases/{database_id}/query", body={
        "filter": {
            "property": "Name",
            "title": {"equals": title},
        }
    })
    results = response.get("results", [])
    return results[0]["id"] if results else None


def _build_properties(
    date_str: str,
    total_fetched: int,
    total_passed: int,
    top_score: int,
) -> dict:
    status = "Complete" if total_passed > 0 else "Empty"
    return {
        "Name": {"title": _rich_text(_page_title(date_str))},
        "Run Date": {"date": {"start": date_str}},
        "Papers Fetched": {"number": total_fetched},
        "Papers Passed": {"number": total_passed},
        "Top Score": {"number": top_score},
        "Status": {"select": {"name": status}},
    }


def _build_body_blocks(date_str: str, papers: list, total_fetched: int) -> list:
    blocks = [
        _heading_1(f"Daily arXiv Digest — {date_str}"),
        _callout(f"{total_fetched} papers fetched → {len(papers)} passed the 7/10 threshold"),
    ]
    for paper in papers:
        blocks.append(_paper_toggle(paper))
    return blocks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def push_to_notion(
    papers: list,
    total_fetched: Optional[int] = None,
) -> str:
    """Create or update a Notion page for today's digest run.

    Returns the URL of the created or updated Notion page.
    """
    token = os.environ["NOTION_TOKEN"]
    database_id = os.environ["NOTION_DATABASE_ID"]

    if total_fetched is None:
        total_fetched = len(papers)

    top_score = max((p.get("score", 0) for p in papers), default=0)
    date_str = _today_iso()
    properties = _build_properties(date_str, total_fetched, len(papers), top_score)
    body_blocks = _build_body_blocks(date_str, papers, total_fetched)
    title = _page_title(date_str)

    existing_id = _find_existing_page(token, database_id, title)

    if existing_id:
        logger.info("Updating existing Notion page %s", existing_id)
        _patch(token, f"pages/{existing_id}", body={"properties": properties})
        existing_blocks = _get(token, f"blocks/{existing_id}/children").get("results", [])
        for block in existing_blocks:
            _delete(token, f"blocks/{block['id']}")
        _patch(token, f"blocks/{existing_id}/children", body={"children": body_blocks})
        page = _get(token, f"pages/{existing_id}")
    else:
        logger.info("Creating new Notion page for %s", date_str)
        page = _post(token, "pages", body={
            "parent": {"database_id": database_id},
            "properties": properties,
            "children": body_blocks,
        })

    page_url = page.get("url", "")
    logger.info("Notion page ready: %s", page_url)
    return page_url


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

_SAMPLE_PAPERS = [
    {
        "id": "2401.00001",
        "title": "Efficient RAG with Hierarchical Retrieval",
        "authors": "Alice Smith, Bob Lee, Carol Wang et al.",
        "abstract": "We propose a two-stage retrieval method…",
        "pdf_url": "https://arxiv.org/pdf/2401.00001",
        "published": "2024-01-01",
        "category": "cs.IR",
        "score": 9,
        "cluster": "RAG",
        "problem": "Dense retrieval at scale is slow and memory-intensive.",
        "approach": "Hierarchical index with coarse-to-fine retrieval stages.",
        "results": "3× faster than baseline on BEIR; +2 NDCG on NQ.",
        "takeaway": "Drop-in replacement for single-stage FAISS retrieval in prod.",
    },
    {
        "id": "2401.00002",
        "title": "Cold-Start Recommendations via LLM Feature Synthesis",
        "authors": "Dan Kim",
        "abstract": "LLMs can generate pseudo-interaction signals…",
        "pdf_url": "https://arxiv.org/pdf/2401.00002",
        "published": "2024-01-01",
        "category": "cs.LG",
        "score": 8,
        "cluster": "Recommendation",
        "problem": "Cold-start users have no interaction history.",
        "approach": "GPT-4 synthesizes virtual interactions from user profiles.",
        "results": "Hit@10 improves 12% vs. content-based baseline.",
        "takeaway": "Viable for new-user onboarding when interaction data is sparse.",
    },
]

if __name__ == "__main__":
    url = push_to_notion(_SAMPLE_PAPERS, total_fetched=42)
    print(f"\nNotion page: {url}")
