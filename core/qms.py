# TelsonBase/core/qms.py
# REM: =======================================================================================
# REM: QUIETFIRE MESSAGE STANDARD (QMS) v2.2.0 — AI AUDIT CHAIN PROTOCOL
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: QMS is both a governance primitive and a security watermark for
# REM: TelsonBase communications. Every message passing through the platform carries QMS
# REM: formatting. Messages without it are flagged as suspicious — they bypassed normal
# REM: channels.
# REM:
# REM: This provides a SECOND LAYER of verification beyond cryptographic signatures:
# REM:   1. Signature = WHO sent the message (identity)
# REM:   2. QMS format = HOW it got here (provenance)
# REM:
# REM: A compromised agent might steal signing keys, but if it injects raw commands
# REM: without QMS formatting, the system flags the anomaly. The attacker would need
# REM: to understand internal message semantics AND have valid keys.
# REM:
# REM: QMS v2.2.0 Formal Chain Syntax:
# REM:   [::!PRIORITY!::-]::<ORIGIN>::-::@@CORRELATION[@@TTL_Ns]@@::-::ACTION::-::DATA::-::COMMAND::
# REM:
# REM: v2.2.0 additions (backward compatible):
# REM:   - Priority prefix: ::!URGENT!:: or ::!P1!:: before the origin block
# REM:     A SECURITY_ALERT halt should preempt a Tool_Checkout_Please.
# REM:   - Correlation TTL: ::@@REQ_id@@TTL_30s@@:: — agents know when to stop waiting
# REM:     Prevents hung agent states on unanswered requests.
# REM:   - Schema registry: qms_schema.json defines valid message structures.
# REM:     "Is this a valid Tool_Checkout_Please?" becomes a schema check, not a regex.
# REM:
# REM: Example (v2.1.6 — still valid):
# REM:   ::<backup_agent>::-::@@REQ_a8f3c2@@::-::Create_Backup::-::##ollama_data##::-::_Please::
# REM:
# REM: Example (v2.2.0 — with priority and TTL):
# REM:   ::!P1!::-::<backup_agent>::-::@@REQ_a8f3c2@@TTL_30s@@::-::Create_Backup::-::_Please::
# REM:
# REM: Halt Postscript Pattern:
# REM:   ...::-::%%%%::-::%%reason%%::
# REM:   The siren fires first. The incident report follows.
# REM:
# REM: BACKWARD COMPATIBILITY: Legacy functions (format_qms, parse_qms, etc.) are
# REM: preserved. New chain functions (build_chain, parse_chain, validate_chain) operate
# REM: alongside them. Migration is incremental — agents adopt formal chains at their
# REM: own pace. v2.1.6 chains without priority or TTL remain fully valid.
# REM: =======================================================================================

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: ENUMS — BLOCK TYPES AND COMMAND STATUS
# REM: =======================================================================================

class QMSStatus(str, Enum):
    """
    REM: QMS Command Block suffixes.
    REM: These are the five transaction terminators that end every standard chain.
    """
    PLEASE = "Please"                       # Request / Action Initiation
    THANK_YOU = "Thank_You"                 # Successful Completion
    THANK_YOU_BUT_NO = "Thank_You_But_No"   # Unsuccessful / Graceful Refusal
    EXCUSE_ME = "Excuse_Me"                 # Need Clarification
    PRETTY_PLEASE = "Pretty_Please"         # High Priority Request


class QMSBlockType(str, Enum):
    """
    REM: QMS v2.2.0 block qualifier types.
    REM: Each qualifier has a specific symbol pair that wraps content inside :: delimiters.
    """
    PRIORITY = "!!"         # v2.2.0: Message priority: ::!URGENT!:: ::!P1!::
    ORIGIN = "<>"           # Agent callsign: ::<agent_id>::
    CORRELATION = "@@"      # Transaction thread: ::@@REQ_id@@:: or ::@@REQ_id@@TTL_30s@@::
    GENERIC = ""            # Unqualified: ::Action_Name::
    NUMERIC = "$$"          # Numbers/financial: ::$$49.99$$::
    IDENTIFIER = "##"       # IDs/paths/booleans: ::##USER_123##::
    STRING = "%%"           # Human text/errors: ::%%Permission Denied%%::
    QUERY = "??"            # Ambiguity/questions: ::??Specify_Path??::
    VERSION = "&&"          # Protocol version: ::&&QMS_v2.2.0&&::
    ENCRYPTED = "||"        # Hashes/encrypted: ::||a746fg2e||::
    COMMAND = "_"           # Command blocks: ::_Please::
    SYSTEM_HALT = "%%%%"    # Catastrophic failure: ::%%%%::


# REM: Preserve legacy enum for backward compatibility
class QMSFieldType(str, Enum):
    """
    REM: Legacy field marker types. Preserved for backward compatibility.
    REM: New code should use QMSBlockType instead.
    """
    CRITICAL = "::"     # Critical field / key data
    PRIORITY = "$$"     # Priority or financial value
    POLICY = "##"       # Policy or rule ID
    TARGET = "@@"       # Agent target or entity reference
    QUESTION = "??"     # Point of uncertainty


# REM: =======================================================================================
# REM: CONSTANTS
# REM: =======================================================================================

SYSTEM_HALT = "%%%%"
SYSTEM_HALT_BLOCK = f"::{SYSTEM_HALT}::"

COMMAND_SUFFIXES = {s.value for s in QMSStatus}

BLOCK_OPEN = "::"
BLOCK_CLOSE = "::"
CHAIN_SEPARATOR = "-"

