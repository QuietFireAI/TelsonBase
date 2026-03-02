# TelsonBase/tests/test_qms.py
# REM: =======================================================================================
# REM: QMS v2.1.6 TEST SUITE — CHAIN BUILDING, PARSING, VALIDATION, SECURITY
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Comprehensive tests for the Quietfire AI Message Standard formal
# REM: chain syntax. Covers block detection, chain assembly, parsing, validation rules,
# REM: halt postscript conventions, and security flagging (anonymous transmission detection).
# REM: =======================================================================================

import pytest
from core.qms import (
    # v2.1.6 chain support
    QMSBlockType,
    QMSBlock,
    QMSChain,
    QMSStatus,
    QMSValidationResult,
    SYSTEM_HALT,
    SYSTEM_HALT_BLOCK,
    build_chain,
    build_halt_chain,
    parse_chain,
    find_chains,
    validate_chain,
    validate_chain_string,
    is_chain_formatted,
    log_qms_chain,
    # Legacy support
    QMSFieldType,
    QMSMessage,
    is_qms_formatted,
    validate_qms,
    parse_qms,
    format_qms,
    format_qms_response,
    # Internal helpers (test via public API where possible)
    _detect_block_type,
    _make_block,
    _wrap_qualifier,
)


# REM: =======================================================================================
# REM: SECTION 1: BLOCK DETECTION — QUALIFIER IDENTIFICATION
# REM: =======================================================================================

class TestBlockDetection:
    """REM: Tests that block type detection correctly identifies qualifiers."""

    def test_detect_origin_block(self):
        assert _detect_block_type("<backup_agent>") == QMSBlockType.ORIGIN

    def test_detect_origin_with_numeric_id(self):
        assert _detect_block_type("<backup_agent/007>") == QMSBlockType.ORIGIN

    def test_detect_origin_federated(self):
        assert _detect_block_type("<alpha_instance/sync_agent/012>") == QMSBlockType.ORIGIN

    def test_detect_correlation_block(self):
        assert _detect_block_type("@@REQ_a8f3c200@@") == QMSBlockType.CORRELATION

    def test_detect_generic_block(self):
        assert _detect_block_type("Create_Backup") == QMSBlockType.GENERIC

    def test_detect_numeric_block(self):
        assert _detect_block_type("$$49.99$$") == QMSBlockType.NUMERIC

    def test_detect_identifier_block(self):
        assert _detect_block_type("##USER_123##") == QMSBlockType.IDENTIFIER

    def test_detect_string_block(self):
        assert _detect_block_type("%%Permission Denied%%") == QMSBlockType.STRING

    def test_detect_query_block(self):
        assert _detect_block_type("??Specify_Filename??") == QMSBlockType.QUERY

    def test_detect_version_block(self):
        assert _detect_block_type("&&QMS_v2.1.6&&") == QMSBlockType.VERSION

    def test_detect_encrypted_block(self):
        assert _detect_block_type("||a746fg2e96a6g7||") == QMSBlockType.ENCRYPTED

    def test_detect_command_please(self):
        assert _detect_block_type("_Please") == QMSBlockType.COMMAND

    def test_detect_command_thank_you(self):
        assert _detect_block_type("_Thank_You") == QMSBlockType.COMMAND

    def test_detect_command_thank_you_but_no(self):
        assert _detect_block_type("_Thank_You_But_No") == QMSBlockType.COMMAND

    def test_detect_command_excuse_me(self):
        assert _detect_block_type("_Excuse_Me") == QMSBlockType.COMMAND

    def test_detect_command_pretty_please(self):
        assert _detect_block_type("_Pretty_Please") == QMSBlockType.COMMAND

    def test_detect_system_halt(self):
        assert _detect_block_type("%%%%") == QMSBlockType.SYSTEM_HALT

    def test_short_qualifier_not_misdetected(self):
        """REM: Qualifiers with length <= 4 should be GENERIC, not misidentified."""
        assert _detect_block_type("$$$$") == QMSBlockType.GENERIC
        assert _detect_block_type("####") == QMSBlockType.GENERIC


