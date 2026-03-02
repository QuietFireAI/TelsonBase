# TelsonBase/toolroom/function_tools.py
# REM: =======================================================================================
# REM: FUNCTION TOOL REGISTRY — IN-HOUSE PYTHON TOOLS AS FIRST-CLASS CITIZENS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Not every tool needs to be a git repo cloned to disk.
# REM: For in-house tools — small, trusted Python functions written by the TelsonBase
# REM: operator — the decorator pattern is simpler, faster, and eliminates the
# REM: subprocess overhead entirely.
# REM:
# REM: Usage:
# REM:   @register_function_tool(
# REM:       name="Hash Calculator",
# REM:       category="crypto",
# REM:       description="Compute SHA-256 hash of input text",
# REM:   )
# REM:   def hash_text(text: str, algorithm: str = "sha256") -> dict:
# REM:       import hashlib
# REM:       h = hashlib.new(algorithm, text.encode()).hexdigest()
# REM:       return {"hash": h, "algorithm": algorithm}
# REM:
# REM: These tools coexist alongside git-cloned tools in the same registry.
# REM: Checkout/return tracking applies equally to both.
# REM:
# REM: v4.6.0CC: Implements Option D (tool-as-function) from architectural review.
# REM:
# REM: QMS: Register_Function_Tool_Please → Register_Function_Tool_Thank_You
# REM: =======================================================================================

import inspect
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, Optional, List, get_type_hints

from toolroom.manifest import ToolManifest, SandboxLevel

logger = logging.getLogger(__name__)


@dataclass
class FunctionToolEntry:
    """
    REM: A registered function tool. Holds the callable and its auto-generated manifest.
    """
    tool_id: str
    name: str
    func: Callable
    manifest: ToolManifest
    description: str = ""
    category: str = "utility"
    version: str = "1.0.0"
    requires_api_access: bool = False
    min_trust_level: str = "resident"


class FunctionToolRegistry:
    """
    REM: Registry of function-based tools. Separate from the main ToolRegistry
    REM: because these tools don't live on disk — they're Python callables.
    REM: The Foreman bridges both registries when an agent checks out a tool.
    REM:
    REM: Thread-safe: dictionary operations are atomic in CPython (GIL).
    """

    def __init__(self):
        self._tools: Dict[str, FunctionToolEntry] = {}

    def register(
        self,
        func: Callable,
        name: str,
        category: str = "utility",
        description: str = "",
        version: str = "1.0.0",
        requires_api_access: bool = False,
        min_trust_level: str = "resident",
        timeout_seconds: int = 300,
    ) -> FunctionToolEntry:
        """
        REM: Register a Python callable as a tool.
        REM: Auto-generates a ToolManifest from function signature inspection.
        """
        tool_id = f"func_{func.__name__}"

        # REM: Auto-generate manifest from function signature
        manifest = self._build_manifest_from_function(
            func=func,
            name=name,
            description=description or func.__doc__ or "",
            version=version,
            timeout_seconds=timeout_seconds,
        )

        entry = FunctionToolEntry(
            tool_id=tool_id,
            name=name,
            func=func,
            manifest=manifest,
            description=description or func.__doc__ or "",
            category=category,
            version=version,
            requires_api_access=requires_api_access,
            min_trust_level=min_trust_level,
        )

        self._tools[tool_id] = entry

        logger.info(
            f"REM: Register_Function_Tool_Thank_You ::{tool_id}:: "
            f"name='{name}' category={category} "
            f"params={[p['name'] for p in manifest.inputs]}"
        )

        return entry

    def get(self, tool_id: str) -> Optional[FunctionToolEntry]:
        """REM: Get a function tool by ID."""
        return self._tools.get(tool_id)

    def list_all(self) -> List[FunctionToolEntry]:
        """REM: List all registered function tools."""
        return list(self._tools.values())

    def unregister(self, tool_id: str) -> bool:
        """REM: Remove a function tool from the registry."""
        if tool_id in self._tools:
            del self._tools[tool_id]
            logger.info(f"REM: Unregister_Function_Tool_Thank_You ::{tool_id}::")
            return True
        return False

    def _build_manifest_from_function(
        self,
        func: Callable,
        name: str,
        description: str,
        version: str,
        timeout_seconds: int,
    ) -> ToolManifest:
        """
        REM: Inspect a Python function's signature and build a ToolManifest.
        REM: This is the bridge between function tools and the manifest system.
        """
        sig = inspect.signature(func)

        # REM: Try to get type hints
        try:
            hints = get_type_hints(func)
        except (TypeError, NameError, AttributeError):
            hints = {}

        # REM: Build input parameters from function signature
        inputs = []
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            param_type = "string"  # default
            hint = hints.get(param_name)
            if hint:
                type_map = {
                    str: "string",
                    int: "integer",
                    float: "float",
                    bool: "boolean",
                    dict: "json",
                    list: "json",
                }
                param_type = type_map.get(hint, "string")

            required = (param.default is inspect.Parameter.empty)
            default = None if required else param.default

            inputs.append({
                "name": param_name,
                "type": param_type,
                "required": required,
                "default": default,
            })

        return ToolManifest(
            name=name,
            entry_point=f"python::{func.__module__}.{func.__name__}",
            version=version,
            description=description,
            sandbox_level=SandboxLevel.NONE,  # In-process — no subprocess
            timeout_seconds=timeout_seconds,
            inputs=inputs,
        )


# REM: =======================================================================================
# REM: SINGLETON REGISTRY INSTANCE
# REM: =======================================================================================

function_tool_registry = FunctionToolRegistry()


# REM: =======================================================================================
# REM: DECORATOR
# REM: =======================================================================================

def register_function_tool(
    name: str,
    category: str = "utility",
    description: str = "",
    version: str = "1.0.0",
    requires_api_access: bool = False,
    min_trust_level: str = "resident",
    timeout_seconds: int = 300,
):
    """
    REM: Decorator to register a Python function as a tool in the Toolroom.
    REM:
    REM: Usage:
    REM:   @register_function_tool(name="My Tool", category="utility")
    REM:   def my_tool(input_text: str) -> dict:
    REM:       return {"result": input_text.upper()}
    REM:
    REM: The decorated function is registered at import time with the
    REM: FunctionToolRegistry singleton. The Foreman syncs these into
    REM: the main ToolRegistry for unified checkout/return tracking.
    """
    def decorator(func: Callable) -> Callable:
        function_tool_registry.register(
            func=func,
            name=name,
            category=category,
            description=description or func.__doc__ or "",
            version=version,
            requires_api_access=requires_api_access,
            min_trust_level=min_trust_level,
            timeout_seconds=timeout_seconds,
        )
        # REM: Mark the function so the Foreman can identify it
        func._is_function_tool = True
        func._tool_id = f"func_{func.__name__}"
        return func

    return decorator