# REM: =======================================================================================
# REM: v2.2.0 — PRIORITY LEVELS AND CORRELATION TTL
# REM: =======================================================================================

# REM: Valid priority levels — URGENT preempts all, P3 is background
PRIORITY_LEVELS = {"URGENT", "P1", "P2", "P3"}

# REM: Default priority when none specified
DEFAULT_PRIORITY = "P2"

# REM: Regex to extract TTL from correlation block content: @@REQ_id@@TTL_30s@@
# REM: The TTL is embedded inside the correlation markers, after the ID.
CORRELATION_TTL_PATTERN = re.compile(r'^@@(.+?)@@TTL_(\d+)s@@$')

# REM: Default TTL by priority (seconds) — matches qms_schema.json
DEFAULT_TTL_BY_PRIORITY = {
    "URGENT": 10,
    "P1": 30,
    "P2": 120,
    "P3": 600,
}


# REM: =======================================================================================
# REM: DATACLASSES — FORMAL CHAIN STRUCTURES
# REM: =======================================================================================

@dataclass
class QMSBlock:
    """
    REM: A single QMS Block — the atomic unit.
    REM: Contains the raw content and its detected type.
    """
    content: str
    block_type: QMSBlockType = QMSBlockType.GENERIC

    def to_string(self) -> str:
        """REM: Render this block as a ::CONTENT:: string."""
        return f"::{self.content}::"

    @property
    def inner_value(self) -> str:
        """REM: Extract the value inside qualifier markers."""
        content = self.content
        if self.block_type == QMSBlockType.PRIORITY:
            return content.lstrip("!").rstrip("!")
        elif self.block_type == QMSBlockType.ORIGIN:
            return content.lstrip("<").rstrip(">")
        elif self.block_type == QMSBlockType.SYSTEM_HALT:
            return ""
        elif self.block_type == QMSBlockType.COMMAND:
            return content.lstrip("_")
        elif self.block_type == QMSBlockType.GENERIC:
            return content
        else:
            # REM: Strip qualifier pair ($$, ##, %%, etc.)
            marker = self.block_type.value
            if len(marker) == 2 and content.startswith(marker) and content.endswith(marker):
                return content[len(marker):-len(marker)]
            return content


@dataclass
class QMSChain:
    """
    REM: A complete QMS Instruction Chain — linked blocks forming a transactional thought.
    REM:
    REM: Canonical structure (v2.2.0):
    REM:   Position 0: Priority     ::!P1!::            (optional, v2.2.0)
    REM:   Position 1: Origin       ::<agent_id>::
    REM:   Position 2: Correlation  ::@@REQ_id@@::      (or ::@@REQ_id@@TTL_30s@@::)
    REM:   Position 3: Action       ::Action_Name::
    REM:   Position 4+: Data        (optional data blocks)
    REM:   Terminal:   Command      ::_Please:: (or halt pattern)
    REM:
    REM: Halt pattern:
    REM:   ...::-::%%%%::                        (siren only)
    REM:   ...::-::%%%%::-::%%reason%%::          (siren + incident report)
    """
    blocks: List[QMSBlock]
    raw: str = ""

    @property
    def _offset(self) -> int:
        """REM: v2.2.0 — Position offset when priority prefix is present (0 or 1)."""
        if self.blocks and self.blocks[0].block_type == QMSBlockType.PRIORITY:
            return 1
        return 0

    @property
    def priority(self) -> Optional[str]:
        """REM: v2.2.0 — Extract message priority level (URGENT, P1, P2, P3). None if absent."""
        if self.blocks and self.blocks[0].block_type == QMSBlockType.PRIORITY:
            return self.blocks[0].inner_value
        return None

    @property
    def origin(self) -> Optional[str]:
        """REM: Extract agent callsign from position 1 (or 2 if priority prefix present)."""
        idx = self._offset
        if len(self.blocks) > idx and self.blocks[idx].block_type == QMSBlockType.ORIGIN:
            return self.blocks[idx].inner_value
        return None

    @property
    def correlation_id(self) -> Optional[str]:
        """REM: Extract transaction thread ID from position 2 (or 3 with priority)."""
        idx = self._offset + 1
        if len(self.blocks) > idx and self.blocks[idx].block_type == QMSBlockType.CORRELATION:
            raw_value = self.blocks[idx].inner_value
            # REM: v2.2.0 — Strip TTL suffix if present (REQ_id@@TTL_30s → REQ_id)
            ttl_match = CORRELATION_TTL_PATTERN.match(self.blocks[idx].content)
            if ttl_match:
                return ttl_match.group(1)
            return raw_value
        return None

    @property
    def ttl_seconds(self) -> Optional[int]:
        """
        REM: v2.2.0 — Extract TTL from correlation block.
        REM: Pattern: ::@@REQ_id@@TTL_30s@@:: → 30
        REM: Returns None if no TTL specified (backward compatible).
        """
        idx = self._offset + 1
        if len(self.blocks) > idx and self.blocks[idx].block_type == QMSBlockType.CORRELATION:
            ttl_match = CORRELATION_TTL_PATTERN.match(self.blocks[idx].content)
            if ttl_match:
                return int(ttl_match.group(2))
        return None

    @property
    def action(self) -> Optional[str]:
        """REM: Extract action name from position 3 (or 4 with priority)."""
        idx = self._offset + 2
        if len(self.blocks) > idx and self.blocks[idx].block_type == QMSBlockType.GENERIC:
            return self.blocks[idx].content
        return None

    @property
    def command(self) -> Optional[QMSStatus]:
        """REM: Extract command status from the terminal block."""
        if not self.blocks:
            return None
        # REM: For standard chains, last block is command
        last = self.blocks[-1]
        if last.block_type == QMSBlockType.COMMAND:
            try:
                return QMSStatus(last.inner_value)
            except ValueError:
                return None
        return None

    @property
    def is_halt(self) -> bool:
        """REM: Check if this chain contains a System Halt."""
        return any(b.block_type == QMSBlockType.SYSTEM_HALT for b in self.blocks)

    @property
    def halt_reason(self) -> Optional[str]:
        """
        REM: Extract halt reason — the %%...%% block immediately AFTER ::%%%%::
        REM: Convention: the siren fires, then the incident report follows.
        REM: Pattern: ...::-::%%%%::-::%%reason%%::
        """
        for i, block in enumerate(self.blocks):
            if block.block_type == QMSBlockType.SYSTEM_HALT:
                # REM: Check if next block is a string (reason postscript)
                if i + 1 < len(self.blocks):
                    next_block = self.blocks[i + 1]
                    if next_block.block_type == QMSBlockType.STRING:
                        return next_block.inner_value
                return None
        return None

    @property
    def data_blocks(self) -> List[QMSBlock]:
        """REM: All data blocks between action and terminal."""
        data_start = self._offset + 3  # After origin, correlation, action
        if len(self.blocks) <= data_start + 1:
            return []
        # REM: Find where data ends (before command, halt, or halt+reason)
        end_idx = len(self.blocks) - 1
        if self.is_halt:
            # REM: Find the halt position — data is before it
            for i, b in enumerate(self.blocks):
                if b.block_type == QMSBlockType.SYSTEM_HALT:
                    end_idx = i
                    break
        return self.blocks[data_start:end_idx]

    def to_string(self) -> str:
        """REM: Render the complete chain as a dash-separated block string."""
        return CHAIN_SEPARATOR.join(b.to_string() for b in self.blocks)