# REM: =======================================================================================
# REM: SECTION 2: BLOCK OBJECT — CONSTRUCTION AND VALUE EXTRACTION
# REM: =======================================================================================

class TestQMSBlock:
    """REM: Tests for QMSBlock creation and inner_value extraction."""

    def test_block_to_string(self):
        block = QMSBlock(content="Create_Backup", block_type=QMSBlockType.GENERIC)
        assert block.to_string() == "::Create_Backup::"

    def test_origin_inner_value(self):
        block = QMSBlock(content="<backup_agent>", block_type=QMSBlockType.ORIGIN)
        assert block.inner_value == "backup_agent"

    def test_origin_federated_inner_value(self):
        block = QMSBlock(content="<alpha/sync/012>", block_type=QMSBlockType.ORIGIN)
        assert block.inner_value == "alpha/sync/012"

    def test_correlation_inner_value(self):
        block = QMSBlock(content="@@REQ_a8f3@@", block_type=QMSBlockType.CORRELATION)
        assert block.inner_value == "REQ_a8f3"

    def test_numeric_inner_value(self):
        block = QMSBlock(content="$$49.99$$", block_type=QMSBlockType.NUMERIC)
        assert block.inner_value == "49.99"

    def test_identifier_inner_value(self):
        block = QMSBlock(content="##USER_123##", block_type=QMSBlockType.IDENTIFIER)
        assert block.inner_value == "USER_123"

    def test_string_inner_value(self):
        block = QMSBlock(content="%%Permission Denied%%", block_type=QMSBlockType.STRING)
        assert block.inner_value == "Permission Denied"

    def test_command_inner_value(self):
        block = QMSBlock(content="_Please", block_type=QMSBlockType.COMMAND)
        assert block.inner_value == "Please"

    def test_halt_inner_value(self):
        block = QMSBlock(content="%%%%", block_type=QMSBlockType.SYSTEM_HALT)
        assert block.inner_value == ""

    def test_generic_inner_value(self):
        block = QMSBlock(content="Create_Backup", block_type=QMSBlockType.GENERIC)
        assert block.inner_value == "Create_Backup"


# REM: =======================================================================================
# REM: SECTION 3: CHAIN BUILDING — FORMAL v2.1.6 SYNTAX
# REM: =======================================================================================

class TestBuildChain:
    """REM: Tests for build_chain() — assembling formal instruction chains."""

    def test_simple_ping(self):
        chain = build_chain(
            origin="monitor_agent",
            action="Ping",
            status=QMSStatus.PLEASE
        )
        chain_str = chain.to_string()
        assert "::<monitor_agent>::" in chain_str
        assert "::Ping::" in chain_str
        assert "::_Please::" in chain_str

    def test_chain_has_origin_in_position_1(self):
        chain = build_chain(origin="test", action="Action", status=QMSStatus.PLEASE)
        assert chain.blocks[0].block_type == QMSBlockType.ORIGIN
        assert chain.origin == "test"

    def test_chain_has_correlation_in_position_2(self):
        chain = build_chain(origin="test", action="Action", status=QMSStatus.PLEASE)
        assert chain.blocks[1].block_type == QMSBlockType.CORRELATION
        assert chain.correlation_id is not None
        assert chain.correlation_id.startswith("REQ_")

    def test_chain_has_action_in_position_3(self):
        chain = build_chain(origin="test", action="Create_Backup", status=QMSStatus.PLEASE)
        assert chain.blocks[2].block_type == QMSBlockType.GENERIC
        assert chain.action == "Create_Backup"

    def test_chain_command_is_terminal(self):
        chain = build_chain(origin="test", action="Action", status=QMSStatus.THANK_YOU)
        assert chain.blocks[-1].block_type == QMSBlockType.COMMAND
        assert chain.command == QMSStatus.THANK_YOU

    def test_chain_with_data_blocks(self):
        chain = build_chain(
            origin="backup_agent",
            action="Create_Backup",
            status=QMSStatus.PLEASE,
            data_blocks=[
                ("ollama_data", QMSBlockType.IDENTIFIER),
                ("1", QMSBlockType.NUMERIC),
            ]
        )
        chain_str = chain.to_string()
        assert "::##ollama_data##::" in chain_str
        assert "::$$1$$::" in chain_str

    def test_chain_with_explicit_correlation_id(self):
        chain = build_chain(
            origin="test",
            action="Action",
            status=QMSStatus.PLEASE,
            correlation_id="REQ_custom123"
        )
        assert chain.correlation_id == "REQ_custom123"
        assert "::@@REQ_custom123@@::" in chain.to_string()

    def test_all_five_command_statuses(self):
        for status in QMSStatus:
            chain = build_chain(origin="test", action="Action", status=status)
            assert chain.command == status
            assert f"::_{status.value}::" in chain.to_string()

    def test_chain_raw_matches_to_string(self):
        chain = build_chain(origin="test", action="Ping", status=QMSStatus.PLEASE)
        assert chain.raw == chain.to_string()

    def test_chain_dash_separator(self):
        """REM: Blocks are separated by single dash, not spaces or other chars."""
        chain = build_chain(origin="test", action="Ping", status=QMSStatus.PLEASE)
        parts = chain.to_string().split("-")
        # Each part should start with :: and end with ::
        for part in parts:
            assert part.startswith("::") and part.endswith("::")


