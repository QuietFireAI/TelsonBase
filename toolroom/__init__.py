# TelsonBase/toolroom/__init__.py
# REM: =======================================================================================
# REM: TOOLROOM - CENTRALIZED TOOL MANAGEMENT FOR TELSONBASE AGENTS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: The Toolroom is the single source of truth for all tools
# REM: available to agents on base. No agent accesses external tools directly. Every
# REM: tool request flows through the Foreman, who manages authentication, usage
# REM: tracking, updates, and HITL gates for any operation requiring API access.
# REM:
# REM: Architecture:
# REM:   toolroom/
# REM:     ├── __init__.py         ← This file (package exports)
# REM:     ├── foreman.py          ← The Foreman agent (supervisor-level)
# REM:     ├── registry.py         ← Tool registry, metadata, and checkout system
# REM:     ├── manifest.py         ← Tool manifest schema and validation (v4.6.0CC)
# REM:     ├── executor.py         ← Tool execution engine (v4.6.0CC)
# REM:     ├── function_tools.py   ← Function tool decorator registry (v4.6.0CC)
# REM:     ├── TOOLROOM.md         ← Documentation
# REM:     └── tools/              ← Actual tool packages live here
# REM:         ├── __init__.py
# REM:         └── (uploaded tools: sql, parsers, etc.)
# REM:
# REM: Key Principles:
# REM:   1. ALL agents draw from the SAME toolroom (no shadow tooling)
# REM:   2. Foreman is the ONLY agent with GitHub access for tool updates
# REM:   3. API access requires HITL approval — no exceptions
# REM:   4. Every checkout is logged, every return is audited
# REM:   5. Every tool must have a manifest to be executable (v4.6.0CC)
# REM:   6. Function tools coexist with git-cloned tools (v4.6.0CC)
# REM: =======================================================================================

from toolroom.registry import (
    ToolRegistry,
    ToolMetadata,
    ToolCheckout,
    ToolStatus,
    tool_registry,
)

from toolroom.foreman import (
    ForemanAgent,
    FOREMAN_AGENT_ID,
)

from toolroom.manifest import (
    ToolManifest,
    SandboxLevel,
    validate_manifest,
    load_manifest_from_tool_dir,
    MANIFEST_FILENAME,
)

from toolroom.executor import (
    ExecutionResult,
    execute_subprocess_tool,
    execute_function_tool,
)

from toolroom.function_tools import (
    FunctionToolRegistry,
    function_tool_registry,
    register_function_tool,
)

__all__ = [
    "ToolRegistry",
    "ToolMetadata",
    "ToolCheckout",
    "ToolStatus",
    "tool_registry",
    "ForemanAgent",
    "FOREMAN_AGENT_ID",
    "ToolManifest",
    "SandboxLevel",
    "validate_manifest",
    "load_manifest_from_tool_dir",
    "MANIFEST_FILENAME",
    "ExecutionResult",
    "execute_subprocess_tool",
    "execute_function_tool",
    "FunctionToolRegistry",
    "function_tool_registry",
    "register_function_tool",
]