# REM: Preserve legacy dataclass for backward compatibility
@dataclass
class QMSMessage:
    """
    REM: Legacy parsed QMS message structure.
    REM: Preserved for backward compatibility with existing code.
    REM: New code should use QMSChain instead.
    """
    action: str
    status: QMSStatus
    fields: Dict[str, Any]
    raw: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

    def to_string(self) -> str:
        """REM: Reconstruct the legacy QMS formatted string."""
        return format_qms(self.action, self.status, **self.fields)


# REM: =======================================================================================
# REM: BLOCK DETECTION
# REM: =======================================================================================

def _detect_block_type(content: str) -> QMSBlockType:
    """
    REM: Detect the qualifier type from block content.
    REM: Checks prefix/suffix characters to determine block type.
    """
    if content == SYSTEM_HALT:
        return QMSBlockType.SYSTEM_HALT
    # REM: v2.2.0 — Priority block: ::!URGENT!:: or ::!P1!::
    if content.startswith("!") and content.endswith("!") and len(content) > 2:
        return QMSBlockType.PRIORITY
    if content.startswith("<") and content.endswith(">"):
        return QMSBlockType.ORIGIN
    if content.startswith("@@") and content.endswith("@@") and len(content) > 4:
        return QMSBlockType.CORRELATION
    if content.startswith("_") and content.lstrip("_") in COMMAND_SUFFIXES:
        return QMSBlockType.COMMAND
    if content.startswith("$$") and content.endswith("$$") and len(content) > 4:
        return QMSBlockType.NUMERIC
    if content.startswith("##") and content.endswith("##") and len(content) > 4:
        return QMSBlockType.IDENTIFIER
    if content.startswith("%%") and content.endswith("%%") and len(content) > 4:
        return QMSBlockType.STRING
    if content.startswith("??") and content.endswith("??") and len(content) > 4:
        return QMSBlockType.QUERY
    if content.startswith("&&") and content.endswith("&&") and len(content) > 4:
        return QMSBlockType.VERSION
    if content.startswith("||") and content.endswith("||") and len(content) > 4:
        return QMSBlockType.ENCRYPTED
    return QMSBlockType.GENERIC


def _make_block(content: str) -> QMSBlock:
    """REM: Create a QMSBlock with auto-detected type."""
    return QMSBlock(content=content, block_type=_detect_block_type(content))


def _wrap_qualifier(value: str, block_type: QMSBlockType) -> str:
    """REM: Wrap a value in its qualifier markers."""
    if block_type == QMSBlockType.PRIORITY:
        return f"!{value}!"
    elif block_type == QMSBlockType.ORIGIN:
        return f"<{value}>"
    elif block_type == QMSBlockType.CORRELATION:
        return f"@@{value}@@"
    elif block_type == QMSBlockType.NUMERIC:
        return f"$${value}$$"
    elif block_type == QMSBlockType.IDENTIFIER:
        return f"##{value}##"
    elif block_type == QMSBlockType.STRING:
        return f"%%{value}%%"
    elif block_type == QMSBlockType.QUERY:
        return f"??{value}??"
    elif block_type == QMSBlockType.VERSION:
        return f"&&{value}&&"
    elif block_type == QMSBlockType.ENCRYPTED:
        return f"||{value}||"
    elif block_type == QMSBlockType.COMMAND:
        return f"_{value}"
    elif block_type == QMSBlockType.SYSTEM_HALT:
        return SYSTEM_HALT
    return value


# REM: =======================================================================================
# REM: CHAIN BUILDING — FORMAL v2.1.6 SYNTAX
# REM: =======================================================================================