# REM: =======================================================================================
# REM: SECTION 4: HALT CHAIN — SYSTEM HALT WITH POSTSCRIPT
# REM: =======================================================================================

class TestBuildHaltChain:
    """REM: Tests for build_halt_chain() — the siren fires first, incident report follows."""

    def test_halt_chain_has_halt_block(self):
        chain = build_halt_chain(origin="test", action="Process_Payment")
        assert chain.is_halt is True

    def test_halt_chain_without_reason(self):
        chain = build_halt_chain(origin="test", action="Process_Payment")
        assert chain.halt_reason is None
        assert SYSTEM_HALT_BLOCK in chain.to_string()

    def test_halt_chain_with_reason(self):
        chain = build_halt_chain(
            origin="payment_agent",
            action="Process_Payment",
            reason="Database connection lost"
        )
        assert chain.halt_reason == "Database connection lost"
        chain_str = chain.to_string()
        assert "::%%%%::" in chain_str
        assert "::%%Database connection lost%%::" in chain_str

    def test_halt_reason_follows_siren(self):
        """REM: The siren ::%%%%:: must come BEFORE the reason ::%%...%%::"""
        chain = build_halt_chain(
            origin="test",
            action="Fail",
            reason="Something broke"
        )
        chain_str = chain.to_string()
        halt_pos = chain_str.index("::%%%%::")
        reason_pos = chain_str.index("::%%Something broke%%::")
        assert halt_pos < reason_pos

    def test_halt_chain_with_data(self):
        chain = build_halt_chain(
            origin="payment_agent",
            action="Process_Payment",
            reason="Database connection lost",
            data_blocks=[("TXN_9987", QMSBlockType.IDENTIFIER)]
        )
        chain_str = chain.to_string()
        assert "::##TXN_9987##::" in chain_str
        assert "::%%%%::" in chain_str
        assert "::%%Database connection lost%%::" in chain_str

    def test_halt_chain_is_not_standard_command(self):
        """REM: Halt chains have no command block — halt replaces it."""
        chain = build_halt_chain(origin="test", action="Fail")
        assert chain.command is None


# REM: =======================================================================================
# REM: SECTION 5: CHAIN PARSING — STRING TO STRUCTURE
# REM: =======================================================================================

