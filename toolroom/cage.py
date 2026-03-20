# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# TelsonBase/toolroom/cage.py
# REM: =======================================================================================
# REM: THE CAGE — SECURED ARCHIVE FOR TOOL PROVENANCE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: In every production toolroom there's a cage — a locked area
# REM: where the most important tools are kept under tighter control. In Jeff's father's
# REM: Ford toolroom (journeyman toolmaker), you didn't just sign tools out — the cage
# REM: kept the master copies, the calibration records, the provenance trail.
# REM:
# REM: This cage does the same thing digitally:
# REM:   1. ARCHIVE — Every tool that enters the toolroom gets a timestamped snapshot
# REM:      stored in the cage. This is the "as-received" copy.
# REM:   2. UPDATE TRAIL — When the Foreman pulls updates, the new version is archived
# REM:      alongside the old. You can diff what changed.
# REM:   3. INTEGRITY — Each archive entry includes SHA-256 hash, source, timestamp,
# REM:      who approved it, and the approval request ID.
# REM:   4. COMPLIANCE — If an auditor asks "what was installed on this date?", the cage
# REM:      has the answer. If they ask "who approved it?", the cage has that too.
# REM:
# REM: Storage: /app/toolroom/cage/{tool_id}/{version}_{timestamp}/
# REM:   - tool_manifest.json (copy)
# REM:   - cage_receipt.json (provenance metadata)
# REM:   - source files (shallow copy or tarball)
# REM:
# REM: The cage is append-only in normal operation. Only the Foreman writes to it.
# REM: Only operators with explicit permission can purge old entries.
# REM:
# REM: QMS Protocol:
# REM:   Cage_Archive_Please ::tool_id:: ::version::
# REM:   Cage_Archive_Thank_You ::receipt_id::
# REM:   Cage_Verify_Please ::tool_id:: → integrity check against live tool
# REM:   Cage_Inventory_Please → list of all archived entries
# REM: =======================================================================================

import hashlib
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid

logger = logging.getLogger(__name__)

# REM: Base path for the cage — defaults to /app/toolroom/cage in Docker,
# REM: falls back to ./toolroom/cage for local development
CAGE_PATH = Path(os.environ.get("CAGE_PATH", "/app/toolroom/cage"))

# REM: Maximum archives per tool (oldest auto-purged beyond this)
MAX_ARCHIVES_PER_TOOL = 20


@dataclass
class CageReceipt:
    """
    REM: Provenance record for a tool archived in the cage.
    REM: This is the "chain of custody" document for every tool on base.
    """
    receipt_id: str = field(default_factory=lambda: f"CAGE-{uuid.uuid4().hex[:12]}")
    tool_id: str = ""
    tool_name: str = ""
    version: str = ""
    source: str = ""                        # "github:owner/repo" or "upload:filename"
    sha256_hash: str = ""                   # Hash of archived content
    archived_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    archived_by: str = "foreman_agent"      # Who performed the archive
    approved_by: str = ""                   # Human who approved the install/update
    approval_request_id: str = ""           # Links back to approval system
    archive_path: str = ""                  # Where on disk this archive lives
    archive_type: str = "install"           # "install", "update", "rollback", "manual"
    previous_version: str = ""              # Version this replaced (for updates)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CageReceipt":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def from_json(cls, json_str: str) -> "CageReceipt":
        return cls.from_dict(json.loads(json_str))