def build_chain(
    origin: str,
    action: str,
    status: QMSStatus,
    correlation_id: str = None,
    data_blocks: List[Tuple[str, QMSBlockType]] = None,
    priority: str = None,
    ttl_seconds: int = None,
) -> QMSChain:
    """
    REM: Build a formal QMS v2.2.0 Instruction Chain.

    Args:
        origin: Agent callsign (e.g., "backup_agent", "alpha/sync_agent")
        action: Action name (e.g., "Create_Backup", "Tool_Checkout")
        status: QMSStatus command to terminate the chain
        correlation_id: Transaction thread ID. Auto-generated if None.
        data_blocks: Optional list of (value, QMSBlockType) tuples for data
        priority: v2.2.0 — Message priority ("URGENT", "P1", "P2", "P3"). None = no prefix.
        ttl_seconds: v2.2.0 — Correlation timeout in seconds. None = no TTL.

    Returns:
        QMSChain with all blocks assembled in canonical order

    Example (v2.1.6 compatible):
        chain = build_chain(
            origin="backup_agent",
            action="Create_Backup",
            status=QMSStatus.PLEASE,
            data_blocks=[("ollama_data", QMSBlockType.IDENTIFIER)]
        )
        # ::<backup_agent>::-::@@REQ_xxxxxxxx@@::-::Create_Backup::-::##ollama_data##::-::_Please::

    Example (v2.2.0 with priority and TTL):
        chain = build_chain(
            origin="backup_agent",
            action="Create_Backup",
            status=QMSStatus.PLEASE,
            priority="P1",
            ttl_seconds=30
        )
        # ::!P1!::-::<backup_agent>::-::@@REQ_xxxxxxxx@@TTL_30s@@::-::Create_Backup::-::_Please::
    """
    if correlation_id is None:
        correlation_id = f"REQ_{uuid.uuid4().hex[:8]}"

    blocks = []

    # REM: v2.2.0 — Optional priority prefix (position 0, before origin)
    if priority:
        priority_upper = priority.upper()
        if priority_upper not in PRIORITY_LEVELS:
            logger.warning(
                f"QMS_INVALID_PRIORITY: '{priority}' not in {PRIORITY_LEVELS}. "
                f"Defaulting to {DEFAULT_PRIORITY}."
            )
            priority_upper = DEFAULT_PRIORITY
        blocks.append(QMSBlock(
            content=f"!{priority_upper}!",
            block_type=QMSBlockType.PRIORITY
        ))

    blocks.append(
        QMSBlock(content=f"<{origin}>", block_type=QMSBlockType.ORIGIN)
    )

    # REM: v2.2.0 — Correlation with optional TTL suffix
    if ttl_seconds and ttl_seconds > 0:
        corr_content = f"@@{correlation_id}@@TTL_{ttl_seconds}s@@"
    else:
        corr_content = f"@@{correlation_id}@@"
    blocks.append(
        QMSBlock(content=corr_content, block_type=QMSBlockType.CORRELATION)
    )

    blocks.append(
        QMSBlock(content=action, block_type=QMSBlockType.GENERIC)
    )

    if data_blocks:
        for value, btype in data_blocks:
            wrapped = _wrap_qualifier(value, btype)
            blocks.append(QMSBlock(content=wrapped, block_type=btype))

    # REM: Terminal command block
    blocks.append(QMSBlock(
        content=f"_{status.value}",
        block_type=QMSBlockType.COMMAND
    ))

    chain = QMSChain(blocks=blocks)
    chain.raw = chain.to_string()
    return chain


def build_halt_chain(
    origin: str,
    action: str,
    reason: str = None,
    correlation_id: str = None,
    data_blocks: List[Tuple[str, QMSBlockType]] = None,
    priority: str = None,
) -> QMSChain:
    """
    REM: Build a QMS chain terminated by System Halt.
    REM:
    REM: The halt is the siren — ::%%%%:: fires first.
    REM: The reason is the incident report — ::%%reason%%:: follows as postscript.
    REM:
    REM: Pattern: ...::-::%%%%::-::%%reason%%::

    Args:
        origin: Agent callsign
        action: Action that failed catastrophically
        reason: Human-readable cause of halt (recommended, follows the siren)
        correlation_id: Transaction thread ID. Auto-generated if None.
        data_blocks: Optional data blocks before the halt
        priority: v2.2.0 — Message priority. Halts default to "URGENT" if not specified.

    Returns:
        QMSChain ending with ::%%%%:: (optionally followed by ::%%reason%%::)

    Example:
        chain = build_halt_chain(
            origin="payment_agent",
            action="Process_Payment",
            reason="Database connection lost",
            data_blocks=[("TXN_9987", QMSBlockType.IDENTIFIER)]
        )
        # ::!URGENT!::-::<payment_agent>::-::@@REQ_xx@@::-::Process_Payment::-::##TXN_9987##::-::%%%%::-::%%Database connection lost%%::
    """
    if correlation_id is None:
        correlation_id = f"REQ_{uuid.uuid4().hex[:8]}"

    # REM: v2.2.0 — Halts default to URGENT priority (they're emergencies)
    effective_priority = priority or "URGENT"

    blocks = []

    if effective_priority:
        priority_upper = effective_priority.upper()
        if priority_upper not in PRIORITY_LEVELS:
            priority_upper = "URGENT"
        blocks.append(QMSBlock(
            content=f"!{priority_upper}!",
            block_type=QMSBlockType.PRIORITY
        ))

    blocks.extend([
        QMSBlock(content=f"<{origin}>", block_type=QMSBlockType.ORIGIN),
        QMSBlock(content=f"@@{correlation_id}@@", block_type=QMSBlockType.CORRELATION),
        QMSBlock(content=action, block_type=QMSBlockType.GENERIC),
    ])

    if data_blocks:
        for value, btype in data_blocks:
            wrapped = _wrap_qualifier(value, btype)
            blocks.append(QMSBlock(content=wrapped, block_type=btype))

    # REM: System Halt — the siren fires
    blocks.append(QMSBlock(content=SYSTEM_HALT, block_type=QMSBlockType.SYSTEM_HALT))

    # REM: Halt postscript — the incident report follows the siren (v2.1.6 convention)
    if reason:
        blocks.append(QMSBlock(content=f"%%{reason}%%", block_type=QMSBlockType.STRING))

    chain = QMSChain(blocks=blocks)
    chain.raw = chain.to_string()
    return chain


