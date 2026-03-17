# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_toolroom_executor_depth.py
# REM: Depth tests for toolroom/executor.py — ExecutionResult, BLOCKED_ENV_VARS,
# REM: execute_function_tool (pure in-process function execution, no subprocess)

import sys
from unittest.mock import MagicMock

# REM: celery not installed locally
if "celery" not in sys.modules:
    sys.modules["celery"] = MagicMock()

import pytest

from toolroom.executor import (
    ExecutionResult,
    BLOCKED_ENV_VARS,
    RESTRICTED_PATH,
    TOOLROOM_TOOLS_PATH,
    execute_function_tool,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstants:
    def test_restricted_path_is_string(self):
        assert isinstance(RESTRICTED_PATH, str)

    def test_restricted_path_has_usr_bin(self):
        assert "/usr/bin" in RESTRICTED_PATH

    def test_blocked_env_vars_is_set(self):
        assert isinstance(BLOCKED_ENV_VARS, (set, frozenset))

    def test_mcp_api_key_blocked(self):
        assert "MCP_API_KEY" in BLOCKED_ENV_VARS

    def test_jwt_secret_key_blocked(self):
        assert "JWT_SECRET_KEY" in BLOCKED_ENV_VARS

    def test_secret_key_blocked(self):
        assert "SECRET_KEY" in BLOCKED_ENV_VARS

    def test_database_url_blocked(self):
        assert "DATABASE_URL" in BLOCKED_ENV_VARS

    def test_redis_url_blocked(self):
        assert "REDIS_URL" in BLOCKED_ENV_VARS

    def test_aws_secret_blocked(self):
        assert "AWS_SECRET_ACCESS_KEY" in BLOCKED_ENV_VARS

    def test_aws_access_key_blocked(self):
        assert "AWS_ACCESS_KEY_ID" in BLOCKED_ENV_VARS

    def test_toolroom_tools_path_is_path(self):
        from pathlib import Path
        assert isinstance(TOOLROOM_TOOLS_PATH, Path)


# ═══════════════════════════════════════════════════════════════════════════════
# ExecutionResult dataclass
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecutionResult:
    def test_minimal_construction(self):
        r = ExecutionResult(tool_id="tool_1", success=True)
        assert r.tool_id == "tool_1"
        assert r.success is True

    def test_default_exit_code_zero(self):
        r = ExecutionResult(tool_id="t", success=True)
        assert r.exit_code == 0

    def test_default_stdout_empty(self):
        r = ExecutionResult(tool_id="t", success=True)
        assert r.stdout == ""

    def test_default_stderr_empty(self):
        r = ExecutionResult(tool_id="t", success=True)
        assert r.stderr == ""

    def test_default_duration_zero(self):
        r = ExecutionResult(tool_id="t", success=True)
        assert r.duration_seconds == 0.0

    def test_default_error_message_empty(self):
        r = ExecutionResult(tool_id="t", success=True)
        assert r.error_message == ""

    def test_default_output_data_empty_dict(self):
        r = ExecutionResult(tool_id="t", success=True)
        assert r.output_data == {}

    def test_to_dict_returns_dict(self):
        r = ExecutionResult(tool_id="t", success=True)
        assert isinstance(r.to_dict(), dict)

    def test_to_dict_contains_tool_id(self):
        r = ExecutionResult(tool_id="my_tool", success=True)
        assert r.to_dict()["tool_id"] == "my_tool"

    def test_to_dict_contains_success(self):
        r = ExecutionResult(tool_id="t", success=False)
        assert r.to_dict()["success"] is False

    def test_construction_with_all_fields(self):
        r = ExecutionResult(
            tool_id="t",
            success=True,
            exit_code=0,
            stdout="hello\n",
            stderr="",
            duration_seconds=0.42,
            error_message="",
            output_data={"key": "value"},
        )
        assert r.stdout == "hello\n"
        assert r.duration_seconds == 0.42
        assert r.output_data["key"] == "value"


# ═══════════════════════════════════════════════════════════════════════════════
# execute_function_tool — in-process function execution
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecuteFunctionTool:
    def test_returns_execution_result(self):
        result = execute_function_tool("t1", lambda: {"x": 1}, {})
        assert isinstance(result, ExecutionResult)

    def test_success_true_on_normal_call(self):
        result = execute_function_tool("t1", lambda: {"x": 1}, {})
        assert result.success is True

    def test_exit_code_zero_on_success(self):
        result = execute_function_tool("t1", lambda: {}, {})
        assert result.exit_code == 0

    def test_dict_result_becomes_output_data(self):
        result = execute_function_tool("t1", lambda: {"answer": 42}, {})
        assert result.output_data == {"answer": 42}

    def test_string_result_wrapped_in_result_key(self):
        result = execute_function_tool("t1", lambda: "hello world", {})
        assert result.output_data == {"result": "hello world"}

    def test_none_result_becomes_empty_dict(self):
        result = execute_function_tool("t1", lambda: None, {})
        assert result.output_data == {}

    def test_int_result_converted_to_string(self):
        result = execute_function_tool("t1", lambda: 42, {})
        assert result.output_data == {"result": "42"}

    def test_list_result_converted_to_string(self):
        result = execute_function_tool("t1", lambda: [1, 2, 3], {})
        assert "result" in result.output_data

    def test_inputs_passed_as_kwargs(self):
        def add_nums(a: int, b: int) -> dict:
            return {"sum": a + b}
        result = execute_function_tool("add", add_nums, {"a": 3, "b": 4})
        assert result.output_data == {"sum": 7}

    def test_tool_id_stored(self):
        result = execute_function_tool("my_tool_id", lambda: {}, {})
        assert result.tool_id == "my_tool_id"

    def test_duration_positive(self):
        result = execute_function_tool("t1", lambda: {}, {})
        assert result.duration_seconds >= 0.0

    def test_failure_on_exception(self):
        def broken():
            raise ValueError("something broke")
        result = execute_function_tool("broken_tool", broken, {})
        assert result.success is False

    def test_failure_exit_code_negative_one(self):
        def broken():
            raise RuntimeError("crash")
        result = execute_function_tool("broken_tool", broken, {})
        assert result.exit_code == -1

    def test_failure_stores_error_message(self):
        def broken():
            raise ValueError("specific error message")
        result = execute_function_tool("broken_tool", broken, {})
        assert "specific error message" in result.error_message

    def test_success_error_message_empty(self):
        result = execute_function_tool("t1", lambda: {}, {})
        assert result.error_message == ""

    def test_agent_id_parameter_accepted(self):
        result = execute_function_tool("t1", lambda: {}, {}, agent_id="agent_x")
        assert result.success is True

    def test_checkout_id_parameter_accepted(self):
        result = execute_function_tool("t1", lambda: {}, {}, checkout_id="CHKOUT-abc")
        assert result.success is True

    def test_complex_output_data(self):
        def complex_func() -> dict:
            return {"nested": {"a": 1, "b": [1, 2, 3]}, "count": 5}
        result = execute_function_tool("complex", complex_func, {})
        assert result.output_data["count"] == 5
        assert result.output_data["nested"]["a"] == 1