class Cage:
    """
    REM: The Cage — append-only archive for tool provenance and compliance.
    REM: Every tool installation, update, and rollback is recorded here.
    """

    def __init__(self, cage_path: Path = None):
        self.cage_path = cage_path or CAGE_PATH
        self._receipts: Dict[str, CageReceipt] = {}
        try:
            self.cage_path.mkdir(parents=True, exist_ok=True)
            self._load_receipts()
        except (PermissionError, OSError) as e:
            # REM: v5.5.0CC — Don't crash on import in dev/test environments
            # REM: where /app doesn't exist. Cage operates in degraded mode.
            logger.warning(
                f"REM: Cage initialization degraded — cannot create {self.cage_path}: {e}. "
                f"Archive/verify operations will fail until path is available."
            )
        logger.info(
            f"REM: Cage initialized at {self.cage_path} — "
            f"{len(self._receipts)} archived entries"
        )

    def _load_receipts(self):
        """REM: Load all cage receipts from disk on startup."""
        for tool_dir in self.cage_path.iterdir():
            if not tool_dir.is_dir():
                continue
            for version_dir in tool_dir.iterdir():
                if not version_dir.is_dir():
                    continue
                receipt_path = version_dir / "cage_receipt.json"
                if receipt_path.exists():
                    try:
                        with open(receipt_path, "r") as f:
                            receipt = CageReceipt.from_json(f.read())
                            self._receipts[receipt.receipt_id] = receipt
                    except Exception as e:
                        logger.warning(
                            f"REM: Failed to load cage receipt from {receipt_path}: {e}"
                        )

    def archive_tool(
        self,
        tool_id: str,
        tool_name: str,
        version: str,
        source: str,
        source_path: Path,
        approved_by: str = "",
        approval_request_id: str = "",
        archive_type: str = "install",
        previous_version: str = "",
        notes: str = "",
    ) -> Optional[CageReceipt]:
        """
        REM: Archive a tool (or tool update) into the cage.
        REM: Creates a timestamped directory with:
        REM:   - Copy of tool files (or manifest + metadata if files are large)
        REM:   - cage_receipt.json with full provenance chain
        REM:
        REM: QMS: Cage_Archive_Please ::tool_id:: ::version::
        REM:      → Cage_Archive_Thank_You ::receipt_id::
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_version = version.replace("/", "_").replace("\\", "_")
        archive_dir = self.cage_path / tool_id / f"{safe_version}_{timestamp}"

        try:
            archive_dir.mkdir(parents=True, exist_ok=True)

            # REM: Copy source files into the cage
            if source_path.is_dir():
                # REM: Copy manifest and key metadata files (not full repo to save space)
                self._archive_directory(source_path, archive_dir)
            elif source_path.is_file():
                shutil.copy2(source_path, archive_dir / source_path.name)

            # REM: Calculate integrity hash of the archived content
            sha256 = self._hash_directory(archive_dir)

            # REM: Create the receipt
            receipt = CageReceipt(
                tool_id=tool_id,
                tool_name=tool_name,
                version=version,
                source=source,
                sha256_hash=sha256,
                approved_by=approved_by,
                approval_request_id=approval_request_id,
                archive_path=str(archive_dir),
                archive_type=archive_type,
                previous_version=previous_version,
                notes=notes,
            )

            # REM: Write receipt to disk
            receipt_path = archive_dir / "cage_receipt.json"
            with open(receipt_path, "w") as f:
                f.write(receipt.to_json())

            self._receipts[receipt.receipt_id] = receipt

            # REM: Enforce per-tool archive limit
            self._enforce_limit(tool_id)

            try:
                from core.audit import audit, AuditEventType
                audit.log(
                    AuditEventType.AGENT_ACTION,
                    f"Tool archived in cage: ::{tool_id}:: v{version} "
                    f"(receipt ::{receipt.receipt_id}::)",
                    actor="foreman_agent",
                    details={
                        "receipt_id": receipt.receipt_id,
                        "tool_id": tool_id,
                        "version": version,
                        "source": source,
                        "sha256": sha256,
                        "archive_type": archive_type,
                        "approved_by": approved_by,
                    },
                )
            except ImportError:
                logger.info(f"Cage archived: {tool_id} v{version}")

            logger.info(
                f"REM: Cage_Archive_Thank_You ::{receipt.receipt_id}:: "
                f"::{tool_id}:: v{version} ({archive_type})"
            )
            return receipt

        except Exception as e:
            logger.error(
                f"REM: Cage_Archive_Thank_You_But_No ::error:: "
                f"::{tool_id}:: v{version}: {e}"
            )
            return None

    def verify_tool(self, tool_id: str, live_tool_path: Path) -> Dict[str, Any]:
        """
        REM: Verify a live tool against its most recent cage archive.
        REM: Compares SHA-256 hash of current files vs archived snapshot.
        REM:
        REM: QMS: Cage_Verify_Please ::tool_id::
        REM:      → {verified: bool, details: ...}
        """
        # REM: Find most recent archive for this tool
        tool_receipts = [
            r for r in self._receipts.values()
            if r.tool_id == tool_id
        ]
        if not tool_receipts:
            return {
                "verified": False,
                "reason": f"No cage archive found for tool '{tool_id}'",
                "qms": f"Cage_Verify_Thank_You_But_No ::no_archive:: ::{tool_id}::",
            }

        latest = sorted(tool_receipts, key=lambda r: r.archived_at)[-1]

        if not live_tool_path.exists():
            return {
                "verified": False,
                "reason": f"Live tool path does not exist: {live_tool_path}",
                "qms": f"Cage_Verify_Thank_You_But_No ::tool_missing:: ::{tool_id}::",
            }

        live_hash = self._hash_directory(live_tool_path) if live_tool_path.is_dir() else self._hash_file(live_tool_path)

        matches = live_hash == latest.sha256_hash
        result = {
            "verified": matches,
            "tool_id": tool_id,
            "live_hash": live_hash,
            "archived_hash": latest.sha256_hash,
            "archived_version": latest.version,
            "archived_at": latest.archived_at,
            "receipt_id": latest.receipt_id,
        }

        if matches:
            result["qms"] = f"Cage_Verify_Thank_You ::{tool_id}:: — integrity confirmed"
            logger.info(f"REM: Cage_Verify_Thank_You ::{tool_id}:: — hashes match")
        else:
            result["qms"] = f"Cage_Verify_Thank_You_But_No ::tampered:: ::{tool_id}::"
            result["reason"] = "Hash mismatch — live tool differs from cage archive"
            try:
                from core.audit import audit, AuditEventType
                audit.log(
                    AuditEventType.SECURITY_ALERT,
                    f"Cage integrity violation: ::{tool_id}:: live hash differs from archive",
                    actor="foreman_agent",
                    details=result,
                )
            except ImportError:
                logger.warning(f"Cage integrity violation: {tool_id}")
            logger.warning(
                f"REM: Cage_Verify_Thank_You_But_No ::tampered:: "
                f"::{tool_id}:: — HASH MISMATCH"
            )

        return result

    def get_inventory(self, tool_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        REM: Get cage inventory — all archived receipts.
        REM: QMS: Cage_Inventory_Please → Cage_Inventory_Thank_You ::count::
        """
        receipts = list(self._receipts.values())
        if tool_id:
            receipts = [r for r in receipts if r.tool_id == tool_id]
        receipts.sort(key=lambda r: r.archived_at, reverse=True)
        return [r.to_dict() for r in receipts]

    def get_receipt(self, receipt_id: str) -> Optional[CageReceipt]:
        """REM: Look up a specific cage receipt."""
        return self._receipts.get(receipt_id)

    def _archive_directory(self, source_dir: Path, archive_dir: Path):
        """
        REM: Copy key files from a tool directory into the cage archive.
        REM: Copies: manifest, README, LICENSE, config files, and top-level Python files.
        REM: Does NOT copy: .git directory, __pycache__, node_modules, etc.
        REM: v5.5.0CC — Does NOT follow symlinks (prevents data exfiltration from
        REM: malicious tool packages that symlink to /etc/passwd or similar).
        """
        for item in source_dir.rglob("*"):
            # REM: Skip excluded directories (uses class constants for consistency with hash)
            if any(skip in item.parts for skip in self._SKIP_DIRS):
                continue
            # REM: v5.5.0CC — Skip symlinks entirely. A tool package should not
            # REM: contain symlinks to paths outside its own tree.
            if item.is_symlink():
                logger.warning(
                    f"REM: Cage skipping symlink during archive: {item} → {item.resolve()}"
                )
                continue
            if item.is_file() and item.suffix not in self._SKIP_EXTENSIONS:
                rel_path = item.relative_to(source_dir)
                dest = archive_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)

    def _enforce_limit(self, tool_id: str):
        """REM: Keep only MAX_ARCHIVES_PER_TOOL most recent archives per tool."""
        tool_receipts = sorted(
            [r for r in self._receipts.values() if r.tool_id == tool_id],
            key=lambda r: r.archived_at,
        )
        while len(tool_receipts) > MAX_ARCHIVES_PER_TOOL:
            oldest = tool_receipts.pop(0)
            # REM: Remove from disk — guard required: Path("") == Path(".") is CWD
            if oldest.archive_path:
                archive_path = Path(oldest.archive_path)
                if archive_path.exists():
                    shutil.rmtree(archive_path, ignore_errors=True)
            # REM: Remove from memory
            self._receipts.pop(oldest.receipt_id, None)
            logger.info(
                f"REM: Cage archive pruned: ::{oldest.receipt_id}:: "
                f"::{oldest.tool_id}:: v{oldest.version} (limit enforcement)"
            )

    # REM: v5.5.0CC — Directories and extensions excluded from hashing.
    # REM: MUST match the exclusions in _archive_directory, otherwise
    # REM: verify_tool always reports false tampering (live hash includes
    # REM: .git etc. that the archive doesn't contain).
    _SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox"}
    _SKIP_EXTENSIONS = {".pyc", ".pyo", ".so", ".o", ".a"}
    _SKIP_FILES = {"cage_receipt.json"}

    @staticmethod
    def _hash_directory(directory: Path) -> str:
        """
        REM: SHA-256 hash of all files in a directory.
        REM: v5.5.0CC — Applies same exclusions as _archive_directory so that
        REM: hashing a live tool directory produces the same hash as hashing
        REM: the archived copy. Also includes relative file paths in the hash
        REM: so renaming a file changes the hash.
        """
        sha256 = hashlib.sha256()
        for filepath in sorted(directory.rglob("*")):
            # REM: Skip excluded directories
            if any(skip in filepath.parts for skip in Cage._SKIP_DIRS):
                continue
            if not filepath.is_file():
                continue
            if filepath.suffix in Cage._SKIP_EXTENSIONS:
                continue
            if filepath.name in Cage._SKIP_FILES:
                continue
            # REM: Include the relative path in the hash — renaming a file
            # REM: should produce a different hash, not just content changes
            rel = filepath.relative_to(directory)
            sha256.update(str(rel).replace("\\", "/").encode("utf-8"))
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def _hash_file(filepath: Path) -> str:
        """REM: SHA-256 hash of a single file."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


# REM: =======================================================================================
# REM: SINGLETON INSTANCE
# REM: =======================================================================================

cage = Cage()
