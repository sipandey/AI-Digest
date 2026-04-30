"""Fetches papers from arXiv for configured categories and date range."""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import arxiv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

CATEGORIES = ["cs.LG", "cs.CL", "cs.IR"]

# Each inner list is a group of synonyms; a paper matches if ANY group matches.
KEYWORD_GROUPS: list[list[str]] = [
    ["rag", "retrieval-augmented", "retrieval augmented"],
    [
        "recommendation system",
        "collaborative filtering",
        "cold-start",
        "cold start",
        "session-based",
    ],
    ["vllm", "kv cache", "quantization", "inference optimization", "llm serving"],
    ["ai agent", "agentic", "tool use", "function calling"],
    ["search ranking", "learning to rank", "neural ranking"],
]

# Flatten to a single compiled pattern for fast matching.
_all_keywords = [kw for group in KEYWORD_GROUPS for kw in group]
_KEYWORD_RE = re.compile(
    "|".join(re.escape(kw) for kw in _all_keywords),
    re.IGNORECASE,
)

RAW_OUTPUT_DIR = Path("daily_papers")


def _matches_keywords(paper: arxiv.Result) -> bool:
    haystack = f"{paper.title} {paper.summary}"
    return bool(_KEYWORD_RE.search(haystack))


def _format_authors(paper: arxiv.Result) -> str:
    names = [a.name for a in paper.authors]
    if len(names) > 3:
        return ", ".join(names[:3]) + " et al."
    return ", ".join(names)


def _arxiv_id(paper: arxiv.Result) -> str:
    # paper.entry_id is a URL like https://arxiv.org/abs/2401.12345v1
    return paper.entry_id.split("/abs/")[-1]


def _to_dict(paper: arxiv.Result) -> dict:
    paper_id = _arxiv_id(paper)
    return {
        "id": paper_id,
        "title": paper.title,
        "authors": _format_authors(paper),
        "abstract": paper.summary,
        "pdf_url": f"https://arxiv.org/pdf/{paper_id}",
        "published": paper.published.strftime("%Y-%m-%d"),
        "category": paper.primary_category,
    }


def fetch_papers(categories: list[str] = CATEGORIES, max_results: int = 100, lookback_hours: int = 48) -> list[dict]:
    """Fetch arXiv papers from the last `lookback_hours`, filtered by keyword, across all categories."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=3)

    seen_ids: set[str] = set()
    all_matched: list[dict] = []

    for cat in categories:
        query = f"cat:{cat}"
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        results = list(client.results(search))

        # Filter to last 24 h
        recent = [p for p in results if p.published >= cutoff]
        logger.info("%s: fetched %d results, %d within last 24 h", cat, len(results), len(recent))

        matched_in_cat = 0
        for paper in recent:
            pid = _arxiv_id(paper)
            if pid in seen_ids:
                continue
            if _matches_keywords(paper):
                seen_ids.add(pid)
                all_matched.append(_to_dict(paper))
                matched_in_cat += 1

        logger.info("%s: %d papers passed keyword filter", cat, matched_in_cat)

    logger.info("Total unique papers after deduplication: %d", len(all_matched))
    _save_raw(all_matched)
    return all_matched


def _save_raw(papers: list[dict]) -> None:
    RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    out_path = RAW_OUTPUT_DIR / f"raw_{date_str}.json"
    out_path.write_text(json.dumps(papers, indent=2, ensure_ascii=False))
    logger.info("Saved %d papers to %s", len(papers), out_path)


if __name__ == "__main__":
    papers = fetch_papers()
    print(f"\nDone — {len(papers)} papers fetched and saved.")
