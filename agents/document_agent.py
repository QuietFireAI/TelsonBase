# TelsonBase/agents/document_agent.py
# REM: =======================================================================================
# REM: DOCUMENT PROCESSOR AGENT FOR TELSONBASE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: A production-ready agent for document processing tasks.
# REM: Designed for legal and healthcare use cases where document handling requires
# REM: audit trails, access control, and secure processing.
# REM:
# REM: Capabilities:
# REM:   - Extract text from documents (PDF, DOCX, TXT)
# REM:   - Summarize document content using local Ollama
# REM:   - Search documents for specific terms
# REM:   - Redact sensitive information
# REM:   - Generate document metadata
# REM:
# REM: QMS Protocol:
# REM:   Document_Extract_Please → Document_Extract_Thank_You
# REM:   Document_Summarize_Please → Document_Summarize_Thank_You
# REM:   Document_Search_Please → Document_Search_Thank_You
# REM:   Document_Redact_Please (requires approval) → Document_Redact_Thank_You
# REM: =======================================================================================

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.base import AgentRequest, AgentResponse, SecureBaseAgent
from core.audit import AuditEventType, audit
from core.config import get_settings
from core.qms import QMSStatus, format_qms

settings = get_settings()
logger = logging.getLogger(__name__)


class DocumentAgent(SecureBaseAgent):
    """
    REM: Secure document processing agent.
    REM: Handles extraction, summarization, search, and redaction.
    """
    
    AGENT_NAME = "document_agent"
    
    CAPABILITIES = [
        "filesystem.read:/data/documents/*",
        "filesystem.write:/data/documents/processed/*",
        "filesystem.read:/sandbox/*",
        "filesystem.write:/sandbox/*",
        "external.none",  # No external network access
    ]
    
    # REM: Redaction requires human approval due to data modification
    REQUIRES_APPROVAL_FOR = ["redact", "delete"]
    
    # REM: Supported actions
    SUPPORTED_ACTIONS = [
        "extract_text",
        "summarize",
        "search",
        "redact",
        "get_metadata",
        "list_documents",
    ]
    
    # REM: Patterns for common sensitive data (for redaction)
    SENSITIVE_PATTERNS = {
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "date_of_birth": r"\b(0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])[-/](19|20)\d{2}\b",
    }
    
    def __init__(self):
        super().__init__()
        self._documents_path = Path("/data/documents")
        self._processed_path = Path("/data/documents/processed")
        self._sandbox_path = Path("/sandbox")
    
    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        """
        REM: Execute document processing action.
        REM: Called by SecureBaseAgent.handle_request() after security checks pass.
        """
        action = request.action.lower()
        payload = request.payload

        if action == "extract_text":
            result = self._extract_text(payload)
        elif action == "summarize":
            result = self._summarize(payload)
        elif action == "search":
            result = self._search(payload)
        elif action == "redact":
            result = self._redact(payload)
        elif action == "get_metadata":
            result = self._get_metadata(payload)
        elif action == "list_documents":
            result = self._list_documents(payload)
        else:
            raise ValueError(f"Unknown action: {action}. Supported: {self.SUPPORTED_ACTIONS}")

        audit.log(
            AuditEventType.AGENT_ACTION,
            format_qms(f"Document_{action.title()}", QMSStatus.THANK_YOU,
                      request_id=request.request_id),
            actor=self.AGENT_NAME,
            details={"action": action, "payload": payload}
        )

        return result
    
    def _resolve_path(self, file_path: str) -> Path:
        """
        REM: Resolve and validate file path.
        REM: Ensures path is within allowed directories.
        """
        path = Path(file_path)
        
        # REM: If relative, check sandbox first, then documents
        if not path.is_absolute():
            sandbox_path = self._sandbox_path / path
            if sandbox_path.exists():
                return sandbox_path
            
            doc_path = self._documents_path / path
            if doc_path.exists():
                return doc_path
            
            # REM: Default to sandbox for new files
            return sandbox_path
        
        # REM: Validate absolute path is in allowed locations
        allowed_roots = [self._documents_path, self._sandbox_path, self._processed_path]
        for root in allowed_roots:
            try:
                path.relative_to(root)
                return path
            except ValueError:
                continue
        
        raise ValueError(f"Path '{file_path}' is outside allowed directories")
    
    def _extract_text(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: Extract text content from a document.
        REM: QMS: Document_Extract_Please with ::file_path::
        """
        file_path = payload.get("file_path")
        if not file_path:
            raise ValueError("file_path required")
        
        path = self._resolve_path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix == ".txt":
            content = path.read_text(encoding="utf-8", errors="replace")
        elif suffix == ".md":
            content = path.read_text(encoding="utf-8", errors="replace")
        elif suffix == ".pdf":
            content = self._extract_pdf(path)
        elif suffix == ".docx":
            content = self._extract_docx(path)
        else:
            # REM: Try to read as text
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except (IOError, OSError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read file {path}: {e}")
                raise ValueError(f"Unsupported file type: {suffix}")
        
        return {
            "file_path": str(path),
            "content": content,
            "length": len(content),
            "lines": content.count("\n") + 1,
        }
    
    def _extract_pdf(self, path: Path) -> str:
        """REM: Extract text from PDF. Falls back to placeholder if PyPDF not available."""
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            return "\n".join(text_parts)
        except ImportError:
            return f"[PDF extraction requires pypdf: {path.name}]"
    
    def _extract_docx(self, path: Path) -> str:
        """REM: Extract text from DOCX. Falls back to placeholder if docx not available."""
        try:
            import docx
            doc = docx.Document(str(path))
            return "\n".join(para.text for para in doc.paragraphs)
        except ImportError:
            return f"[DOCX extraction requires python-docx: {path.name}]"
    
    def _summarize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: Summarize document content using local Ollama.
        REM: QMS: Document_Summarize_Please with ::file_path:: or ::content::
        """
        # REM: Get content either from file or directly
        if "content" in payload:
            content = payload["content"]
            source = "direct_input"
        elif "file_path" in payload:
            extract_result = self._extract_text(payload)
            content = extract_result["content"]
            source = payload["file_path"]
        else:
            raise ValueError("Either 'content' or 'file_path' required")
        
        max_length = payload.get("max_length", 500)
        style = payload.get("style", "concise")  # concise, detailed, bullet_points
        
        # REM: Call Ollama for summarization via OllamaService (direct HTTP, no client dependency)
        try:
            from core.ollama_service import get_ollama_service
            
            prompt = self._build_summary_prompt(content, max_length, style)
            ollama_svc = get_ollama_service()
            
            result = ollama_svc.generate(
                prompt=prompt,
                model=payload.get("model"),
            )
            
            summary = result.get("response", "").strip()
            
            return {
                "source": source,
                "summary": summary,
                "style": style,
                "original_length": len(content),
                "summary_length": len(summary),
                "model_used": result.get("model", ollama_svc.default_model),
                "tokens_per_second": result.get("tokens_per_second", 0),
            }
            
        except ImportError:
            # REM: Fallback if OllamaService not available
            return {
                "source": source,
                "summary": content[:max_length] + "..." if len(content) > max_length else content,
                "style": "truncated (Ollama unavailable)",
                "original_length": len(content),
                "summary_length": min(len(content), max_length),
            }
        except Exception as e:
            logger.warning(f"Ollama summarization failed: {e}")
            return {
                "source": source,
                "summary": content[:max_length] + "..." if len(content) > max_length else content,
                "style": f"truncated (error: {e})",
                "original_length": len(content),
            }
    
    def _build_summary_prompt(self, content: str, max_length: int, style: str) -> str:
        """REM: Build prompt for Ollama summarization."""
        style_instructions = {
            "concise": "Provide a brief, concise summary.",
            "detailed": "Provide a detailed summary covering all main points.",
            "bullet_points": "Summarize as bullet points.",
        }
        
        # REM: Truncate content if too long for context window
        max_content = 8000
        if len(content) > max_content:
            content = content[:max_content] + "\n\n[Content truncated...]"
        
        return f"""Summarize the following document in approximately {max_length} characters.
{style_instructions.get(style, style_instructions['concise'])}

Document:
{content}

Summary:"""
    
    def _search(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: Search document for specific terms.
        REM: QMS: Document_Search_Please with ::file_path:: ::query::
        """
        file_path = payload.get("file_path")
        query = payload.get("query")
        case_sensitive = payload.get("case_sensitive", False)
        regex = payload.get("regex", False)
        context_lines = payload.get("context_lines", 2)
        
        if not query:
            raise ValueError("query required")
        
        # REM: Get content
        if file_path:
            extract_result = self._extract_text({"file_path": file_path})
            content = extract_result["content"]
            source = file_path
        elif "content" in payload:
            content = payload["content"]
            source = "direct_input"
        else:
            raise ValueError("Either 'file_path' or 'content' required")
        
        lines = content.split("\n")
        matches = []
        
        if regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(query, flags)
        else:
            if not case_sensitive:
                query = query.lower()
        
        for i, line in enumerate(lines):
            check_line = line if case_sensitive else line.lower()
            
            if regex:
                if pattern.search(line):
                    matches.append(self._get_match_context(lines, i, context_lines, query))
            else:
                if query in check_line:
                    matches.append(self._get_match_context(lines, i, context_lines, query))
        
        return {
            "source": source,
            "query": payload.get("query"),
            "match_count": len(matches),
            "matches": matches[:100],  # Limit to first 100 matches
            "total_lines": len(lines),
        }
    
    def _get_match_context(self, lines: List[str], index: int, context: int, query: str) -> Dict[str, Any]:
        """REM: Get match with surrounding context lines."""
        start = max(0, index - context)
        end = min(len(lines), index + context + 1)
        
        return {
            "line_number": index + 1,
            "line": lines[index],
            "context_before": lines[start:index],
            "context_after": lines[index + 1:end],
        }
    
    def _redact(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: Redact sensitive information from document.
        REM: QMS: Document_Redact_Please with ::file_path:: (REQUIRES APPROVAL)
        
        This action modifies data and requires human approval.
        """
        file_path = payload.get("file_path")
        patterns = payload.get("patterns", list(self.SENSITIVE_PATTERNS.keys()))
        replacement = payload.get("replacement", "[REDACTED]")
        output_path = payload.get("output_path")
        
        if not file_path:
            raise ValueError("file_path required")
        
        # REM: Extract content
        extract_result = self._extract_text({"file_path": file_path})
        content = extract_result["content"]
        
        redaction_counts = {}
        redacted_content = content
        
        for pattern_name in patterns:
            if pattern_name in self.SENSITIVE_PATTERNS:
                pattern = self.SENSITIVE_PATTERNS[pattern_name]
                matches = re.findall(pattern, redacted_content)
                redaction_counts[pattern_name] = len(matches)
                redacted_content = re.sub(pattern, replacement, redacted_content)
        
        # REM: Save redacted document
        if output_path:
            out_path = self._resolve_path(output_path)
        else:
            path = self._resolve_path(file_path)
            out_path = self._processed_path / f"redacted_{path.name}"
        
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(redacted_content, encoding="utf-8")
        
        total_redactions = sum(redaction_counts.values())
        
        audit.log(
            AuditEventType.SECURITY_ALERT,
            format_qms("Document_Redact", QMSStatus.THANK_YOU,
                      file=file_path, redactions=total_redactions),
            actor=self.AGENT_NAME,
            details={"redaction_counts": redaction_counts, "output_path": str(out_path)}
        )
        
        return {
            "original_path": file_path,
            "output_path": str(out_path),
            "redaction_counts": redaction_counts,
            "total_redactions": total_redactions,
            "patterns_applied": patterns,
        }
    
    def _get_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: Get document metadata.
        REM: QMS: Document_Metadata_Please with ::file_path::
        """
        file_path = payload.get("file_path")
        if not file_path:
            raise ValueError("file_path required")
        
        path = self._resolve_path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        stat = path.stat()
        
        # REM: Calculate file hash for integrity
        with open(path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        return {
            "file_path": str(path),
            "file_name": path.name,
            "extension": path.suffix,
            "size_bytes": stat.st_size,
            "size_human": self._human_readable_size(stat.st_size),
            "created": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "sha256": file_hash,
        }
    
    def _list_documents(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: List documents in allowed directories.
        REM: QMS: Document_List_Please with optional ::directory:: ::pattern::
        """
        directory = payload.get("directory", "")
        pattern = payload.get("pattern", "*")
        recursive = payload.get("recursive", False)
        
        if directory:
            base_path = self._resolve_path(directory)
        else:
            base_path = self._documents_path
        
        if not base_path.exists():
            return {"documents": [], "count": 0, "directory": str(base_path)}
        
        if recursive:
            files = list(base_path.rglob(pattern))
        else:
            files = list(base_path.glob(pattern))
        
        # REM: Filter to files only, exclude directories
        files = [f for f in files if f.is_file()]
        
        documents = []
        for f in files[:1000]:  # Limit to 1000 files
            try:
                stat = f.stat()
                documents.append({
                    "path": str(f),
                    "name": f.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                })
            except (IOError, OSError) as e:
                logger.debug(f"Could not stat file {f}: {e}")
                continue
        
        return {
            "directory": str(base_path),
            "pattern": pattern,
            "recursive": recursive,
            "count": len(documents),
            "documents": documents,
        }
    
    def _human_readable_size(self, size_bytes: int) -> str:
        """REM: Convert bytes to human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"


# REM: =======================================================================================
# REM: EXPORTS
# REM: =======================================================================================

__all__ = ["DocumentAgent"]
