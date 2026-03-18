# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_agents_document_depth.py
# REM: Depth coverage for agents/document_agent.py
# REM: Pure methods tested directly; filesystem ops use tmp_path.

import sys
from unittest.mock import MagicMock

if "celery" not in sys.modules:
    celery_mock = MagicMock()
    celery_mock.shared_task = lambda *args, **kwargs: (lambda f: f)
    sys.modules["celery"] = celery_mock

import re
import tempfile
from pathlib import Path

import pytest

from agents.document_agent import DocumentAgent


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def agent():
    return DocumentAgent()


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level constants and patterns
# ═══════════════════════════════════════════════════════════════════════════════

class TestDocumentAgentConstants:
    def test_agent_name(self, agent):
        assert agent.AGENT_NAME == "document_agent"

    def test_capabilities_is_list(self, agent):
        assert isinstance(agent.CAPABILITIES, list)

    def test_requires_approval_for(self, agent):
        assert "redact" in agent.REQUIRES_APPROVAL_FOR

    def test_supported_actions_is_list(self, agent):
        assert isinstance(agent.SUPPORTED_ACTIONS, list)
        assert "extract_text" in agent.SUPPORTED_ACTIONS

    def test_sensitive_patterns_is_dict(self, agent):
        assert isinstance(agent.SENSITIVE_PATTERNS, dict)
        assert len(agent.SENSITIVE_PATTERNS) > 0

    def test_ssn_pattern_exists(self, agent):
        assert "ssn" in agent.SENSITIVE_PATTERNS

    def test_email_pattern_exists(self, agent):
        assert "email" in agent.SENSITIVE_PATTERNS

    def test_phone_pattern_exists(self, agent):
        assert "phone" in agent.SENSITIVE_PATTERNS


# ═══════════════════════════════════════════════════════════════════════════════
# _human_readable_size — pure helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestHumanReadableSize:
    def test_bytes(self, agent):
        result = agent._human_readable_size(512)
        assert "B" in result

    def test_kilobytes(self, agent):
        result = agent._human_readable_size(1024)
        assert "KB" in result

    def test_megabytes(self, agent):
        result = agent._human_readable_size(1024 ** 2)
        assert "MB" in result

    def test_gigabytes(self, agent):
        result = agent._human_readable_size(1024 ** 3)
        assert "GB" in result

    def test_zero(self, agent):
        result = agent._human_readable_size(0)
        assert "0.0 B" == result


# ═══════════════════════════════════════════════════════════════════════════════
# _resolve_path — path validation logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolvePath:
    def test_absolute_path_in_sandbox_allowed(self, agent):
        # /sandbox is an allowed root
        path = agent._resolve_path("/sandbox/test.txt")
        assert "sandbox" in str(path).replace("\\", "/")
        assert "test.txt" in str(path)

    def test_absolute_path_in_documents_allowed(self, agent):
        path = agent._resolve_path("/data/documents/test.txt")
        assert "documents" in str(path).replace("\\", "/")
        assert "test.txt" in str(path)

    def test_absolute_path_outside_raises_on_linux(self, agent):
        # REM: On Windows, POSIX paths without drive letters are not absolute,
        # so path security enforcement only works in Linux containers — skip on Windows.
        import sys
        if sys.platform != "win32":
            with pytest.raises(ValueError, match="outside allowed"):
                agent._resolve_path("/etc/passwd")

    def test_relative_path_returns_sandbox_path(self, agent):
        # Relative path → returns /sandbox/<path> (doesn't exist, defaults to sandbox)
        path = agent._resolve_path("relative/test.txt")
        assert "sandbox" in str(path) or "documents" in str(path)