class TestParseChain:
    """REM: Tests for parse_chain() — converting chain strings to QMSChain objects."""

    def test_parse_simple_chain(self):
        chain_str = "::<test>::-::@@REQ_001@@::-::Ping::-::_Please::"
        chain = parse_chain(chain_str)
        assert chain is not None
        assert chain.origin == "test"
        assert chain.correlation_id == "REQ_001"
        assert chain.action == "Ping"
        assert chain.command == QMSStatus.PLEASE

    def test_parse_chain_with_data(self):
        chain_str = "::<backup>::-::@@REQ_002@@::-::Create_Backup::-::##ollama_data##::-::_Thank_You::"
        chain = parse_chain(chain_str)
        assert chain is not None
        assert chain.origin == "backup"
        assert chain.action == "Create_Backup"
        assert chain.command == QMSStatus.THANK_YOU
        assert len(chain.data_blocks) == 1
        assert chain.data_blocks[0].inner_value == "ollama_data"

    def test_parse_halt_chain_bare(self):
        chain_str = "::<test>::-::@@REQ_003@@::-::Fail::-::%%%%::"
        chain = parse_chain(chain_str)
        assert chain is not None
        assert chain.is_halt is True
        assert chain.halt_reason is None

    def test_parse_halt_chain_with_reason(self):
        chain_str = "::<test>::-::@@REQ_004@@::-::Fail::-::%%%%::-::%%DB crashed%%::"
        chain = parse_chain(chain_str)
        assert chain is not None
        assert chain.is_halt is True
        assert chain.halt_reason == "DB crashed"

    def test_parse_returns_none_for_empty(self):
        assert parse_chain("") is None
        assert parse_chain(None) is None

    def test_parse_returns_none_for_no_chain(self):
        assert parse_chain("just plain text with no blocks") is None

    def test_parse_preserves_raw(self):
        chain_str = "::<test>::-::@@REQ_005@@::-::Ping::-::_Please::"
        chain = parse_chain(chain_str)
        assert chain.raw == chain_str

    def test_parse_chain_embedded_in_text(self):
        """REM: Parser should find chain even if surrounded by non-chain text."""
        text = "INFO 2026-02-07 ::<agent>::-::@@REQ_006@@::-::Ping::-::_Please:: end of log"
        chain = parse_chain(text)
        assert chain is not None
        assert chain.origin == "agent"

    def test_roundtrip_build_parse(self):
        """REM: Build a chain, convert to string, parse it back — should match."""
        original = build_chain(
            origin="roundtrip_agent",
            action="Test_Action",
            status=QMSStatus.THANK_YOU,
            correlation_id="REQ_roundtrip",
            data_blocks=[("test_data", QMSBlockType.IDENTIFIER)]
        )
        parsed = parse_chain(original.to_string())
        assert parsed is not None
        assert parsed.origin == "roundtrip_agent"
        assert parsed.correlation_id == "REQ_roundtrip"
        assert parsed.action == "Test_Action"
        assert parsed.command == QMSStatus.THANK_YOU

    def test_roundtrip_halt_chain(self):
        """REM: Build halt chain, parse back — halt and reason should survive."""
        original = build_halt_chain(
            origin="halt_agent",
            action="Critical_Fail",
            reason="Memory exhausted",
            correlation_id="REQ_halt_test"
        )
        parsed = parse_chain(original.to_string())
        assert parsed is not None
        assert parsed.is_halt is True
        assert parsed.halt_reason == "Memory exhausted"
        assert parsed.origin == "halt_agent"


# REM: =======================================================================================
# REM: SECTION 6: FIND CHAINS — MULTIPLE CHAINS IN TEXT
# REM: =======================================================================================

class TestFindChains:
    """REM: Tests for find_chains() — extracting multiple chains from log text."""

    def test_find_single_chain(self):
        text = "::<agent>::-::@@REQ_001@@::-::Ping::-::_Please::"
        chains = find_chains(text)
        assert len(chains) == 1

    def test_find_multiple_chains(self):
        text = (
            "LOG: ::<agent>::-::@@REQ_001@@::-::Ping::-::_Please:: "
            "LOG: ::<agent>::-::@@REQ_001@@::-::Ping::-::_Thank_You::"
        )
        chains = find_chains(text)
        assert len(chains) == 2

    def test_find_no_chains(self):
        assert find_chains("just text no chains") == []
        assert find_chains("") == []
        assert find_chains(None) == []

    def test_find_chains_ignores_surrounding_text(self):
        text = "DEBUG noise ::<a>::-::@@REQ@@::-::Act::-::_Please:: more noise"
        chains = find_chains(text)
        assert len(chains) == 1
        assert chains[0].origin == "a"


# REM: =======================================================================================
# REM: SECTION 7: CHAIN VALIDATION — BLOCKCHAIN INTEGRITY
# REM: =======================================================================================

