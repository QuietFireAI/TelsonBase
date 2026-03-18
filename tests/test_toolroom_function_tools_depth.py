# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_toolroom_function_tools_depth.py
# REM: Depth tests for toolroom/function_tools.py — pure in-memory, no Redis/external deps

import sys
from unittest.mock import MagicMock

# REM: celery is not installed locally — stub before toolroom import
if "celery" not in sys.modules:
    celery_mock = MagicMock()
    celery_mock.shared_task = lambda *args, **kwargs: (lambda f: f)
    sys.modules["celery"] = celery_mock

import pytest

from toolroom.function_tools import (
    FunctionToolEntry,
    FunctionToolRegistry,
    register_function_tool,
)
from toolroom.manifest import ToolManifest, SandboxLevel


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures / helpers
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def freg():
    """Fresh FunctionToolRegistry for each test (not the global singleton)."""
    return FunctionToolRegistry()


def _simple_func(text: str) -> dict:
    """A simple test function."""
    return {"result": text}


def _typed_func(name: str, count: int, ratio: float, flag: bool) -> dict:
    """All basic type hints."""
    return {}


def _defaulted_func(required: str, optional: str = "default") -> dict:
    """A function with an optional param."""
    return {}


def _no_hints(x, y):
    """No type hints at all."""
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# FunctionToolEntry dataclass
# ═══════════════════════════════════════════════════════════════════════════════

class TestFunctionToolEntry:
    def test_construction(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_simple_func, name="Test", description="", version="1.0.0", timeout_seconds=30
        )
        entry = FunctionToolEntry(
            tool_id="func_test",
            name="Test",
            func=_simple_func,
            manifest=manifest,
        )
        assert entry.tool_id == "func_test"
        assert entry.name == "Test"

    def test_default_version(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_simple_func, name="T", description="", version="1.0.0", timeout_seconds=30
        )
        entry = FunctionToolEntry(tool_id="f", name="T", func=_simple_func, manifest=manifest)
        assert entry.version == "1.0.0"

    def test_default_requires_api_access_false(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_simple_func, name="T", description="", version="1.0.0", timeout_seconds=30
        )
        entry = FunctionToolEntry(tool_id="f", name="T", func=_simple_func, manifest=manifest)
        assert entry.requires_api_access is False

    def test_default_min_trust_level(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_simple_func, name="T", description="", version="1.0.0", timeout_seconds=30
        )
        entry = FunctionToolEntry(tool_id="f", name="T", func=_simple_func, manifest=manifest)
        assert entry.min_trust_level == "resident"


# ═══════════════════════════════════════════════════════════════════════════════
# FunctionToolRegistry.register
# ═══════════════════════════════════════════════════════════════════════════════

class TestFunctionToolRegistryRegister:
    def test_returns_entry(self, freg):
        entry = freg.register(func=_simple_func, name="Simple")
        assert isinstance(entry, FunctionToolEntry)

    def test_tool_id_is_func_name(self, freg):
        entry = freg.register(func=_simple_func, name="Simple")
        assert entry.tool_id == "func__simple_func"

    def test_stored_in_registry(self, freg):
        freg.register(func=_simple_func, name="Simple")
        assert "func__simple_func" in freg._tools

    def test_name_stored(self, freg):
        freg.register(func=_simple_func, name="My Name")
        assert freg._tools["func__simple_func"].name == "My Name"

    def test_category_stored(self, freg):
        freg.register(func=_simple_func, name="T", category="crypto")
        assert freg._tools["func__simple_func"].category == "crypto"

    def test_description_uses_func_docstring_if_empty(self, freg):
        entry = freg.register(func=_simple_func, name="T", description="")
        assert "simple" in entry.description.lower()

    def test_description_explicit_takes_precedence(self, freg):
        entry = freg.register(func=_simple_func, name="T", description="My desc")
        assert entry.description == "My desc"

    def test_requires_api_access_stored(self, freg):
        entry = freg.register(func=_simple_func, name="T", requires_api_access=True)
        assert entry.requires_api_access is True

    def test_min_trust_level_stored(self, freg):
        entry = freg.register(func=_simple_func, name="T", min_trust_level="citizen")
        assert entry.min_trust_level == "citizen"

    def test_manifest_is_tool_manifest(self, freg):
        entry = freg.register(func=_simple_func, name="T")
        assert isinstance(entry.manifest, ToolManifest)

    def test_manifest_sandbox_none(self, freg):
        entry = freg.register(func=_simple_func, name="T")
        assert entry.manifest.sandbox_level == SandboxLevel.NONE

    def test_manifest_has_inputs(self, freg):
        entry = freg.register(func=_simple_func, name="T")
        # _simple_func has one param: text: str
        assert len(entry.manifest.inputs) == 1
        assert entry.manifest.inputs[0]["name"] == "text"

    def test_overwrite_same_tool_id(self, freg):
        freg.register(func=_simple_func, name="Version 1")
        freg.register(func=_simple_func, name="Version 2")
        assert freg._tools["func__simple_func"].name == "Version 2"


# ═══════════════════════════════════════════════════════════════════════════════
# FunctionToolRegistry.get / list_all / unregister
# ═══════════════════════════════════════════════════════════════════════════════

