"""Scores and summarizes papers for a developer learning AI and building AI products."""

import json
import logging
import os
from collections import defaultdict
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
You are a research curator for a web developer who is learning AI and wants to \
build AI-powered web applications and products. They have strong JS/frontend/backend \
skills but are new to ML research. Your job is to score and summarize arXiv papers \
so they can find the most useful and accessible work quickly.

Score each paper across four criteria. The total score is the sum (max 10).

BUILDER RELEVANCE (0-3):
  3 = you could start building something with this this weekend
  2 = useful within months with some learning
  1 = useful eventually but requires deep ML background
  0 = purely theoretical, no clear application path

UNDERSTANDABILITY (0-3):
  3 = a developer new to AI can follow the core idea
  2 = requires some ML basics but approachable
  1 = requires significant ML background
  0 = requires PhD-level specialisation

REAL WORLD GROUNDING (0-2):
  2 = tested on real-world problems with clear use cases
  1 = somewhat realistic but still mostly academic
  0 = toy datasets or purely synthetic evaluation

NOVELTY AND TIMING (0-2):
  2 = genuinely new approach or surprising finding
  1 = incremental improvement on known technique
  0 = replication or minor variation of existing work

Respond with a JSON array only. No preamble, no markdown fences, no commentary.
Each element must match this exact schema:
{
  "id": "<arXiv ID string>",
  "score": <integer 1-10, sum of the four criteria>,
  "breakdown": {
    "builder_relevance": <0-3>,
    "understandability": <0-3>,
    "real_world_grounding": <0-2>,
    "novelty_timing": <0-2>
  },
  "cluster": "<one of: Building with LLMs | AI Agents | Search and Retrieval | AI in Products | Multimodal AI | Foundational Concepts | Tools and Frameworks>",
  "problem": "<2 sentences — what problem this paper solves, explained simply>",
  "approach": "<2 sentences — what they did, avoiding jargon where possible>",
  "results": "<2 sentences — what they found, focusing on practical meaning of numbers>",
  "builder_takeaway": "<1 sentence — the single most useful thing a developer building AI apps can take from this>",
  "learning_path": "<1 sentence — what concept the reader should understand first, e.g. \\"Understand how vector embeddings work before diving in\\" or \\"No prerequisites — start here\\">"
}
"""


def _build_user_prompt(papers: list) -> str:
    lines = ["Score and summarize each of the following papers.\n"]
    for i, p in enumerate(papers, 1):
        lines.append(f"[{i}] ID: {p['id']}")
        lines.append(f"Title: {p['title']}")
        lines.append(f"Abstract: {p['abstract']}\n")
    return "\n".join(lines)


def _parse_response(raw: str) -> list:
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


def _call_openai(papers: list) -> list:
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


def _format_digest(papers: list, total_fetched: int = 0) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    passed = len(papers)

    if not papers:
        return (
            f"# arXiv Digest — {date_str}\n"
            f"Papers fetched: {total_fetched} | Papers passed (7+): 0\n\n"
            f"_(No papers scored 7 or higher today.)_\n"
        )

    # Build cluster summary
    cluster_counts: dict = defaultdict(int)
    for p in papers:
        cluster_counts[p.get("cluster", "Other")] += 1

    cluster_lines = "\n".join(
        f"- {cluster} ({count})"
        for cluster, count in sorted(cluster_counts.items(), key=lambda x: -x[1])
    )

    header = (
        f"# arXiv Digest — {date_str}\n"
        f"Papers fetched: {total_fetched} | Papers passed (7+): {passed}\n\n"
        f"## Today by cluster\n"
        f"{cluster_lines}\n"
    )

    sections = [header]
    for p in papers:
        bd = p.get("breakdown", {})
        sections.append(
            f"\n---\n"
            f"**{p['title']}**\n"
            f"arXiv: {p['id']} | Score: {p['score']}/10 | Cluster: {p.get('cluster', '?')}\n"
            f"Builder: {bd.get('builder_relevance', '?')}/3 | "
            f"Clarity: {bd.get('understandability', '?')}/3 | "
            f"Real-world: {bd.get('real_world_grounding', '?')}/2 | "
            f"Novel: {bd.get('novelty_timing', '?')}/2\n"
            f"\n"
            f"-> Problem: {p.get('problem', '')}\n"
            f"-> Approach: {p.get('approach', '')}\n"
            f"-> Results: {p.get('results', '')}\n"
            f"-> Builder Takeaway: {p.get('builder_takeaway', '')}\n"
            f"-> Before reading: {p.get('learning_path', '')}\n"
            f"-> PDF: {p.get('pdf_url', '')}\n"
        )

    return "\n".join(sections)


def _save_digest(digest_text: str) -> Path:
    RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    out_path = RAW_OUTPUT_DIR / f"digest_{date_str}.md"
    out_path.write_text(digest_text, encoding="utf-8")
    logger.info("Digest saved to %s", out_path)
    return out_path


def rank_papers(papers: list) -> list:
    """Score, filter (≥7), and summarize papers via a single GPT-4o-mini call.

    Returns paper dicts with summary fields merged in, sorted by score descending.
    Also writes a markdown digest to daily_papers/digest_YYYY_MM_DD.md.
    """
    total_fetched = len(papers)

    if not papers:
        logger.warning("rank_papers received an empty list — writing empty digest.")
        _save_digest(_format_digest([], total_fetched=0))
        return []

    scored = _call_openai(papers)

    originals = {p["id"]: p for p in papers}

    merged = []
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
    logger.info("%d / %d papers passed score threshold (%d).", len(merged), total_fetched, MIN_SCORE)

    if not merged:
        logger.warning("Zero papers passed the score filter (threshold=%d).", MIN_SCORE)

    digest_text = _format_digest(merged, total_fetched=total_fetched)
    _save_digest(digest_text)
    print(digest_text)

    return merged


if __name__ == "__main__":
    from src.fetcher import fetch_papers

    papers = fetch_papers()
    ranked = rank_papers(papers)
    print(f"\nDone — {len(ranked)} papers in today's digest.")
