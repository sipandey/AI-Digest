"""Orchestrates the full daily digest pipeline."""

import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

LOGS_DIR = Path("logs")


# ---------------------------------------------------------------------------
# Run-log writer
# ---------------------------------------------------------------------------

def _write_run_log(
    date_str: str,
    fetched_count: int,
    passed_count: int,
    top_paper: Optional[dict],
    notion_url: str,
    errors: list[str],
) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"run_{date_str.replace('-', '_')}.log"

    lines = [
        f"timestamp       : {datetime.now(timezone.utc).isoformat()}",
        f"papers_fetched  : {fetched_count}",
        f"papers_passed   : {passed_count}",
    ]

    if top_paper:
        lines.append(
            f"top_paper       : \"{top_paper['title']}\" (score {top_paper.get('score', '?')}/10)"
        )
    else:
        lines.append("top_paper       : —")

    lines.append(f"notion_url      : {notion_url or '—'}")

    if errors:
        lines.append("errors          :")
        for err in errors:
            lines.append(f"  - {err}")
    else:
        lines.append("errors          : none")

    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Run log written to %s", log_path)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run() -> None:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    errors: list[str] = []
    fetched_count = 0
    passed_count = 0
    notion_url = ""
    top_paper: Optional[dict] = None

    # ------------------------------------------------------------------
    # Stage 1: Fetch
    # ------------------------------------------------------------------
    try:
        from src.fetcher import fetch_papers
        raw_papers = fetch_papers()
        fetched_count = len(raw_papers)
        logger.info("Fetcher complete: %d papers", fetched_count)
    except Exception:
        msg = traceback.format_exc().strip()
        logger.error("Fetcher failed:\n%s", msg)
        errors.append(f"fetcher: {msg}")
        _write_run_log(date_str, 0, 0, None, "", errors)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Stage 2: Empty-run short-circuit
    # ------------------------------------------------------------------
    if not raw_papers:
        logger.info("No papers matched today — pushing empty Notion page.")
        try:
            from src.notion_client import push_to_notion
            notion_url = push_to_notion([], total_fetched=0)
        except Exception:
            msg = traceback.format_exc().strip()
            logger.warning("Notion push failed (non-fatal):\n%s", msg)
            errors.append(f"notion (empty run): {msg}")

        _write_run_log(date_str, 0, 0, None, notion_url, errors)
        print(f"Run complete: 0 papers fetched, 0 passed, Notion page: {notion_url}")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Stage 3: Rank
    # ------------------------------------------------------------------
    try:
        from src.ranker import rank_papers
        scored_papers = rank_papers(raw_papers)
        passed_count = len(scored_papers)
        top_paper = scored_papers[0] if scored_papers else None
        logger.info("Ranker complete: %d / %d papers passed threshold", passed_count, fetched_count)
    except Exception:
        msg = traceback.format_exc().strip()
        logger.error("Ranker failed:\n%s", msg)
        errors.append(f"ranker: {msg}")
        _write_run_log(date_str, fetched_count, 0, None, "", errors)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Stage 4: Notion
    # ------------------------------------------------------------------
    try:
        from src.notion_client import push_to_notion
        notion_url = push_to_notion(scored_papers, total_fetched=fetched_count)
        logger.info("Notion push complete: %s", notion_url)
    except Exception:
        msg = traceback.format_exc().strip()
        logger.warning(
            "Notion push failed (non-fatal — digest saved locally):\n%s", msg
        )
        errors.append(f"notion: {msg}")

    # ------------------------------------------------------------------
    # Stage 5: Run log + summary
    # ------------------------------------------------------------------
    _write_run_log(date_str, fetched_count, passed_count, top_paper, notion_url, errors)

    print(
        f"Run complete: {fetched_count} papers fetched, {passed_count} passed, "
        f"Notion page: {notion_url or '(unavailable)'}"
    )
    sys.exit(0)


if __name__ == "__main__":
    run()