class TestValidateChain:
    """REM: Tests for validate_chain() — enforcing v2.1.6 spec rules."""

    def test_valid_standard_chain(self):
        chain = build_chain(origin="test", action="Ping", status=QMSStatus.PLEASE)
        result = validate_chain(chain)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_valid_halt_chain_with_reason(self):
        chain = build_halt_chain(origin="test", action="Fail", reason="broken")
        result = validate_chain(chain)
        assert result.valid is True

    def test_valid_halt_chain_bare_warns(self):
        """REM: Bare halt is valid but should produce warning recommending reason."""
        chain = build_halt_chain(origin="test", action="Fail")
        result = validate_chain(chain)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("halt_no_reason" in w for w in result.warnings)

    def test_missing_origin_is_error(self):
        """REM: Anonymous transmission — no radio callsign."""
        chain = QMSChain(blocks=[
            QMSBlock(content="@@REQ_001@@", block_type=QMSBlockType.CORRELATION),
            QMSBlock(content="Ping", block_type=QMSBlockType.GENERIC),
            QMSBlock(content="_Please", block_type=QMSBlockType.COMMAND),
        ])
        result = validate_chain(chain)
        assert result.valid is False
        assert any("missing_origin" in e for e in result.errors)

    def test_missing_correlation_is_error(self):
        """REM: Untraceable transaction."""
        chain = QMSChain(blocks=[
            QMSBlock(content="<test>", block_type=QMSBlockType.ORIGIN),
            QMSBlock(content="Ping", block_type=QMSBlockType.GENERIC),
            QMSBlock(content="_Please", block_type=QMSBlockType.COMMAND),
        ])
        result = validate_chain(chain)
        assert result.valid is False
        assert any("missing_correlation" in e for e in result.errors)

    def test_incomplete_chain_no_command(self):
        """REM: Chain without terminal command is incomplete thought."""
        chain = QMSChain(blocks=[
            QMSBlock(content="<test>", block_type=QMSBlockType.ORIGIN),
            QMSBlock(content="@@REQ_001@@", block_type=QMSBlockType.CORRELATION),
            QMSBlock(content="Ping", block_type=QMSBlockType.GENERIC),
        ])
        result = validate_chain(chain)
        assert result.valid is False
        assert any("incomplete_chain" in e for e in result.errors)

    def test_invalid_command_suffix(self):
        """REM: Unrecognized command block should fail."""
        chain = QMSChain(blocks=[
            QMSBlock(content="<test>", block_type=QMSBlockType.ORIGIN),
            QMSBlock(content="@@REQ_001@@", block_type=QMSBlockType.CORRELATION),
            QMSBlock(content="Ping", block_type=QMSBlockType.GENERIC),
            QMSBlock(content="_InvalidCommand", block_type=QMSBlockType.COMMAND),
        ])
        result = validate_chain(chain)
        assert result.valid is False
        assert any("invalid_command" in e for e in result.errors)

    def test_halt_with_wrong_postscript_type(self):
        """REM: Only %%...%% may follow %%%%."""
        chain = QMSChain(blocks=[
            QMSBlock(content="<test>", block_type=QMSBlockType.ORIGIN),
            QMSBlock(content="@@REQ_001@@", block_type=QMSBlockType.CORRELATION),
            QMSBlock(content="Fail", block_type=QMSBlockType.GENERIC),
            QMSBlock(content="%%%%", block_type=QMSBlockType.SYSTEM_HALT),
            QMSBlock(content="##wrong_type##", block_type=QMSBlockType.IDENTIFIER),
        ])
        result = validate_chain(chain)
        assert result.valid is False
        assert any("halt_invalid_postscript" in e for e in result.errors)

    def test_halt_with_excess_blocks(self):
        """REM: Only ONE block may follow %%%%."""
        chain = QMSChain(blocks=[
            QMSBlock(content="<test>", block_type=QMSBlockType.ORIGIN),
            QMSBlock(content="@@REQ_001@@", block_type=QMSBlockType.CORRELATION),
            QMSBlock(content="Fail", block_type=QMSBlockType.GENERIC),
            QMSBlock(content="%%%%", block_type=QMSBlockType.SYSTEM_HALT),
            QMSBlock(content="%%reason1%%", block_type=QMSBlockType.STRING),
            QMSBlock(content="%%reason2%%", block_type=QMSBlockType.STRING),
        ])
        result = validate_chain(chain)
        assert result.valid is False
        assert any("halt_excess_blocks" in e for e in result.errors)

    def test_empty_chain_is_invalid(self):
        chain = QMSChain(blocks=[])
        result = validate_chain(chain)
        assert result.valid is False

    def test_none_chain_is_invalid(self):
        result = validate_chain(None)
        assert result.valid is False