# REM: =======================================================================================
# REM: CHAIN PARSING — FORMAL v2.1.6 SYNTAX
# REM: =======================================================================================

# REM: Regex to find complete chains in text.
# REM: A chain is: ::CONTENT:: optionally followed by -::CONTENT:: repeating.
# REM: v5.3.0CC fix: [^:]+ changed to [^:]+(?::[^:]+)* to allow colons inside blocks
# REM: (e.g., URLs like http://example.com). The pattern still stops at :: boundaries.
CHAIN_PATTERN = re.compile(
    r'::[^:]+(?::[^:]+)*::(?:-::[^:]+(?::[^:]+)*::)*'
)

# REM: Pattern to extract individual block contents from a chain string
BLOCK_CONTENT_PATTERN = re.compile(r'::([^:]+(?::[^:]+)*)::')


def parse_chain(chain_string: str) -> Optional[QMSChain]:
    """
    REM: Parse a formal QMS v2.1.6 Instruction Chain string into a QMSChain.

    Args:
        chain_string: A string containing a QMS chain
            e.g. "::<backup_agent>::-::@@REQ_01@@::-::Ping::-::_Please::"

    Returns:
        QMSChain if valid chain found, None otherwise
    """
    if not chain_string or not isinstance(chain_string, str):
        return None

    match = CHAIN_PATTERN.search(chain_string)
    if not match:
        return None

    raw = match.group(0)

    block_contents = BLOCK_CONTENT_PATTERN.findall(raw)
    if not block_contents:
        return None

    blocks = [_make_block(content) for content in block_contents]

    return QMSChain(blocks=blocks, raw=raw)


def find_chains(text: str) -> List[QMSChain]:
    """
    REM: Find ALL valid QMS chains in a block of text (e.g., a log file).
    REM: Text outside chains is ignored per spec.

    Args:
        text: Text that may contain one or more QMS chains

    Returns:
        List of QMSChain objects found in the text
    """
    if not text or not isinstance(text, str):
        return []

    chains = []
    for match in CHAIN_PATTERN.finditer(text):
        raw = match.group(0)
        block_contents = BLOCK_CONTENT_PATTERN.findall(raw)
        if block_contents:
            blocks = [_make_block(content) for content in block_contents]
            chains.append(QMSChain(blocks=blocks, raw=raw))

    return chains


# REM: =======================================================================================
# REM: CHAIN VALIDATION — "BLOCKCHAIN" INTEGRITY
# REM: =======================================================================================

