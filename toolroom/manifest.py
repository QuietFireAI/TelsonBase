# TelsonBase/toolroom/manifest.py
# REM: =======================================================================================
# REM: TOOL MANIFEST — THE CONTRACT EVERY TOOL MUST FULFILL
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: A tool without a manifest is cargo without a shipping label.
# REM: The manifest defines HOW a tool is invoked, WHAT it expects, WHAT it returns,
# REM: and WHAT isolation level it requires. Without this, the Toolroom is a warehouse
# REM: of boxes nobody can open.
# REM:
# REM: v4.6.0CC: Closes the execution gap identified in architectural review.
# REM: Every installed tool must provide a tool_manifest.json at its root.
# REM: Tools registered via @register_function_tool bypass this (they ARE the manifest).
# REM:
# REM: QMS: Tool_Manifest_Validate_Please → Tool_Manifest_Thank_You / Thank_You_But_No
# REM: =======================================================================================

import json
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "tool_manifest.json"


class SandboxLevel(str, Enum):
    """
    REM: How isolated should this tool's execution be?
    REM: Higher isolation = more overhead but stronger containment.
    """
    NONE = "none"           # In-process function call (function tools only)
    SUBPROCESS = "subprocess"   # subprocess.run with scoped env (default for git tools)
    CONTAINER = "container"     # Future: Docker container per execution


class InputType(str, Enum):
    """REM: Supported input types for tool parameters."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"
    FILE_PATH = "file_path"


@dataclass
class ToolParameter:
    """REM: A single input or output parameter for a tool."""
    name: str
    type: str = InputType.STRING    # InputType value
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass
class ToolManifest:
    """
    REM: The manifest every tool must provide.
    REM: This is the contract between the tool and the Foreman's execution engine.
    REM:
    REM: For git-cloned tools: read from tool_manifest.json in the repo root.
    REM: For function tools: auto-generated from the @register_function_tool decorator.
    REM: For uploaded tools: must be included in the upload or created manually.
    """
    # REM: Required — every manifest must have these
    name: str                                   # Human-readable tool name
    entry_point: str                            # How to invoke: "python main.py", "./run.sh", etc.
    version: str                                # SemVer of the tool itself

    # REM: Description and classification
    description: str = ""
    author: str = ""
    license: str = ""

    # REM: Execution contract
    inputs: List[Dict[str, Any]] = field(default_factory=list)   # List of ToolParameter dicts
    outputs: List[Dict[str, Any]] = field(default_factory=list)  # Expected output structure

    # REM: Isolation and security
    sandbox_level: str = SandboxLevel.SUBPROCESS  # SandboxLevel value
    timeout_seconds: int = 300                     # Max execution time (5 min default)
    requires_network: bool = False                 # Does it need outbound network access?
    requires_gpu: bool = False                     # Does it need GPU acceleration?
    environment_vars: Dict[str, str] = field(default_factory=dict)  # Env vars to inject

    # REM: Dependencies
    python_dependencies: List[str] = field(default_factory=list)  # pip packages needed
    system_dependencies: List[str] = field(default_factory=list)  # apt packages needed

    # REM: Metadata
    min_telsonbase_version: str = "4.6.0"          # Minimum compatible TelsonBase version
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolManifest":
        """REM: Build manifest from dict. Ignores unknown fields for forward compat."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, json_str: str) -> "ToolManifest":
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, manifest_path: Path) -> "ToolManifest":
        """REM: Load manifest from a tool_manifest.json file."""
        with open(manifest_path, "r") as f:
            return cls.from_dict(json.load(f))


# REM: =======================================================================================
# REM: MANIFEST VALIDATION
# REM: =======================================================================================

class ManifestValidationError(Exception):
    """REM: Raised when a tool_manifest.json fails validation."""
    pass


def validate_manifest(manifest: ToolManifest) -> List[str]:
    """
    REM: Validate a ToolManifest. Returns list of errors (empty = valid).
    REM: QMS: Tool_Manifest_Validate_Please → errors[] or []
    """
    errors = []

    # REM: Required fields
    if not manifest.name or not manifest.name.strip():
        errors.append("'name' is required and cannot be empty")

    if not manifest.entry_point or not manifest.entry_point.strip():
        errors.append("'entry_point' is required and cannot be empty")

    if not manifest.version or not manifest.version.strip():
        errors.append("'version' is required and cannot be empty")

    # REM: Sandbox level must be recognized
    try:
        SandboxLevel(manifest.sandbox_level)
    except ValueError:
        errors.append(
            f"'sandbox_level' must be one of: {[s.value for s in SandboxLevel]}. "
            f"Got: '{manifest.sandbox_level}'"
        )

    # REM: Timeout must be positive and bounded
    if manifest.timeout_seconds <= 0:
        errors.append("'timeout_seconds' must be positive")
    if manifest.timeout_seconds > 3600:
        errors.append("'timeout_seconds' exceeds maximum of 3600 (1 hour)")

    # REM: Entry point security — no shell injection vectors
    dangerous_chars = [";", "&&", "||", "|", "`", "$(", "${"]
    for char in dangerous_chars:
        if char in manifest.entry_point:
            errors.append(
                f"'entry_point' contains dangerous character sequence '{char}'. "
                f"Use explicit command + args, not shell expressions."
            )

    # REM: Input parameters must have names
    for i, inp in enumerate(manifest.inputs):
        if not inp.get("name"):
            errors.append(f"Input parameter at index {i} is missing 'name'")

    # REM: Network access + subprocess is fine; network + none is suspicious
    if manifest.requires_network and manifest.sandbox_level == SandboxLevel.NONE:
        errors.append(
            "Tools requiring network access should use 'subprocess' or 'container' "
            "sandbox level, not 'none'"
        )

    return errors


def load_manifest_from_tool_dir(tool_dir: Path) -> Optional[ToolManifest]:
    """
    REM: Load and validate manifest from a tool's install directory.
    REM: Returns None if no manifest found or validation fails.
    """
    manifest_path = tool_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        logger.warning(
            f"REM: Tool_Manifest_Thank_You_But_No ::missing:: "
            f"No {MANIFEST_FILENAME} in {tool_dir}"
        )
        return None

    try:
        manifest = ToolManifest.from_file(manifest_path)
        errors = validate_manifest(manifest)
        if errors:
            logger.error(
                f"REM: Tool_Manifest_Thank_You_But_No ::invalid:: "
                f"Validation errors in {manifest_path}: {errors}"
            )
            return None
        logger.info(
            f"REM: Tool_Manifest_Thank_You ::{manifest.name}:: "
            f"v{manifest.version} entry_point={manifest.entry_point}"
        )
        return manifest
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(
            f"REM: Tool_Manifest_Thank_You_But_No ::parse_error:: "
            f"Failed to parse {manifest_path}: {e}"
        )
        return None