# REM: =======================================================================================
# REM: SECTION 8: SECURITY FLAGGING — ANONYMOUS TRANSMISSION DETECTION
# REM: =======================================================================================

class TestSecurityFlagging:
    """REM: Tests for is_chain_formatted() and validate_chain_string()."""

    def test_is_chain_formatted_detects_origin(self):
        assert is_chain_formatted("::<agent>::-::@@REQ@@::-::Ping::-::_Please::") is True

    def test_is_chain_formatted_rejects_no_origin(self):
        assert is_chain_formatted("::Ping::-::_Please::") is False

    def test_is_chain_formatted_rejects_empty(self):
        assert is_chain_formatted("") is False
        assert is_chain_formatted(None) is False

    def test_is_chain_formatted_rejects_plain_text(self):
        assert is_chain_formatted("just a regular log message") is False

    def test_is_chain_formatted_rejects_legacy_format(self):
        """REM: Legacy suffix format should not be detected as formal chain."""
        assert is_chain_formatted("Create_Backup_Please ::volume=ollama_data::") is False

    def test_validate_chain_string_valid(self):
        chain_str = "::<agent>::-::@@REQ_001@@::-::Ping::-::_Please::"
        is_valid, result = validate_chain_string(chain_str, log_warning=False)
        assert is_valid is True
        assert result is not None
        assert result.valid is True

    def test_validate_chain_string_missing_chain(self):
        is_valid, result = validate_chain_string("no chain here", log_warning=False)
        assert is_valid is False
        assert result is None

    def test_validate_chain_string_anonymous(self):
        """REM: Chain without origin should be flaggable."""
        chain_str = "::@@REQ_001@@::-::Ping::-::_Please::"
        is_valid, result = validate_chain_string(chain_str, log_warning=False)
        assert is_valid is False
        assert result is not None
        assert any("missing_origin" in e for e in result.errors)


# REM: =======================================================================================
# REM: SECTION 9: QMS CHAIN PROPERTIES — DATA ACCESS
# REM: =======================================================================================

class TestChainProperties:
    """REM: Tests for QMSChain property accessors."""

    def test_data_blocks_extraction(self):
        chain = build_chain(
            origin="test",
            action="Action",
            status=QMSStatus.PLEASE,
            data_blocks=[
                ("value1", QMSBlockType.IDENTIFIER),
                ("value2", QMSBlockType.STRING),
            ]
        )
        data = chain.data_blocks
        assert len(data) == 2
        assert data[0].inner_value == "value1"
        assert data[1].inner_value == "value2"

    def test_data_blocks_empty_when_none(self):
        chain = build_chain(origin="test", action="Ping", status=QMSStatus.PLEASE)
        assert chain.data_blocks == []

    def test_origin_none_when_missing(self):
        chain = QMSChain(blocks=[
            QMSBlock(content="Ping", block_type=QMSBlockType.GENERIC),
        ])
        assert chain.origin is None

    def test_correlation_none_when_missing(self):
        chain = QMSChain(blocks=[
            QMSBlock(content="<test>", block_type=QMSBlockType.ORIGIN),
        ])
        assert chain.correlation_id is None

    def test_command_none_when_halt(self):
        chain = build_halt_chain(origin="test", action="Fail")
        assert chain.command is None

    def test_is_halt_false_for_standard(self):
        chain = build_chain(origin="test", action="Ping", status=QMSStatus.PLEASE)
        assert chain.is_halt is False

    def test_halt_reason_none_for_standard(self):
        chain = build_chain(origin="test", action="Ping", status=QMSStatus.PLEASE)
        assert chain.halt_reason is None