@dataclass
class QMSValidationResult:
    """REM: Result of chain validation with specific error details."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_chain(chain: QMSChain) -> QMSValidationResult:
    """
    REM: Validate a QMS chain against v2.2.0 spec rules.

    Checks:
    1. Block integrity — all blocks have :: delimiters (guaranteed by parser)
    2. Priority integrity — if present, must be position 0 with valid level (v2.2.0)
    3. Origin integrity — must be ::<agent>:: (position 1, or 2 with priority)
    4. Correlation integrity — must be ::@@id@@:: with optional TTL (v2.2.0)
    5. Transactional integrity — terminal must be command or system halt
    6. Halt postscript — warns if halt has no following reason block
    7. Halt postscript validity — only %%...%% may follow %%%%

    Args:
        chain: A QMSChain to validate

    Returns:
        QMSValidationResult with errors and warnings
    """
    errors = []
    warnings = []

    if not chain or not chain.blocks:
        return QMSValidationResult(valid=False, errors=["empty_chain: No blocks found"])

    # REM: v2.2.0 — Determine offset (0 without priority, 1 with)
    offset = chain._offset

    # REM: v2.2.0 — Priority Integrity (if present)
    if offset == 1:
        priority_val = chain.blocks[0].inner_value
        if priority_val not in PRIORITY_LEVELS:
            errors.append(
                f"invalid_priority: ::!{priority_val}!:: is not a recognized priority level. "
                f"Valid: {', '.join(sorted(PRIORITY_LEVELS))}"
            )

    # REM: Rule 3.4 — Origin Integrity
    origin_idx = offset
    if len(chain.blocks) <= origin_idx or chain.blocks[origin_idx].block_type != QMSBlockType.ORIGIN:
        errors.append(
            "missing_origin: Origin Block ::<agent>:: not found at expected position. "
            "Anonymous transmission detected — no radio callsign."
        )

    # REM: Rule 3.5 — Correlation Integrity
    corr_idx = offset + 1
    if len(chain.blocks) <= corr_idx or chain.blocks[corr_idx].block_type != QMSBlockType.CORRELATION:
        errors.append(
            "missing_correlation: Correlation Block ::@@id@@:: not found at expected position. "
            "Transaction cannot be traced."
        )
    else:
        # REM: v2.2.0 — Validate TTL if present
        ttl = chain.ttl_seconds
        if ttl is not None and ttl <= 0:
            errors.append(
                f"invalid_ttl: TTL must be positive, got {ttl}s."
            )

    # REM: Rule 3.3 — Transactional Integrity (with halt postscript support)
    if chain.is_halt:
        # REM: Find the halt block position
        halt_idx = None
        for i, b in enumerate(chain.blocks):
            if b.block_type == QMSBlockType.SYSTEM_HALT:
                halt_idx = i
                break

        if halt_idx is not None:
            remaining = chain.blocks[halt_idx + 1:]
            if len(remaining) == 0:
                # REM: Bare halt — valid but recommend postscript
                warnings.append(
                    "halt_no_reason: System Halt has no postscript ::%%reason%%:: block. "
                    "Recommended: the siren should be followed by the incident report."
                )
            elif len(remaining) == 1:
                if remaining[0].block_type != QMSBlockType.STRING:
                    errors.append(
                        "halt_invalid_postscript: Only a ::%%reason%%:: block may follow "
                        "::%%%%::. Found block type: " + remaining[0].block_type.value
                    )
            else:
                errors.append(
                    f"halt_excess_blocks: Only ONE block (the reason) may follow ::%%%%::. "
                    f"Found {len(remaining)} blocks after halt."
                )
    else:
        # REM: Standard chain — last block must be command
        last_block = chain.blocks[-1]
        if last_block.block_type == QMSBlockType.COMMAND:
            suffix = last_block.inner_value
            if suffix not in COMMAND_SUFFIXES:
                errors.append(
                    f"invalid_command: Unrecognized command block ::_{suffix}::. "
                    f"Valid: {', '.join(sorted(COMMAND_SUFFIXES))}"
                )
        else:
            errors.append(
                "incomplete_chain: Chain does not end with a Command Block or System Halt. "
                "This is an incomplete thought — syntactically invalid."
            )

    # REM: Minimum chain length (origin + correlation + action + terminal = 4, plus optional priority)
    min_blocks = 3 + offset  # priority (0 or 1) + origin + correlation + action
    if len(chain.blocks) < min_blocks:
        errors.append(
            f"chain_too_short: Minimum chain requires origin, correlation, and action "
            f"({min_blocks} blocks minimum with {'priority' if offset else 'no priority'}). "
            f"Found {len(chain.blocks)}."
        )

    return QMSValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def is_chain_formatted(message: str) -> bool:
    """
    REM: Quick check — does this string contain a formal QMS v2.1.6 chain?
    REM: Looks for the ::<...>:: origin pattern as the definitive marker.
    REM: No radio callsign = not a formal chain.
    """
    if not message or not isinstance(message, str):
        return False
    return bool(re.search(r'::<[^>]+>::', message))


def validate_chain_string(
    message: str,
    source: str = "unknown",
    log_warning: bool = True
) -> Tuple[bool, Optional[QMSValidationResult]]:
    """
    REM: Parse and validate a chain string in one step.
    REM: Logs security warnings for missing origin (anonymous transmission).

    Args:
        message: String that may contain a QMS chain
        source: Identifier for logging
        log_warning: Whether to log warnings

    Returns:
        Tuple of (is_valid_chain, QMSValidationResult or None)
    """
    chain = parse_chain(message)
    if chain is None:
        if log_warning:
            logger.warning(
                f"QMS_CHAIN_MISSING: No formal chain found from ::{source}:: "
                "— possible legacy format or bypass"
            )
        return (False, None)

    result = validate_chain(chain)

    if not result.valid and log_warning:
        for error in result.errors:
            if "missing_origin" in error:
                # REM: Anonymous transmission — elevated security concern
                try:
                    from core.audit import AuditEventType, audit
                    audit.log(
                        AuditEventType.SECURITY_ALERT,
                        f"Anonymous QMS chain detected from ::{source}:: "
                        "— no origin block (no radio callsign)",
                        actor=source,
                        details={
                            "chain_raw": message[:200],
                            "validation_errors": result.errors
                        }
                    )
                except ImportError:
                    logger.warning(f"QMS_ANONYMOUS_CHAIN: {error}")
            else:
                logger.warning(f"QMS_CHAIN_INVALID [{source}]: {error}")

    return (result.valid, result)


# REM: =======================================================================================
# REM: v2.2.0 — SCHEMA REGISTRY
# REM: =======================================================================================
# REM: The schema registry is a JSON file (qms_schema.json) that defines valid message
# REM: structures. "Is this a valid Tool_Checkout_Please?" becomes a schema check, not
# REM: a regex. The registry is loaded once on import and cached.

_QMS_SCHEMA: Optional[Dict[str, Any]] = None
_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "qms_schema.json")


def _load_schema() -> Dict[str, Any]:
    """REM: Load the QMS schema registry from disk. Cached after first load."""
    global _QMS_SCHEMA
    if _QMS_SCHEMA is not None:
        return _QMS_SCHEMA
    try:
        with open(_SCHEMA_PATH, "r") as f:
            _QMS_SCHEMA = json.load(f)
        logger.info(f"QMS schema registry loaded: {_SCHEMA_PATH}")
    except FileNotFoundError:
        logger.warning(f"QMS schema registry not found at {_SCHEMA_PATH} — semantic validation disabled")
        _QMS_SCHEMA = {}
    except json.JSONDecodeError as e:
        logger.error(f"QMS schema registry parse error: {e}")
        _QMS_SCHEMA = {}
    return _QMS_SCHEMA


def get_message_schema(action: str) -> Optional[Dict[str, Any]]:
    """
    REM: Look up the schema definition for a QMS message type.

    Args:
        action: The action name (e.g., "Tool_Checkout", "Create_Backup")

    Returns:
        Schema dict if found, None otherwise
    """
    schema = _load_schema()
    message_types = schema.get("message_types", {})
    return message_types.get(action)


def validate_chain_semantics(chain: QMSChain) -> QMSValidationResult:
    """
    REM: v2.2.0 — Validate a chain against the schema registry.
    REM: This goes beyond structural validation (validate_chain) to check:
    REM:   1. Is the action a known message type?
    REM:   2. Is the command status valid for this message type?
    REM:   3. Is the priority valid for this message type?
    REM:   4. Are required blocks present?
    REM:
    REM: Returns valid=True with warnings for unknown message types (new types are OK).
    REM: Returns errors only for known types that violate their schema.

    Args:
        chain: A parsed QMSChain

    Returns:
        QMSValidationResult with semantic errors and warnings
    """
    # REM: First run structural validation
    structural = validate_chain(chain)
    if not structural.valid:
        return structural

    errors = list(structural.errors)
    warnings = list(structural.warnings)

    action = chain.action
    if not action:
        return QMSValidationResult(valid=True, errors=errors, warnings=warnings)

    schema = get_message_schema(action)
    if schema is None:
        # REM: Unknown message type — warn but don't block (extensibility)
        warnings.append(
            f"unknown_message_type: '{action}' not found in schema registry. "
            "Message is structurally valid but semantically unverified."
        )
        return QMSValidationResult(valid=True, errors=errors, warnings=warnings)

    # REM: Check command status validity
    command = chain.command
    if command:
        valid_statuses = schema.get("valid_statuses", [])
        if valid_statuses and command.value not in valid_statuses:
            errors.append(
                f"invalid_status_for_type: {action} does not accept ::_{command.value}::. "
                f"Valid: {', '.join(valid_statuses)}"
            )

    # REM: Check priority validity
    priority = chain.priority
    if priority:
        valid_priorities = schema.get("valid_priorities", [])
        if valid_priorities and priority not in valid_priorities:
            warnings.append(
                f"unusual_priority: {action} typically uses priorities "
                f"{valid_priorities}, got '{priority}'."
            )

    # REM: Check halt permission
    if chain.is_halt and not schema.get("allows_halt", False):
        warnings.append(
            f"halt_on_non_halt_type: {action} schema does not declare allows_halt=true. "
            "Halt is structurally valid but unusual for this message type."
        )

    return QMSValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def get_default_ttl(priority: str = None) -> int:
    """
    REM: v2.2.0 — Get the default TTL for a priority level.

    Args:
        priority: Priority level ("URGENT", "P1", "P2", "P3"). None = P2 default.

    Returns:
        TTL in seconds
    """
    schema = _load_schema()
    ttl_map = schema.get("default_ttl_seconds", DEFAULT_TTL_BY_PRIORITY)
    key = (priority or DEFAULT_PRIORITY).upper()
    return ttl_map.get(key, DEFAULT_TTL_BY_PRIORITY.get(DEFAULT_PRIORITY, 120))


# REM: =======================================================================================
# REM: LEGACY FUNCTIONS — BACKWARD COMPATIBILITY
# REM: =======================================================================================
# REM: Everything below this line is the original v4.6.0CC implementation.
# REM: These functions are preserved so existing agents continue to work
# REM: during the incremental migration to formal chain syntax.

# REM: Core pattern: ActionName_Status (legacy suffix format)
QMS_STATUS_PATTERN = re.compile(
    r'([\w]+)_(Please|Thank_You|Thank_You_But_No|Excuse_Me|Pretty_Please)\b'
)

# REM: Legacy field extraction patterns
FIELD_PATTERNS = {
    QMSFieldType.CRITICAL: re.compile(r'::(\w+)=([^:]+)::'),
    QMSFieldType.PRIORITY: re.compile(r'\$\$(\w+)=([^$]+)\$\$'),
    QMSFieldType.POLICY: re.compile(r'##(\w+)=([^#]+)##'),
    QMSFieldType.TARGET: re.compile(r'@@(\w+)=([^@]+)@@'),
    QMSFieldType.QUESTION: re.compile(r'\?\?(\w+)=([^?]+)\?\?'),
}


def is_qms_formatted(message: str) -> bool:
    """
    REM: Check if a message follows QMS formatting (legacy OR formal).
    REM: Returns True if EITHER legacy suffix pattern OR formal chain detected.
    """
    if not message or not isinstance(message, str):
        return False
    if is_chain_formatted(message):
        return True
    return bool(QMS_STATUS_PATTERN.search(message))


def validate_qms(
    message: str,
    source: str = "unknown",
    log_warning: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    REM: Validate message and optionally log if non-QMS detected.
    REM: Checks BOTH formal chain and legacy suffix patterns.
    REM: Does NOT block — only flags for awareness.
    """
    if is_qms_formatted(message):
        return (True, None)

    warning = f"Non-QMS message detected from ::{source}:: — potential bypass or legacy code"

    if log_warning:
        try:
            from core.audit import AuditEventType, audit
            audit.log(
                AuditEventType.SECURITY_ALERT,
                warning,
                actor=source,
                details={
                    "message_preview": message[:100] if message else "empty",
                    "message_length": len(message) if message else 0,
                    "qms_validation": "failed"
                }
            )
        except ImportError:
            logger.warning(f"QMS_VALIDATION_WARNING: {warning}")

    return (False, warning)