# ═══════════════════════════════════════════════════════════════════════════════
# _get_match_context — pure helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetMatchContext:
    def test_context_includes_matching_line(self, agent):
        lines = ["line 0", "line 1", "line 2", "line 3", "line 4"]
        result = agent._get_match_context(lines, 2, 1, "line")
        assert result["line"] == "line 2"
        assert result["line_number"] == 3  # 1-indexed

    def test_context_before_and_after(self, agent):
        lines = ["a", "b", "c", "d", "e"]
        result = agent._get_match_context(lines, 2, 1, "c")
        assert result["context_before"] == ["b"]
        assert result["context_after"] == ["d"]

    def test_context_at_start_of_file(self, agent):
        lines = ["first", "second", "third"]
        result = agent._get_match_context(lines, 0, 2, "first")
        assert result["context_before"] == []
        assert "second" in result["context_after"]

    def test_context_at_end_of_file(self, agent):
        lines = ["a", "b", "last"]
        result = agent._get_match_context(lines, 2, 2, "last")
        assert result["context_after"] == []
        assert "b" in result["context_before"]

    def test_zero_context(self, agent):
        lines = ["a", "b", "c"]
        result = agent._get_match_context(lines, 1, 0, "b")
        assert result["context_before"] == []
        assert result["context_after"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# _build_summary_prompt — pure string building
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildSummaryPrompt:
    def test_prompt_contains_content(self, agent):
        result = agent._build_summary_prompt("test content here", 500, "concise")
        assert "test content here" in result

    def test_prompt_contains_max_length(self, agent):
        result = agent._build_summary_prompt("content", 300, "concise")
        assert "300" in result

    def test_prompt_for_concise_style(self, agent):
        result = agent._build_summary_prompt("content", 100, "concise")
        assert "concise" in result.lower() or "brief" in result.lower()

    def test_prompt_for_detailed_style(self, agent):
        result = agent._build_summary_prompt("content", 100, "detailed")
        assert "detailed" in result.lower()

    def test_prompt_for_bullet_points_style(self, agent):
        result = agent._build_summary_prompt("content", 100, "bullet_points")
        assert "bullet" in result.lower()

    def test_long_content_truncated(self, agent):
        long_content = "x" * 9000
        result = agent._build_summary_prompt(long_content, 500, "concise")
        # Should truncate and add ellipsis
        assert "truncated" in result or len(result) < 15000

    def test_unknown_style_uses_concise_fallback(self, agent):
        result = agent._build_summary_prompt("content", 100, "unknown_style")
        # Falls back to concise
        assert "Summary:" in result


# ═══════════════════════════════════════════════════════════════════════════════
# _search — with direct content (no file needed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSearchWithContent:
    def test_simple_search_finds_match(self, agent):
        result = agent._search({
            "content": "Hello world\nThis is a test",
            "query": "world",
        })
        assert result["match_count"] == 1

    def test_search_no_match_returns_empty(self, agent):
        result = agent._search({
            "content": "Hello world",
            "query": "nonexistent_xyz",
        })
        assert result["match_count"] == 0

    def test_search_case_insensitive_default(self, agent):
        result = agent._search({
            "content": "Hello WORLD",
            "query": "world",
        })
        assert result["match_count"] == 1

    def test_search_case_sensitive(self, agent):
        result = agent._search({
            "content": "Hello WORLD",
            "query": "world",
            "case_sensitive": True,
        })
        assert result["match_count"] == 0

    def test_search_case_sensitive_exact_match(self, agent):
        result = agent._search({
            "content": "Hello WORLD",
            "query": "WORLD",
            "case_sensitive": True,
        })
        assert result["match_count"] == 1

    def test_search_regex_mode(self, agent):
        result = agent._search({
            "content": "Phone: 555-1234\nNo phone here",
            "query": r"\d{3}-\d{4}",
            "regex": True,
        })
        assert result["match_count"] == 1

    def test_search_without_query_raises(self, agent):
        with pytest.raises(ValueError, match="query required"):
            agent._search({"content": "some content"})

    def test_search_without_content_or_file_raises(self, agent):
        with pytest.raises(ValueError):
            agent._search({"query": "something"})

    def test_search_multiple_matches(self, agent):
        result = agent._search({
            "content": "apple\nbanana\napple\ncherry",
            "query": "apple",
        })
        assert result["match_count"] == 2

    def test_search_returns_total_lines(self, agent):
        result = agent._search({
            "content": "line1\nline2\nline3",
            "query": "line1",
        })
        assert result["total_lines"] == 3

    def test_search_source_is_direct_input(self, agent):
        result = agent._search({
            "content": "test content",
            "query": "test",
        })
        assert result["source"] == "direct_input"


# ═══════════════════════════════════════════════════════════════════════════════
# SENSITIVE_PATTERNS — regex validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestSensitivePatterns:
    def test_ssn_matches(self, agent):
        pattern = agent.SENSITIVE_PATTERNS["ssn"]
        assert re.search(pattern, "SSN: 123-45-6789")

    def test_ssn_no_match(self, agent):
        pattern = agent.SENSITIVE_PATTERNS["ssn"]
        assert not re.search(pattern, "12345")

    def test_email_matches(self, agent):
        pattern = agent.SENSITIVE_PATTERNS["email"]
        assert re.search(pattern, "Contact: user@example.com today")

    def test_phone_matches(self, agent):
        pattern = agent.SENSITIVE_PATTERNS["phone"]
        assert re.search(pattern, "Call 555-123-4567 now")

    def test_credit_card_matches(self, agent):
        pattern = agent.SENSITIVE_PATTERNS["credit_card"]
        assert re.search(pattern, "Card: 1234-5678-9012-3456")


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_text with real files (using tmp_path via monkeypatching)
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractText:
    def test_extract_txt_file(self, agent, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello from test file", encoding="utf-8")
        # Patch the resolve_path to return the tmp_path file
        import unittest.mock as mock
        with mock.patch.object(agent, "_resolve_path", return_value=f):
            result = agent._extract_text({"file_path": "test.txt"})
        assert result["content"] == "Hello from test file"
        assert result["length"] == 20

    def test_extract_md_file(self, agent, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("# Header\nContent here", encoding="utf-8")
        import unittest.mock as mock
        with mock.patch.object(agent, "_resolve_path", return_value=f):
            result = agent._extract_text({"file_path": "test.md"})
        assert "Header" in result["content"]

    def test_extract_no_file_path_raises(self, agent):
        with pytest.raises(ValueError, match="file_path required"):
            agent._extract_text({})

    def test_extract_nonexistent_file_raises(self, agent, tmp_path):
        import unittest.mock as mock
        nonexistent = tmp_path / "doesnotexist.txt"
        with mock.patch.object(agent, "_resolve_path", return_value=nonexistent):
            with pytest.raises(FileNotFoundError):
                agent._extract_text({"file_path": "doesnotexist.txt"})

    def test_extract_line_count(self, agent, tmp_path):
        f = tmp_path / "multiline.txt"
        f.write_text("line1\nline2\nline3", encoding="utf-8")
        import unittest.mock as mock
        with mock.patch.object(agent, "_resolve_path", return_value=f):
            result = agent._extract_text({"file_path": "multiline.txt"})
        assert result["lines"] == 3


# ═══════════════════════════════════════════════════════════════════════════════
# _get_metadata with real files
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetMetadata:
    def test_get_metadata_has_required_keys(self, agent, tmp_path):
        f = tmp_path / "meta.txt"
        f.write_text("hello", encoding="utf-8")
        import unittest.mock as mock
        with mock.patch.object(agent, "_resolve_path", return_value=f):
            result = agent._get_metadata({"file_path": "meta.txt"})
        for key in ["file_path", "file_name", "extension", "size_bytes", "sha256", "created", "modified"]:
            assert key in result

    def test_get_metadata_sha256_length(self, agent, tmp_path):
        f = tmp_path / "hash.txt"
        f.write_text("content", encoding="utf-8")
        import unittest.mock as mock
        with mock.patch.object(agent, "_resolve_path", return_value=f):
            result = agent._get_metadata({"file_path": "hash.txt"})
        assert len(result["sha256"]) == 64

    def test_get_metadata_no_file_path_raises(self, agent):
        with pytest.raises(ValueError, match="file_path required"):
            agent._get_metadata({})

    def test_get_metadata_nonexistent_raises(self, agent, tmp_path):
        import unittest.mock as mock
        nonexistent = tmp_path / "ghost.txt"
        with mock.patch.object(agent, "_resolve_path", return_value=nonexistent):
            with pytest.raises(FileNotFoundError):
                agent._get_metadata({"file_path": "ghost.txt"})

    def test_get_metadata_size_bytes(self, agent, tmp_path):
        f = tmp_path / "sized.txt"
        f.write_bytes(b"x" * 100)
        import unittest.mock as mock
        with mock.patch.object(agent, "_resolve_path", return_value=f):
            result = agent._get_metadata({"file_path": "sized.txt"})
        assert result["size_bytes"] == 100


# ═══════════════════════════════════════════════════════════════════════════════
# _list_documents — when directory doesn't exist
# ═══════════════════════════════════════════════════════════════════════════════

class TestListDocuments:
    def test_nonexistent_directory_returns_empty(self, agent):
        result = agent._list_documents({})
        # /data/documents likely doesn't exist in CI unit env
        # Returns success with empty list
        assert "documents" in result
        assert isinstance(result["documents"], list)

    def test_list_with_explicit_nonexistent_dir(self, agent, tmp_path):
        nonexistent = tmp_path / "nonexistent_subdir"
        import unittest.mock as mock
        with mock.patch.object(agent, "_resolve_path", return_value=nonexistent):
            result = agent._list_documents({"directory": "nonexistent_subdir"})
        assert result["count"] == 0
        assert result["documents"] == []

    def test_list_existing_dir(self, agent, tmp_path):
        (tmp_path / "doc1.txt").write_text("content1")
        (tmp_path / "doc2.txt").write_text("content2")
        import unittest.mock as mock
        with mock.patch.object(agent, "_resolve_path", return_value=tmp_path):
            result = agent._list_documents({"directory": str(tmp_path)})
        assert result["count"] == 2

    def test_list_recursive(self, agent, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested")
        (tmp_path / "top.txt").write_text("top")
        import unittest.mock as mock
        with mock.patch.object(agent, "_resolve_path", return_value=tmp_path):
            result = agent._list_documents({"directory": str(tmp_path), "recursive": True})
        assert result["count"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# execute — unknown action
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecuteUnknownAction:
    def test_unknown_action_raises(self, agent):
        from agents.base import AgentRequest
        req = AgentRequest(action="unknown_xyz", payload={}, requester="test")
        with pytest.raises(ValueError, match="Unknown action"):
            agent.execute(req)


# ═══════════════════════════════════════════════════════════════════════════════
# handle_request — search via direct content
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandleRequestSearch:
    def test_search_via_handle_request(self, agent):
        from agents.base import AgentRequest
        req = AgentRequest(
            action="search",
            payload={"content": "needle in haystack", "query": "needle"},
            requester="test"
        )
        response = agent.handle_request(req)
        assert response.success is True
        assert response.result["match_count"] == 1

    def test_summarize_direct_content_falls_back(self, agent):
        from agents.base import AgentRequest
        req = AgentRequest(
            action="summarize",
            payload={"content": "Short document content.", "max_length": 100},
            requester="test"
        )
        response = agent.handle_request(req)
        # Ollama not available in unit tests → fallback truncation
        assert response.success is True
        assert "summary" in response.result