# REM: =======================================================================================
# REM: SECTION 10: QUALIFIER WRAPPING — INTERNAL HELPER
# REM: =======================================================================================

class TestWrapQualifier:
    """REM: Tests for _wrap_qualifier() — ensuring correct marker pairs."""

    def test_wrap_origin(self):
        assert _wrap_qualifier("agent", QMSBlockType.ORIGIN) == "<agent>"

    def test_wrap_correlation(self):
        assert _wrap_qualifier("REQ_001", QMSBlockType.CORRELATION) == "@@REQ_001@@"

    def test_wrap_numeric(self):
        assert _wrap_qualifier("49.99", QMSBlockType.NUMERIC) == "$$49.99$$"

    def test_wrap_identifier(self):
        assert _wrap_qualifier("USER_123", QMSBlockType.IDENTIFIER) == "##USER_123##"

    def test_wrap_string(self):
        assert _wrap_qualifier("Error msg", QMSBlockType.STRING) == "%%Error msg%%"

    def test_wrap_query(self):
        assert _wrap_qualifier("What path?", QMSBlockType.QUERY) == "??What path???"

    def test_wrap_version(self):
        assert _wrap_qualifier("QMS_v2.1.6", QMSBlockType.VERSION) == "&&QMS_v2.1.6&&"

    def test_wrap_encrypted(self):
        assert _wrap_qualifier("abc123", QMSBlockType.ENCRYPTED) == "||abc123||"

    def test_wrap_command(self):
        assert _wrap_qualifier("Please", QMSBlockType.COMMAND) == "_Please"

    def test_wrap_halt(self):
        assert _wrap_qualifier("", QMSBlockType.SYSTEM_HALT) == "%%%%"

    def test_wrap_generic(self):
        assert _wrap_qualifier("Action", QMSBlockType.GENERIC) == "Action"


# REM: =======================================================================================
# REM: SECTION 11: LEGACY COMPATIBILITY — EXISTING FUNCTIONS STILL WORK
# REM: =======================================================================================

class TestLegacyCompatibility:
    """REM: Tests that legacy QMS functions still work alongside formal chains."""

    def test_format_qms_legacy(self):
        result = format_qms("Create_Backup", QMSStatus.PLEASE, volume="ollama_data")
        assert "Create_Backup_Please" in result
        assert "::volume=ollama_data::" in result

    def test_parse_qms_legacy(self):
        msg = "Create_Backup_Please ::volume=ollama_data::"
        parsed = parse_qms(msg)
        assert parsed is not None
        assert parsed.action == "Create_Backup"
        assert parsed.status == QMSStatus.PLEASE

    def test_format_qms_response_success(self):
        result = format_qms_response("Backup", True)
        assert "Backup_Thank_You" in result

    def test_format_qms_response_failure(self):
        result = format_qms_response("Backup", False)
        assert "Backup_Thank_You_But_No" in result

    def test_is_qms_formatted_detects_legacy(self):
        assert is_qms_formatted("Create_Backup_Please ::volume=data::") is True

    def test_is_qms_formatted_detects_formal(self):
        assert is_qms_formatted("::<agent>::-::@@REQ@@::-::Ping::-::_Please::") is True

    def test_is_qms_formatted_rejects_plain(self):
        assert is_qms_formatted("no QMS here") is False

    def test_validate_qms_accepts_both_formats(self):
        valid_legacy, _ = validate_qms("Action_Please", log_warning=False)
        assert valid_legacy is True

        valid_chain, _ = validate_qms(
            "::<a>::-::@@REQ@@::-::Act::-::_Please::", log_warning=False
        )
        assert valid_chain is True

    def test_validate_qms_rejects_plain(self):
        valid, warning = validate_qms("plain text", log_warning=False)
        assert valid is False
        assert warning is not None


# REM: =======================================================================================
# REM: SECTION 12: CONSTANTS AND ENUMS — SPEC ALIGNMENT
# REM: =======================================================================================

