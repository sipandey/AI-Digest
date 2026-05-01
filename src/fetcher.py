"""Fetches arXiv papers relevant to learning AI and building AI-powered products."""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import arxiv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

CATEGORIES = ["cs.LG", "cs.CL", "cs.IR", "cs.AI", "cs.HC"]

# Each group is a (name, keywords) pair.
# A paper passes if its title+abstract matches ANY keyword from ANY group.
KEYWORD_GROUPS: list[tuple[str, list[str]]] = [
    ("Building with LLMs", [
        "rag", "retrieval augmented", "retrieval-augmented",
        "llm application", "llm integration", "prompt engineering",
        "prompt tuning", "in-context learning", "few-shot",
        "chain of thought", "function calling", "tool use",
        "structured output", "llm evaluation", "hallucination",
        "grounding", "context window",
    ]),
    ("AI Agents and Automation", [
        "ai agent", "agentic", "autonomous agent", "multi-agent",
        "workflow automation", "task planning", "tool calling",
        "code generation", "code assistant", "copilot",
    ]),
    ("Practical AI Systems", [
        "recommendation system", "personalization",
        "search ranking", "semantic search", "vector database",
        "embedding", "similarity search", "knowledge graph",
        "question answering", "document understanding",
        "information extraction",
    ]),
    ("AI Product and UX", [
        "human-ai interaction", "ai interface", "ai assistant",
        "chatbot", "conversational ai", "user study",
        "ai evaluation", "ai safety", "ai alignment",
        "explainability", "interpretability",
    ]),
    ("Multimodal and Emerging", [
        "multimodal", "vision language", "image text",
        "text to image", "speech recognition", "audio",
        "video understanding", "document ai",
    ]),
]

# Pre-compile one regex per group for fast per-paper matching.
_GROUP_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        name,
        re.compile("|".join(re.escape(kw) for kw in keywords), re.IGNORECASE),
    )
    for name, keywords in KEYWORD_GROUPS
]

RAW_OUTPUT_DIR = Path("daily_papers")


def _matched_group(paper: arxiv.Result) -> Optional[str]:
    """Return the name of the first keyword group that matches, or None."""
    haystack = f"{paper.title} {paper.summary}"
    for name, pattern in _GROUP_PATTERNS:
        if pattern.search(haystack):
            return name
    return None


def _format_authors(paper: arxiv.Result) -> str:
    names = [a.name for a in paper.authors]
    if len(names) > 3:
        return ", ".join(names[:3]) + " et al."
    return ", ".join(names)


def _arxiv_id(paper: arxiv.Result) -> str:
    # entry_id is a URL like https://arxiv.org/abs/2401.12345v1
    return paper.entry_id.split("/abs/")[-1]


def _to_dict(paper: arxiv.Result, matched_group: str) -> dict:
    paper_id = _arxiv_id(paper)
    return {
        "id": paper_id,
        "title": paper.title,
        "authors": _format_authors(paper),
        "abstract": paper.summary,
        "pdf_url": f"https://arxiv.org/pdf/{paper_id}",
        "published": paper.published.strftime("%Y-%m-%d"),
        "category": paper.primary_category,
        "matched_group": matched_group,
    }


def fetch_papers(
    categories: list[str] = CATEGORIES,
    max_results: int = 150,
    lookback_hours: int = 48,
) -> list[dict]:
    """Fetch arXiv papers from the last `lookback_hours`, filtered by keyword group."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=3)

    seen_ids: set[str] = set()
    all_matched: list[dict] = []
    group_counts: dict[str, int] = {name: 0 for name, _ in KEYWORD_GROUPS}

    for cat in categories:
        search = arxiv.Search(
            query=f"cat:{cat}",
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        results = list(client.results(search))
        recent = [p for p in results if p.published >= cutoff]
        logger.info("%s: fetched %d results, %d within lookback window", cat, len(results), len(recent))

        matched_in_cat = 0
        for paper in recent:
            pid = _arxiv_id(paper)
            if pid in seen_ids:
                continue
            group = _matched_group(paper)
            if group:
                seen_ids.add(pid)
                all_matched.append(_to_dict(paper, group))
                group_counts[group] += 1
                matched_in_cat += 1

        logger.info("%s: %d papers passed keyword filter", cat, matched_in_cat)

    logger.info("Total unique papers after deduplication: %d", len(all_matched))
    for group_name, count in group_counts.items():
        if count:
            logger.info("  %-30s %d papers", group_name, count)

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
