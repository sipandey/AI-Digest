"""Ranks and summarizes fetched papers via a single batched GPT-4o-mini call."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

RAW_OUTPUT_DIR = Path("daily_papers")
MIN_SCORE = 7
MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """\
You are a research analyst for a senior ML engineer who builds production \
recommendation systems and RAG pipelines. Your job is to score and summarize \
arXiv papers so they can triage the most relevant work quickly.

Score each paper from 1–10 using these criteria:
- Direct applicability to production (not just theoretical)
- Novelty of the approach
- Quality of evaluation (real benchmarks, not toy datasets)
- Practical takeaway potential

Respond with a JSON array only. No preamble, no markdown fences, no commentary.
Each element must match this exact schema:
{
  "id": "<arXiv ID string>",
  "score": <integer 1–10>,
  "cluster": "<one of: RAG | Recommendation | LLM Serving | AI Agents | Search & Ranking | Other>",
  "problem": "<2 sentences describing the problem addressed>",
  "approach": "<2 sentences describing the method or approach>",
  "results": "<2 sentences describing key results or benchmarks>",
  "takeaway": "<1 sentence production takeaway>"
}
"""


def _build_user_prompt(papers: list[dict]) -> str:
    lines = ["Score and summarize each of the following papers.\n"]
    for i, p in enumerate(papers, 1):
        lines.append(f"[{i}] ID: {p['id']}")
        lines.append(f"Title: {p['title']}")
        lines.append(f"Abstract: {p['abstract']}\n")
    return "\n".join(lines)


def _parse_response(raw: str) -> list[dict]:
    """Parse and validate the raw JSON string returned by the model."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Malformed JSON from OpenAI:\n%s", raw)
        raise ValueError("OpenAI returned malformed JSON") from exc

    # json_object mode wraps the array in a single-key dict; unwrap if needed.
    if isinstance(parsed, dict):
        candidates = list(parsed.values())
        if len(candidates) == 1 and isinstance(candidates[0], list):
            parsed = candidates[0]
        else:
            logger.error("Unexpected JSON structure from OpenAI:\n%s", raw)
            raise ValueError("OpenAI returned an unexpected JSON structure")

    if not isinstance(parsed, list):
        logger.error("Expected a JSON array, got: %s\n%s", type(parsed).__name__, raw)
        raise ValueError("OpenAI response was not a JSON array")

    return parsed


def _call_openai(papers: list[dict]) -> list[dict]:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    user_prompt = _build_user_prompt(papers)

    logger.info("Sending %d papers to %s for scoring…", len(papers), MODEL)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    logger.info(
        "OpenAI call complete. Tokens used: %d prompt / %d completion",
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
    )
    return _parse_response(raw)


def _format_digest(papers: list[dict]) -> str:
    if not papers:
        return "(No papers scored ≥ 7 today.)\n"
    sections = []
    for p in papers:
        sections.append(
            f"---\n"
            f"**{p['title']}**\n"
            f"arXiv: {p['id']} | Score: {p['score']}/10 | Cluster: {p['cluster']}\n"
            f"\n"
            f"-> Problem: {p['problem']}\n"
            f"-> Approach: {p['approach']}\n"
            f"-> Results: {p['results']}\n"
            f"-> Production Takeaway: {p['takeaway']}\n"
            f"-> PDF: {p['pdf_url']}\n"
        )
    return "\n".join(sections)


def _save_digest(digest_text: str) -> Path:
    RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    out_path = RAW_OUTPUT_DIR / f"digest_{date_str}.md"
    out_path.write_text(digest_text, encoding="utf-8")
    logger.info("Digest saved to %s", out_path)
    return out_path


def rank_papers(papers: list[dict]) -> list[dict]:
    """Score, filter (≥7), and summarize papers via a single GPT-4o-mini call.

    Returns paper dicts with summary fields merged in, sorted by score descending.
    Also writes a markdown digest to daily_papers/digest_YYYY_MM_DD.md.
    """
    if not papers:
        logger.warning("rank_papers received an empty list — writing empty digest.")
        _save_digest("(No papers to rank today.)\n")
        return []

    scored = _call_openai(papers)

    # Index original papers by arXiv ID for fast lookup during merge.
    originals = {p["id"]: p for p in papers}

    merged: list[dict] = []
    for entry in scored:
        pid = entry.get("id", "")
        if pid not in originals:
            logger.warning("Scored entry has unknown arXiv ID %r — skipping.", pid)
            continue
        score = entry.get("score", 0)
        if score < MIN_SCORE:
            continue
        merged.append({**originals[pid], **entry})

    merged.sort(key=lambda p: p["score"], reverse=True)
    logger.info("%d / %d papers passed score threshold (%d).", len(merged), len(papers), MIN_SCORE)

    if not merged:
        logger.warning("Zero papers passed the score filter (threshold=%d).", MIN_SCORE)

    digest_text = _format_digest(merged)
    _save_digest(digest_text)
    print(digest_text)

    return merged


if __name__ == "__main__":
    from src.fetcher import fetch_papers

    papers = fetch_papers()
    ranked = rank_papers(papers)
    print(f"\nDone — {len(ranked)} papers in today's digest.")