class TestConstantsAndEnums:
    """REM: Tests that constants match the v2.1.6 specification."""

    def test_system_halt_constant(self):
        assert SYSTEM_HALT == "%%%%"

    def test_system_halt_block_constant(self):
        assert SYSTEM_HALT_BLOCK == "::%%%%::"

    def test_all_qms_statuses_present(self):
        expected = {"Please", "Thank_You", "Thank_You_But_No", "Excuse_Me", "Pretty_Please"}
        actual = {s.value for s in QMSStatus}
        assert actual == expected

    def test_block_type_origin_qualifier(self):
        assert QMSBlockType.ORIGIN.value == "<>"

    def test_block_type_correlation_qualifier(self):
        assert QMSBlockType.CORRELATION.value == "@@"

    def test_block_type_halt_qualifier(self):
        assert QMSBlockType.SYSTEM_HALT.value == "%%%%"

    def test_qms_status_enum_values(self):
        """REM: Ensure enum string values match command block content exactly."""
        assert QMSStatus.PLEASE.value == "Please"
        assert QMSStatus.THANK_YOU.value == "Thank_You"
        assert QMSStatus.THANK_YOU_BUT_NO.value == "Thank_You_But_No"
        assert QMSStatus.EXCUSE_ME.value == "Excuse_Me"
        assert QMSStatus.PRETTY_PLEASE.value == "Pretty_Please"


# REM: =======================================================================================
# REM: SECTION 13: FULL CHAIN STRING EXAMPLES — SPEC COMPLIANCE
# REM: =======================================================================================

class TestSpecExamples:
    """REM: Tests that reproduce exact examples from the QMS v2.1.6 specification."""

    def test_spec_example_ping(self):
        chain = build_chain(
            origin="monitor_agent",
            action="Ping",
            status=QMSStatus.PLEASE,
            correlation_id="REQ_0001aa00"
        )
        expected = "::<monitor_agent>::-::@@REQ_0001aa00@@::-::Ping::-::_Please::"
        assert chain.to_string() == expected

    def test_spec_example_halt_with_reason(self):
        chain = build_halt_chain(
            origin="payment_agent",
            action="Process_Payment",
            reason="Database connection lost",
            correlation_id="REQ_e5f6a7b8",
            data_blocks=[
                ("TXN_9987", QMSBlockType.IDENTIFIER),
                ("15000", QMSBlockType.NUMERIC),
            ]
        )
        # REM: v2.2.0 — Halt chains default to URGENT priority (prepended as first block)
        expected = (
            "::!URGENT!::-::<payment_agent>::-::@@REQ_e5f6a7b8@@::-::Process_Payment::"
            "-::##TXN_9987##::-::$$15000$$::-::%%%%::-::%%Database connection lost%%::"
        )
        assert chain.to_string() == expected

    def test_spec_example_graceful_failure(self):
        chain = build_chain(
            origin="file_agent",
            action="Delete_File",
            status=QMSStatus.THANK_YOU_BUT_NO,
            correlation_id="REQ_d1e2f3a4",
            data_blocks=[
                ("/etc/system.conf", QMSBlockType.IDENTIFIER),
                ("Permission Denied: Critical System File", QMSBlockType.STRING),
            ]
        )
        expected = (
            "::<file_agent>::-::@@REQ_d1e2f3a4@@::-::Delete_File::"
            "-::##/etc/system.conf##::-::%%Permission Denied: Critical System File%%::"
            "-::_Thank_You_But_No::"
        )
        assert chain.to_string() == expected

    def test_spec_example_clarification(self):
        chain = build_chain(
            origin="archive_agent",
            action="Create_Archive",
            status=QMSStatus.EXCUSE_ME,
            correlation_id="REQ_c7d8e9f0",
            data_blocks=[
                ("Specify_Filename_and_Path", QMSBlockType.QUERY),
            ]
        )
        expected = (
            "::<archive_agent>::-::@@REQ_c7d8e9f0@@::-::Create_Archive::"
            "-::??Specify_Filename_and_Path??::-::_Excuse_Me::"
        )
        assert chain.to_string() == expected
