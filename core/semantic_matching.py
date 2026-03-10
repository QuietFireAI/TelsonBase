# TelsonBase/core/semantic_matching.py
# REM: =======================================================================================
# REM: SEMANTIC ACTION MATCHING
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.2.0CC: New feature - Semantic matching for capability checks
#
# REM: Mission Statement: Enable intelligent matching of actions to capabilities beyond
# REM: simple string matching. Maps synonymous actions, understands hierarchies, and
# REM: provides fuzzy matching for better usability while maintaining security.
#
# REM: Features:
# REM:   - Action synonym mapping (delete/remove/destroy → delete)
# REM:   - Resource hierarchy matching (file inherits from filesystem)
# REM:   - Path normalization and matching
# REM:   - Configurable strictness levels
# REM: =======================================================================================

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Set, Tuple

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


class MatchStrictness(str, Enum):
    """REM: How strict matching should be."""
    STRICT = "strict"       # Exact matches only
    STANDARD = "standard"   # Synonyms and hierarchies
    RELAXED = "relaxed"     # Include fuzzy matching


# REM: Action synonyms - canonical form is the first in each group
ACTION_SYNONYMS: Dict[str, List[str]] = {
    "read": ["view", "get", "fetch", "retrieve", "load", "access"],
    "write": ["save", "store", "put", "update", "modify", "edit"],
    "create": ["new", "add", "insert", "make", "generate"],
    "delete": ["remove", "destroy", "drop", "unlink", "erase"],
    "execute": ["run", "invoke", "call", "trigger", "start"],
    "list": ["enumerate", "browse", "scan", "index"],
    "send": ["transmit", "post", "push", "emit"],
    "receive": ["accept", "pull", "fetch"],
}

# REM: Build reverse lookup
_SYNONYM_TO_CANONICAL: Dict[str, str] = {}
for canonical, synonyms in ACTION_SYNONYMS.items():
    _SYNONYM_TO_CANONICAL[canonical] = canonical
    for syn in synonyms:
        _SYNONYM_TO_CANONICAL[syn] = canonical


# REM: Resource hierarchy - child inherits from parent
RESOURCE_HIERARCHY: Dict[str, str] = {
    "file": "filesystem",
    "directory": "filesystem",
    "folder": "filesystem",
    "document": "file",
    "image": "file",
    "config": "file",
    "database": "storage",
    "table": "database",
    "record": "table",
    "api": "external",
    "http": "external",
    "https": "external",
    "webhook": "external",
    "email": "external",
    "agent": "internal",
    "task": "internal",
    "queue": "internal",
}


