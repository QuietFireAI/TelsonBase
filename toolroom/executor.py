# TelsonBase/toolroom/executor.py
# REM: =======================================================================================
# REM: TOOL EXECUTION ENGINE — HOW AGENTS ACTUALLY INVOKE TOOLS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: The Toolroom governance is production-grade (HITL gates, trust
# REM: levels, audit trails). But governance without execution is a library where nobody
# REM: can read the books. This module closes that gap.
# REM:
# REM: Two execution paths:
# REM:   1. SUBPROCESS — For git-cloned tools. Runs entry_point from manifest with
# REM:      scoped environment, timeout, and restricted PATH.
# REM:   2. FUNCTION — For in-house Python tools registered via @register_function_tool.
# REM:      Direct callable invocation, no subprocess overhead.
# REM:
# REM: v4.6.0CC: Implements Option B (subprocess isolation) from architectural review.
# REM:
# REM: QMS: Tool_Execute_Please ::tool_id:: → Tool_Execute_Thank_You / Thank_You_But_No
# REM: =======================================================================================

import logging
import os
import json
import subprocess
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from core.audit import audit, AuditEventType
from toolroom.manifest import ToolManifest, SandboxLevel

logger = logging.getLogger(__name__)

# REM: Base path where tools are installed — defaults to /app/toolroom/tools in Docker,
# REM: falls back to env var for local dev and CI (same pattern as CAGE_PATH in cage.py)
TOOLROOM_TOOLS_PATH = Path(os.environ.get("TOOLROOM_PATH", "/app/toolroom/tools"))

# REM: Minimal PATH for subprocess execution — no access to system tools beyond basics
RESTRICTED_PATH = "/usr/local/bin:/usr/bin:/bin"

# REM: Environment variables that are NEVER passed to tools
BLOCKED_ENV_VARS = {
    "MCP_API_KEY",
    "JWT_SECRET_KEY",
    "SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_ACCESS_KEY_ID",
}


@dataclass
class ExecutionResult:
    """
    REM: Result of a tool execution. Standardized contract for all execution paths.
    """
    tool_id: str
    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    error_message: str = ""
    output_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# REM: =======================================================================================
# REM: SUBPROCESS EXECUTION — FOR GIT-CLONED TOOLS
# REM: =======================================================================================

def execute_subprocess_tool(
    tool_id: str,
    manifest: ToolManifest,
    tool_dir: Path,
    inputs: Dict[str, Any],
    agent_id: str = "unknown",
    checkout_id: str = "",
) -> ExecutionResult:
    """
    REM: Execute a tool via subprocess with scoped environment.
    REM:
    REM: Security controls:
    REM:   - Restricted PATH (no arbitrary system binaries)
    REM:   - Blocked sensitive env vars (API keys, secrets)
    REM:   - Working directory set to tool's own directory
    REM:   - Timeout enforced from manifest
    REM:   - stdin/stdout/stderr captured
    REM:   - Input data passed via temp file (not command line args — no injection)
    REM:
    REM: QMS: Tool_Execute_Subprocess_Please ::tool_id:: → Thank_You / Thank_You_But_No
    """
    start_time = time.monotonic()

    logger.info(
        f"REM: Tool_Execute_Subprocess_Please ::{tool_id}:: "
        f"entry_point={manifest.entry_point} agent={agent_id} "
        f"checkout={checkout_id}"
    )

    # REM: Build scoped environment — start clean, only add what's needed
    scoped_env = {
        "PATH": RESTRICTED_PATH,
        "HOME": str(tool_dir),
        "TOOL_ID": tool_id,
        "TOOL_DIR": str(tool_dir),
        "AGENT_ID": agent_id,
        "CHECKOUT_ID": checkout_id,
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
    }

    # REM: Add manifest-declared environment vars (tool-specific config)
    for key, value in manifest.environment_vars.items():
        if key.upper() not in BLOCKED_ENV_VARS:
            scoped_env[key] = value
        else:
            logger.warning(
                f"REM: Blocked env var ::{key}:: for tool ::{tool_id}:: "
                f"— in BLOCKED_ENV_VARS list"
            )

    # REM: Write inputs to a temp file — tools read from TOOL_INPUT_FILE
    input_file = None
    try:
        if inputs:
            input_file = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                prefix=f"telson_input_{tool_id}_",
                delete=False,
                dir=str(tool_dir),
            )
            json.dump(inputs, input_file)
            input_file.close()
            scoped_env["TOOL_INPUT_FILE"] = input_file.name

        # REM: Parse entry_point into command + args
        # REM: entry_point is validated by manifest (no shell injection chars)
        cmd_parts = manifest.entry_point.split()

        # REM: Execute with subprocess — no shell=True, no injection vector
        result = subprocess.run(
            cmd_parts,
            cwd=str(tool_dir),
            env=scoped_env,
            capture_output=True,
            text=True,
            timeout=manifest.timeout_seconds,
        )

        duration = time.monotonic() - start_time

        # REM: Try to parse stdout as JSON for structured output
        output_data = {}
        if result.stdout.strip():
            try:
                output_data = json.loads(result.stdout.strip())
            except json.JSONDecodeError:
                output_data = {"raw_output": result.stdout.strip()}

        exec_result = ExecutionResult(
            tool_id=tool_id,
            success=(result.returncode == 0),
            exit_code=result.returncode,
            stdout=result.stdout[:10000],  # Cap at 10KB
            stderr=result.stderr[:5000],   # Cap at 5KB
            duration_seconds=round(duration, 3),
            output_data=output_data,
        )

        # REM: Audit the execution
        audit.log(
            AuditEventType.AGENT_ACTION,
            f"Tool executed: ::{tool_id}:: exit_code={result.returncode} "
            f"duration={duration:.2f}s",
            actor=agent_id,
            details={
                "tool_id": tool_id,
                "checkout_id": checkout_id,
                "exit_code": result.returncode,
                "duration_seconds": round(duration, 3),
            },
        )

        if exec_result.success:
            logger.info(
                f"REM: Tool_Execute_Thank_You ::{tool_id}:: "
                f"exit=0 duration={duration:.2f}s"
            )
        else:
            logger.warning(
                f"REM: Tool_Execute_Thank_You_But_No ::{tool_id}:: "
                f"exit={result.returncode} stderr={result.stderr[:200]}"
            )

        return exec_result

    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start_time
        logger.error(
            f"REM: Tool_Execute_Thank_You_But_No ::{tool_id}:: "
            f"::timeout:: after {manifest.timeout_seconds}s"
        )
        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Tool execution timed out: ::{tool_id}:: after {manifest.timeout_seconds}s",
            actor=agent_id,
            details={"tool_id": tool_id, "timeout": manifest.timeout_seconds},
        )
        return ExecutionResult(
            tool_id=tool_id,
            success=False,
            exit_code=-1,
            error_message=f"Execution timed out after {manifest.timeout_seconds} seconds",
            duration_seconds=round(duration, 3),
        )

    except FileNotFoundError as e:
        duration = time.monotonic() - start_time
        logger.error(
            f"REM: Tool_Execute_Thank_You_But_No ::{tool_id}:: "
            f"::entry_point_not_found:: {manifest.entry_point}"
        )
        return ExecutionResult(
            tool_id=tool_id,
            success=False,
            exit_code=-2,
            error_message=f"Entry point not found: {manifest.entry_point}. Error: {e}",
            duration_seconds=round(duration, 3),
        )

    except Exception as e:
        duration = time.monotonic() - start_time
        logger.error(
            f"REM: Tool_Execute_Thank_You_But_No ::{tool_id}:: "
            f"::unexpected_error:: {e}"
        )
        return ExecutionResult(
            tool_id=tool_id,
            success=False,
            exit_code=-3,
            error_message=f"Unexpected execution error: {str(e)}",
            duration_seconds=round(duration, 3),
        )

    finally:
        # REM: Cleanup temp input file
        if input_file and os.path.exists(input_file.name):
            try:
                os.unlink(input_file.name)
            except OSError:
                pass