def parse_qms(message: str) -> Optional[QMSMessage]:
    """
    REM: Parse a legacy QMS-formatted message into structured components.
    REM: For formal chains, use parse_chain() instead.
    """
    if not message or not isinstance(message, str):
        return None

    match = QMS_STATUS_PATTERN.search(message)
    if not match:
        return None

    action = match.group(1)
    status_str = match.group(2)

    try:
        status = QMSStatus(status_str)
    except ValueError:
        return None

    fields = {}
    for field_type, pattern in FIELD_PATTERNS.items():
        for field_match in pattern.finditer(message):
            key = field_match.group(1)
            value = field_match.group(2).strip()
            fields[key] = {
                "value": value,
                "type": field_type.value
            }

    return QMSMessage(
        action=action,
        status=status,
        fields=fields,
        raw=message
    )


def format_qms(
    action: str,
    status: QMSStatus,
    **fields
) -> str:
    """
    REM: Format an outgoing message in legacy QMS style.
    REM: For formal chains, use build_chain() instead.
    """
    base = f"{action}_{status.value}"

    field_parts = []
    for key, value in fields.items():
        if key == "priority" or key.startswith("priority_"):
            field_parts.append(f"$${key}={value}$$")
        elif key == "policy" or key.startswith("policy_"):
            field_parts.append(f"##{key}={value}##")
        elif key == "target" or key.startswith("target_"):
            field_parts.append(f"@@{key}={value}@@")
        elif key == "question" or key.startswith("question_"):
            field_parts.append(f"??{key}={value}??")
        else:
            field_parts.append(f"::{key}={value}::")

    if field_parts:
        return f"{base} {' '.join(field_parts)}"
    return base