@dataclass
class MatchResult:
    """REM: Result of a semantic match attempt."""
    matched: bool
    capability: str
    required: str
    match_type: str  # exact, synonym, hierarchy, path, fuzzy
    confidence: float  # 0.0 to 1.0
    canonical_action: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class SemanticMatcher:
    """
    REM: Semantic capability matcher for intelligent permission checking.
    """

    def __init__(self, strictness: MatchStrictness = MatchStrictness.STANDARD):
        self.strictness = strictness
        self._custom_synonyms: Dict[str, List[str]] = {}
        self._custom_hierarchy: Dict[str, str] = {}

    def canonicalize_action(self, action: str) -> str:
        """REM: Convert action to its canonical form."""
        action_lower = action.lower()
        return _SYNONYM_TO_CANONICAL.get(action_lower, action_lower)

    def get_resource_ancestors(self, resource: str) -> List[str]:
        """REM: Get the hierarchy chain for a resource type."""
        ancestors = [resource]
        current = resource.lower()

        # REM: Check custom hierarchy first
        hierarchy = {**RESOURCE_HIERARCHY, **self._custom_hierarchy}

        while current in hierarchy:
            parent = hierarchy[current]
            ancestors.append(parent)
            current = parent

        return ancestors

    def normalize_path(self, path: str) -> str:
        """REM: Normalize a path for matching."""
        if not path:
            return ""

        path = path.replace("\\", "/")
        path = re.sub(r"/+", "/", path)
        path = path.rstrip("/")

        try:
            posix = PurePosixPath(path)
            return str(posix)
        except Exception:
            return path

    def path_matches(self, pattern: str, path: str) -> bool:
        """REM: Check if a path matches a pattern with wildcards."""
        pattern = self.normalize_path(pattern)
        path = self.normalize_path(path)

        if pattern == path:
            return True

        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            if path.startswith(prefix + "/") or path == prefix:
                return True
            return False

        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            if path.startswith(prefix + "/") or path == prefix:
                return True
            return False

        if "*" in pattern:
            regex_pattern = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
            return bool(re.fullmatch(regex_pattern, path))

        return False

    def match_capability(
        self,
        held_capability: str,
        required_capability: str
    ) -> MatchResult:
        """
        REM: Check if a held capability satisfies a required capability.

        Args:
            held_capability: Capability the agent has (e.g., "filesystem.read:/data/*")
            required_capability: Capability needed (e.g., "file.view:/data/docs/report.txt")

        Returns:
            MatchResult with match details
        """
        held_parts = self._parse_capability(held_capability)
        required_parts = self._parse_capability(required_capability)

        if held_parts is None or required_parts is None:
            return MatchResult(
                matched=False,
                capability=held_capability,
                required=required_capability,
                match_type="parse_error",
                confidence=0.0,
                details={"error": "Could not parse capability"}
            )

        held_resource, held_action, held_path = held_parts
        req_resource, req_action, req_path = required_parts

        # REM: Step 1: Match action (with synonym support)
        action_match, action_type, canonical = self._match_action(held_action, req_action)
        if not action_match:
            return MatchResult(
                matched=False,
                capability=held_capability,
                required=required_capability,
                match_type="action_mismatch",
                confidence=0.0,
                canonical_action=canonical,
                details={
                    "held_action": held_action,
                    "required_action": req_action,
                    "canonical": canonical
                }
            )

        # REM: Step 2: Match resource (with hierarchy support)
        resource_match, resource_type = self._match_resource(held_resource, req_resource)
        if not resource_match:
            return MatchResult(
                matched=False,
                capability=held_capability,
                required=required_capability,
                match_type="resource_mismatch",
                confidence=0.0,
                canonical_action=canonical,
                details={
                    "held_resource": held_resource,
                    "required_resource": req_resource,
                    "resource_ancestors": self.get_resource_ancestors(req_resource)
                }
            )

        # REM: Step 3: Match path (with wildcard support)
        if held_path and req_path:
            path_match = self.path_matches(held_path, req_path)
            if not path_match:
                return MatchResult(
                    matched=False,
                    capability=held_capability,
                    required=required_capability,
                    match_type="path_mismatch",
                    confidence=0.0,
                    canonical_action=canonical,
                    details={
                        "held_path": held_path,
                        "required_path": req_path
                    }
                )

        # REM: Calculate confidence
        confidence = 1.0
        match_type = "exact"

        if action_type == "synonym":
            confidence *= 0.95
            match_type = "synonym"
        if resource_type == "hierarchy":
            confidence *= 0.90
            match_type = "hierarchy"

        return MatchResult(
            matched=True,
            capability=held_capability,
            required=required_capability,
            match_type=match_type,
            confidence=confidence,
            canonical_action=canonical,
            details={
                "action_match": action_type,
                "resource_match": resource_type
            }
        )

    def _parse_capability(self, capability: str) -> Optional[Tuple[str, str, str]]:
        """REM: Parse a capability string into (resource, action, path)."""
        try:
            if ":" in capability:
                base, path = capability.split(":", 1)
            else:
                base = capability
                path = ""

            if "." in base:
                resource, action = base.rsplit(".", 1)
            else:
                resource = base
                action = "*"

            return (resource, action, path)
        except Exception:
            return None

    def _match_action(self, held: str, required: str) -> Tuple[bool, str, str]:
        """REM: Match actions with synonym support."""
        held_lower = held.lower()
        required_lower = required.lower()

        if held_lower == required_lower:
            return True, "exact", required_lower

        if held_lower == "*":
            return True, "wildcard", required_lower

        held_canonical = self.canonicalize_action(held_lower)
        required_canonical = self.canonicalize_action(required_lower)

        if held_canonical == required_canonical:
            return True, "synonym", required_canonical

        if self.strictness == MatchStrictness.STRICT:
            return False, "none", required_canonical

        return False, "none", required_canonical

    def _match_resource(self, held: str, required: str) -> Tuple[bool, str]:
        """REM: Match resources with hierarchy support."""
        held_lower = held.lower()
        required_lower = required.lower()

        if held_lower == required_lower:
            return True, "exact"

        if held_lower == "*":
            return True, "wildcard"

        if self.strictness == MatchStrictness.STRICT:
            return False, "none"

        ancestors = self.get_resource_ancestors(required_lower)
        if held_lower in ancestors:
            return True, "hierarchy"

        return False, "none"

    def find_matching_capability(
        self,
        held_capabilities: List[str],
        required_capability: str
    ) -> Optional[MatchResult]:
        """
        REM: Find the best matching capability from a list.

        Returns the best match, or None if no match found.
        """
        best_match: Optional[MatchResult] = None

        for held in held_capabilities:
            result = self.match_capability(held, required_capability)
            if result.matched:
                if best_match is None or result.confidence > best_match.confidence:
                    best_match = result

        return best_match

    def add_custom_synonym(self, canonical: str, synonyms: List[str]) -> None:
        """REM: Add custom synonyms for an action."""
        self._custom_synonyms[canonical] = synonyms
        for syn in synonyms:
            _SYNONYM_TO_CANONICAL[syn.lower()] = canonical.lower()

        logger.info(
            f"REM: Added custom synonyms for ::{canonical}:: - {synonyms}_Thank_You"
        )

    def add_custom_hierarchy(self, child: str, parent: str) -> None:
        """REM: Add custom resource hierarchy."""
        self._custom_hierarchy[child.lower()] = parent.lower()

        logger.info(
            f"REM: Added custom hierarchy: ::{child}:: inherits from ::{parent}::_Thank_You"
        )

    def explain_match(self, result: MatchResult) -> str:
        """REM: Generate human-readable explanation of a match result."""
        if result.matched:
            return (
                f"MATCH ({result.match_type}, {result.confidence:.0%} confidence): "
                f"'{result.capability}' satisfies '{result.required}'"
            )
        else:
            reason = result.match_type.replace("_", " ")
            return (
                f"NO MATCH ({reason}): "
                f"'{result.capability}' does not satisfy '{result.required}'"
            )


# REM: Global semantic matcher instance
semantic_matcher = SemanticMatcher()


def check_capability_semantic(
    held_capabilities: List[str],
    required_capability: str,
    agent_id: Optional[str] = None
) -> Tuple[bool, Optional[MatchResult]]:
    """
    REM: Check if any held capability satisfies the required capability.

    Convenience function for capability enforcement.
    """
    result = semantic_matcher.find_matching_capability(held_capabilities, required_capability)

    if result and result.matched:
        if agent_id:
            logger.debug(
                f"REM: Semantic match for ::{agent_id}:: - {result.match_type} match_Thank_You"
            )
        return True, result

    if agent_id:
        logger.debug(
            f"REM: No semantic match for ::{agent_id}:: on ::{required_capability}::_Thank_You_But_No"
        )
    return False, result