# REM: =======================================================================================
# REM: FUNCTION TOOL EXECUTION — FOR IN-HOUSE PYTHON TOOLS
# REM: =======================================================================================

def execute_function_tool(
    tool_id: str,
    func: Callable,
    inputs: Dict[str, Any],
    agent_id: str = "unknown",
    checkout_id: str = "",
    timeout_seconds: int = 300,
) -> ExecutionResult:
    """
    REM: Execute a registered function tool directly.
    REM: No subprocess overhead — function is called in-process.
    REM:
    REM: Security note: Function tools are in-house code registered by the
    REM: TelsonBase operator. They run with Foreman-level access by design.
    REM: For untrusted tools, use subprocess execution instead.
    REM:
    REM: QMS: Tool_Execute_Function_Please ::tool_id:: → Thank_You / Thank_You_But_No
    """
    start_time = time.monotonic()

    logger.info(
        f"REM: Tool_Execute_Function_Please ::{tool_id}:: "
        f"func={func.__name__} agent={agent_id}"
    )

    try:
        # REM: Call the function with inputs as kwargs
        result = func(**inputs)
        duration = time.monotonic() - start_time

        # REM: Normalize result to dict
        if isinstance(result, dict):
            output_data = result
        elif isinstance(result, str):
            output_data = {"result": result}
        elif result is None:
            output_data = {}
        else:
            output_data = {"result": str(result)}

        audit.log(
            AuditEventType.AGENT_ACTION,
            f"Function tool executed: ::{tool_id}:: duration={duration:.2f}s",
            actor=agent_id,
            details={
                "tool_id": tool_id,
                "checkout_id": checkout_id,
                "function": func.__name__,
                "duration_seconds": round(duration, 3),
            },
        )

        logger.info(
            f"REM: Tool_Execute_Function_Thank_You ::{tool_id}:: "
            f"duration={duration:.2f}s"
        )

        return ExecutionResult(
            tool_id=tool_id,
            success=True,
            exit_code=0,
            duration_seconds=round(duration, 3),
            output_data=output_data,
        )

    except Exception as e:
        duration = time.monotonic() - start_time
        logger.error(
            f"REM: Tool_Execute_Function_Thank_You_But_No ::{tool_id}:: "
            f"::error:: {e}"
        )
        audit.log(
            AuditEventType.AGENT_ACTION,
            f"Function tool failed: ::{tool_id}:: error={e}",
            actor=agent_id,
            details={"tool_id": tool_id, "error": str(e)},
        )
        return ExecutionResult(
            tool_id=tool_id,
            success=False,
            exit_code=-1,
            error_message=str(e),
            duration_seconds=round(duration, 3),
        )