def format_qms_response(
    original_action: str,
    success: bool,
    **fields
) -> str:
    """REM: Convenience function for formatting legacy response messages."""
    status = QMSStatus.THANK_YOU if success else QMSStatus.THANK_YOU_BUT_NO
    return format_qms(original_action, status, **fields)


# REM: =======================================================================================
# REM: QMS DECORATOR FOR FUNCTIONS
# REM: =======================================================================================

def qms_endpoint(action_name: str):
    """
    REM: Decorator that documents a function as QMS-aware.
    REM: Does NOT enforce QMS yet — adds metadata and logging for awareness.
    REM: v5.5.0CC — Handles both sync and async functions correctly.
    """
    import asyncio
    import functools

    def decorator(func):
        func._qms_action = action_name
        func._qms_aware = True

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                logger.debug(f"QMS endpoint called: {action_name}")
                return await func(*args, **kwargs)
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                logger.debug(f"QMS endpoint called: {action_name}")
                return func(*args, **kwargs)

        wrapper._qms_action = action_name
        wrapper._qms_aware = True
        return wrapper
    return decorator


# REM: =======================================================================================
# REM: QMS AUDIT HELPERS
# REM: =======================================================================================

def log_qms_transaction(
    action: str,
    status: QMSStatus,
    actor: str,
    details: Dict[str, Any] = None
) -> str:
    """
    REM: Log a legacy QMS-formatted transaction to the audit log.
    REM: Returns the formatted QMS message for reference.
    """
    qms_message = format_qms(action, status, **(details or {}))

    try:
        from core.audit import AuditEventType, audit
        audit.log(
            AuditEventType.AGENT_ACTION,
            qms_message,
            actor=actor,
            details=details,
            qms_status=status.value
        )
    except ImportError:
        logger.info(f"QMS_TRANSACTION [{actor}]: {qms_message}")

    return qms_message


def log_qms_chain(
    chain: QMSChain,
    actor: str = None,
    details: Dict[str, Any] = None
) -> str:
    """
    REM: Log a formal QMS chain to the audit log.
    REM: Uses the chain's origin as actor if not explicitly provided.

    Args:
        chain: A QMSChain to log
        actor: Override for actor (defaults to chain.origin)
        details: Additional details for the audit entry

    Returns:
        The chain string
    """
    chain_str = chain.to_string()
    effective_actor = actor or chain.origin or "unknown"

    qms_status = None
    if chain.command:
        qms_status = chain.command.value
    elif chain.is_halt:
        qms_status = "SYSTEM_HALT"

    try:
        from core.audit import AuditEventType, audit
        event_type = (
            AuditEventType.SECURITY_ALERT if chain.is_halt
            else AuditEventType.AGENT_ACTION
        )
        audit.log(
            event_type,
            chain_str,
            actor=effective_actor,
            details={
                **(details or {}),
                "qms_version": "2.2.0",
                "correlation_id": chain.correlation_id,
                "priority": chain.priority,
                "ttl_seconds": chain.ttl_seconds,
                "is_halt": chain.is_halt,
            },
            qms_status=qms_status
        )
    except ImportError:
        logger.info(f"QMS_CHAIN [{effective_actor}]: {chain_str}")

    return chain_str


# REM: =======================================================================================
# REM: MODULE EXPORTS
# REM: =======================================================================================

__all__ = [
    # REM: v2.2.0 — Formal chain support with priority, TTL, and schema registry
    "QMSBlockType",
    "QMSBlock",
    "QMSChain",
    "QMSValidationResult",
    "SYSTEM_HALT",
    "SYSTEM_HALT_BLOCK",
    "PRIORITY_LEVELS",
    "DEFAULT_PRIORITY",
    "DEFAULT_TTL_BY_PRIORITY",
    "build_chain",
    "build_halt_chain",
    "parse_chain",
    "find_chains",
    "validate_chain",
    "validate_chain_semantics",
    "validate_chain_string",
    "is_chain_formatted",
    "log_qms_chain",
    "get_message_schema",
    "get_default_ttl",
    # REM: Legacy — backward compatible
    "QMSStatus",
    "QMSFieldType",
    "QMSMessage",
    "is_qms_formatted",
    "validate_qms",
    "parse_qms",
    "format_qms",
    "format_qms_response",
    "qms_endpoint",
    "log_qms_transaction",
]