class TestFunctionToolRegistryCRUD:
    def test_get_returns_none_for_unknown(self, freg):
        assert freg.get("func_nonexistent") is None

    def test_get_returns_entry(self, freg):
        freg.register(func=_simple_func, name="T")
        entry = freg.get("func__simple_func")
        assert isinstance(entry, FunctionToolEntry)

    def test_list_all_empty(self, freg):
        assert freg.list_all() == []

    def test_list_all_after_register(self, freg):
        freg.register(func=_simple_func, name="T")
        assert len(freg.list_all()) == 1

    def test_list_all_multiple(self, freg):
        freg.register(func=_simple_func, name="T1")
        freg.register(func=_typed_func, name="T2")
        assert len(freg.list_all()) == 2

    def test_unregister_returns_false_for_unknown(self, freg):
        assert freg.unregister("func_nonexistent") is False

    def test_unregister_returns_true(self, freg):
        freg.register(func=_simple_func, name="T")
        assert freg.unregister("func__simple_func") is True

    def test_unregister_removes_from_registry(self, freg):
        freg.register(func=_simple_func, name="T")
        freg.unregister("func__simple_func")
        assert freg.get("func__simple_func") is None


# ═══════════════════════════════════════════════════════════════════════════════
# _build_manifest_from_function — type mapping logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildManifestFromFunction:
    def test_string_type_mapped(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_typed_func, name="T", description="", version="1.0.0", timeout_seconds=60
        )
        name_param = next(p for p in manifest.inputs if p["name"] == "name")
        assert name_param["type"] == "string"

    def test_int_type_mapped(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_typed_func, name="T", description="", version="1.0.0", timeout_seconds=60
        )
        count_param = next(p for p in manifest.inputs if p["name"] == "count")
        assert count_param["type"] == "integer"

    def test_float_type_mapped(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_typed_func, name="T", description="", version="1.0.0", timeout_seconds=60
        )
        ratio_param = next(p for p in manifest.inputs if p["name"] == "ratio")
        assert ratio_param["type"] == "float"

    def test_bool_type_mapped(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_typed_func, name="T", description="", version="1.0.0", timeout_seconds=60
        )
        flag_param = next(p for p in manifest.inputs if p["name"] == "flag")
        assert flag_param["type"] == "boolean"

    def test_no_hints_defaults_to_string(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_no_hints, name="T", description="", version="1.0.0", timeout_seconds=60
        )
        assert all(p["type"] == "string" for p in manifest.inputs)

    def test_required_param_has_required_true(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_defaulted_func, name="T", description="", version="1.0.0", timeout_seconds=60
        )
        req = next(p for p in manifest.inputs if p["name"] == "required")
        assert req["required"] is True

    def test_optional_param_has_required_false(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_defaulted_func, name="T", description="", version="1.0.0", timeout_seconds=60
        )
        opt = next(p for p in manifest.inputs if p["name"] == "optional")
        assert opt["required"] is False

    def test_optional_param_has_default(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_defaulted_func, name="T", description="", version="1.0.0", timeout_seconds=60
        )
        opt = next(p for p in manifest.inputs if p["name"] == "optional")
        assert opt["default"] == "default"

    def test_entry_point_format(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_simple_func, name="T", description="", version="1.0.0", timeout_seconds=60
        )
        assert "_simple_func" in manifest.entry_point
        assert manifest.entry_point.startswith("python::")

    def test_timeout_stored(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_simple_func, name="T", description="", version="1.0.0", timeout_seconds=45
        )
        assert manifest.timeout_seconds == 45

    def test_sandbox_level_none(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_simple_func, name="T", description="", version="1.0.0", timeout_seconds=60
        )
        assert manifest.sandbox_level == SandboxLevel.NONE

    def test_skips_self_cls_params(self, freg):
        class MyClass:
            def method(self, value: str) -> dict:
                return {}
        manifest = freg._build_manifest_from_function(
            func=MyClass.method, name="T", description="", version="1.0.0", timeout_seconds=60
        )
        param_names = [p["name"] for p in manifest.inputs]
        assert "self" not in param_names

    def test_four_params_for_typed_func(self, freg):
        manifest = freg._build_manifest_from_function(
            func=_typed_func, name="T", description="", version="1.0.0", timeout_seconds=60
        )
        assert len(manifest.inputs) == 4


# ═══════════════════════════════════════════════════════════════════════════════
# register_function_tool decorator
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegisterFunctionToolDecorator:
    def test_decorator_marks_function(self):
        @register_function_tool(name="Marked Tool")
        def my_decorated(text: str) -> dict:
            return {}
        assert my_decorated._is_function_tool is True

    def test_decorator_sets_tool_id(self):
        @register_function_tool(name="ID Tool")
        def id_tool_func(text: str) -> dict:
            return {}
        assert id_tool_func._tool_id == "func_id_tool_func"

    def test_decorator_preserves_callable(self):
        @register_function_tool(name="Callable Tool")
        def callable_func(x: str) -> dict:
            return {"x": x}
        assert callable(callable_func)
        assert callable_func("hello") == {"x": "hello"}

    def test_decorator_returns_same_function(self):
        def raw(x: str) -> dict:
            return {}
        decorated = register_function_tool(name="Same Fn")(raw)
        # The decorator returns the original function with attributes added
        assert decorated is raw
