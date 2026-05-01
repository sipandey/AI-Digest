"""Unit tests for the arXiv digest pipeline — zero real API calls."""

import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_paper(paper_id: str, title: str, abstract: str = "", score: int = 8) -> dict:
    return {
        "id": paper_id,
        "title": title,
        "authors": "Alice Smith",
        "abstract": abstract,
        "pdf_url": f"https://arxiv.org/pdf/{paper_id}",
        "published": "2024-01-01",
        "category": "cs.LG",
        "score": score,
        "cluster": "RAG",
        "problem": "A problem.",
        "approach": "An approach.",
        "results": "Some results.",
        "takeaway": "A takeaway.",
    }


# ---------------------------------------------------------------------------
# Test 1: fetcher keyword filter
# ---------------------------------------------------------------------------

class TestFetcherKeywordFilter(unittest.TestCase):
    def test_fetcher_keyword_filter(self):
        from src.fetcher import _GROUP_PATTERNS

        def first_match(title, abstract):
            haystack = f"{title} {abstract}"
            for name, pattern in _GROUP_PATTERNS:
                if pattern.search(haystack):
                    return name
            return None

        # 3 should match (one per group), 2 should not
        candidates = [
            ("RAG pipeline for open-domain QA", "We study retrieval-augmented generation.", "Building with LLMs"),
            ("An AI agent for workflow automation", "Agentic task planning system.", "AI Agents and Automation"),
            ("Semantic search with vector databases", "Embedding-based similarity search.", "Practical AI Systems"),
            ("Image segmentation with diffusion models", "No relevant keywords here.", None),
            ("Graph neural networks for molecule property prediction", "Unrelated content.", None),
        ]

        for title, abstract, expected_group in candidates:
            result = first_match(title, abstract)
            self.assertEqual(result, expected_group, f"Failed for: {title}")


# ---------------------------------------------------------------------------
# Test 2: ranker JSON parsing + filter
# ---------------------------------------------------------------------------

class TestRankerJsonParsing(unittest.TestCase):
    def _scored_entries(self):
        return [
            {"id": "2401.00001", "score": 8, "cluster": "RAG",
             "problem": "p", "approach": "a", "results": "r", "takeaway": "t"},
            {"id": "2401.00002", "score": 6, "cluster": "Other",
             "problem": "p", "approach": "a", "results": "r", "takeaway": "t"},
            {"id": "2401.00003", "score": 9, "cluster": "LLM Serving",
             "problem": "p", "approach": "a", "results": "r", "takeaway": "t"},
        ]

    def test_ranker_json_parsing(self):
        from src.ranker import _parse_response, rank_papers

        # json_object mode wraps the array; verify unwrapping works
        raw = json.dumps({"papers": self._scored_entries()})
        parsed = _parse_response(raw)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 3)

        # Filter (>= 7) and sort via rank_papers
        sample_papers = [
            _make_paper("2401.00001", "Paper A"),
            _make_paper("2401.00002", "Paper B"),
            _make_paper("2401.00003", "Paper C"),
        ]

        with patch("src.ranker._call_openai", return_value=parsed):
            with patch("src.ranker._save_digest"):
                with patch("builtins.print"):
                    result = rank_papers(sample_papers)

        # Score 6 is below threshold; only 8 and 9 survive
        self.assertEqual(len(result), 2)
        # Sorted descending
        self.assertEqual(result[0]["score"], 9)
        self.assertEqual(result[1]["score"], 8)


# ---------------------------------------------------------------------------
# Test 3: digest markdown formatting
# ---------------------------------------------------------------------------

class TestDigestFormatting(unittest.TestCase):
    def test_digest_formatting(self):
        from src.ranker import _format_digest

        papers = [
            _make_paper("2401.00001", "Hierarchical RAG at Scale", score=9),
            _make_paper("2401.00002", "Cold-Start via LLM Synthesis", score=7),
        ]

        digest = _format_digest(papers)

        for p in papers:
            self.assertIn(p["title"], digest)
            self.assertIn(str(p["score"]), digest)
            self.assertIn(p["cluster"], digest)
            self.assertIn(p["pdf_url"], digest)


# ---------------------------------------------------------------------------
# Test 4: Notion page properties builder
# ---------------------------------------------------------------------------

class TestNotionPageProperties(unittest.TestCase):
    def test_notion_page_properties(self):
        from src.notion_client import _build_properties

        props = _build_properties(
            date_str="2024-01-15",
            total_fetched=42,
            total_passed=5,
            top_score=9,
        )

        required_keys = {"Name", "Run Date", "Papers Fetched", "Papers Passed", "Top Score", "Status"}
        self.assertEqual(required_keys, set(props.keys()))

        self.assertEqual(props["Run Date"]["date"]["start"], "2024-01-15")
        self.assertEqual(props["Papers Fetched"]["number"], 42)
        self.assertEqual(props["Papers Passed"]["number"], 5)
        self.assertEqual(props["Top Score"]["number"], 9)
        self.assertEqual(props["Status"]["select"]["name"], "Complete")

        # Zero passed → Status should be "Empty"
        empty_props = _build_properties("2024-01-15", 0, 0, 0)
        self.assertEqual(empty_props["Status"]["select"]["name"], "Empty")


# ---------------------------------------------------------------------------
# Test 5: empty-run pipeline handling
# ---------------------------------------------------------------------------

class TestEmptyRunHandling(unittest.TestCase):
    def test_empty_run_handling(self):
        from src.notion_client import _build_properties

        notion_mock = MagicMock(return_value="https://notion.so/test-page")

        with patch("src.fetcher.fetch_papers", return_value=[]):
            with patch("src.notion_client.push_to_notion", notion_mock):
                with patch("src.pipeline._write_run_log"):
                    with patch("builtins.print"):
                        with self.assertRaises(SystemExit) as ctx:
                            from src.pipeline import run
                            run()

        # Pipeline must exit cleanly with code 0
        self.assertEqual(ctx.exception.code, 0)

        # push_to_notion must have been called with an empty list
        call_args = notion_mock.call_args
        self.assertEqual(call_args.args[0], [])
        self.assertEqual(call_args.kwargs.get("total_fetched", call_args.args[1] if len(call_args.args) > 1 else None), 0)

        # Properties builder confirms Status="Empty" for zero papers
        props = _build_properties("2024-01-15", 0, 0, 0)
        self.assertEqual(props["Status"]["select"]["name"], "Empty")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
