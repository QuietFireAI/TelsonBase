# TelsonBase/core/minimum_necessary.py
# REM: =======================================================================================
# REM: HIPAA MINIMUM NECESSARY STANDARD ENFORCEMENT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: HIPAA 45 CFR 164.502(b) requires covered entities to make
# REM: reasonable efforts to limit PHI access to the minimum necessary to accomplish
# REM: the intended purpose. This module enforces role-based field-level filtering
# REM: so that each role only sees the PHI fields required for their function.
#
# REM: Features:
# REM:   - AccessScope enum for categorizing data access levels
# REM:   - Policy-based field filtering per role
# REM:   - Default policies for all 5 RBAC roles
# REM:   - Audit logging of every field filtering action
# REM:   - QMS-formatted logging throughout
#
# REM: v6.3.0CC: Initial implementation for HIPAA healthcare compliance infrastructure
# REM: =======================================================================================

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


class AccessScope(str, Enum):
    """
    REM: Categorization of data access scope per HIPAA Minimum Necessary.
    REM: Each scope represents a different level of PHI access.
    """
    FULL = "full"                   # REM: Unrestricted access — SuperAdmin only
    TREATMENT = "treatment"         # REM: Direct patient care — clinical fields
    PAYMENT = "payment"             # REM: Billing and payment processing
    OPERATIONS = "operations"       # REM: Healthcare operations — quality, auditing
    LIMITED = "limited"             # REM: Restricted view — de-identified summaries only
    DE_IDENTIFIED = "de_identified" # REM: Only de-identified data, no PHI


@dataclass
class MinimumNecessaryPolicy:
    """
    REM: A policy defining what fields a role may access under Minimum Necessary.
    REM: allowed_fields is the whitelist; denied_fields is the explicit blacklist.
    REM: If both are empty, the default_scope determines behavior.
    """
    role: str
    default_scope: AccessScope
    allowed_fields: Set[str] = field(default_factory=set)
    denied_fields: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "role": self.role,
            "default_scope": self.default_scope.value,
            "allowed_fields": sorted(list(self.allowed_fields)),
            "denied_fields": sorted(list(self.denied_fields))
        }


class MinimumNecessaryEnforcer:
    """
    REM: Enforces the HIPAA Minimum Necessary standard by filtering data records
    REM: based on the requesting role's policy. All filtering actions are audit-logged.
    """

    def __init__(self):
        # REM: Policies keyed by role name
        self._policies: Dict[str, MinimumNecessaryPolicy] = {}

        # REM: Register default policies for the 5 existing RBAC roles
        self._register_default_policies()

        logger.info("REM: MinimumNecessaryEnforcer initialized with default policies_Thank_You")

    def _register_default_policies(self):
        """REM: Register default Minimum Necessary policies for all RBAC roles."""
        # REM: Viewer — LIMITED scope, only summary/de-identified fields
        self.register_policy(
            role="viewer",
            scope=AccessScope.LIMITED,
            allowed_fields={"patient_id", "visit_date", "department", "status", "summary"},
            denied_fields={"ssn", "diagnosis_detail", "treatment_notes", "billing_code", "insurance_id"}
        )

        # REM: Operator — OPERATIONS scope, quality and workflow fields
        self.register_policy(
            role="operator",
            scope=AccessScope.OPERATIONS,
            allowed_fields={
                "patient_id", "visit_date", "department", "status", "summary",
                "provider_name", "diagnosis_code", "procedure_code", "disposition"
            },
            denied_fields={"ssn", "treatment_notes", "insurance_id"}
        )

        # REM: Admin — OPERATIONS scope, broader access for system management
        self.register_policy(
            role="admin",
            scope=AccessScope.OPERATIONS,
            allowed_fields={
                "patient_id", "visit_date", "department", "status", "summary",
                "provider_name", "diagnosis_code", "procedure_code", "disposition",
                "billing_code", "insurance_id", "admission_date", "discharge_date"
            },
            denied_fields={"ssn", "treatment_notes"}
        )

        # REM: SecurityOfficer — LIMITED scope, security-focused, no clinical detail
        self.register_policy(
            role="security_officer",
            scope=AccessScope.LIMITED,
            allowed_fields={
                "patient_id", "visit_date", "department", "status",
                "access_log", "last_accessed_by", "disclosure_history"
            },
            denied_fields={"ssn", "diagnosis_detail", "treatment_notes", "billing_code"}
        )

        # REM: SuperAdmin — FULL scope, unrestricted access
        self.register_policy(
            role="super_admin",
            scope=AccessScope.FULL,
            allowed_fields=set(),  # REM: Empty means all fields allowed for FULL scope
            denied_fields=set()
        )

    def register_policy(
        self,
        role: str,
        scope: AccessScope,
        allowed_fields: Optional[Set[str]] = None,
        denied_fields: Optional[Set[str]] = None
    ) -> MinimumNecessaryPolicy:
        """REM: Register or update a Minimum Necessary policy for a role."""
        policy = MinimumNecessaryPolicy(
            role=role,
            default_scope=scope,
            allowed_fields=allowed_fields or set(),
            denied_fields=denied_fields or set()
        )

        self._policies[role] = policy

        logger.info(
            f"REM: Minimum Necessary policy registered for role ::{role}:: "
            f"scope ::{scope.value}::_Thank_You"
        )

        return policy

    def filter_data(self, data: Dict[str, Any], role: str, purpose: str) -> Dict[str, Any]:
        """
        REM: Filter a data record according to the role's Minimum Necessary policy.
        REM: Strips fields not in the allowed set and any fields in the denied set.
        REM: For FULL scope, no filtering is applied.
        """
        policy = self._policies.get(role)

        if not policy:
            logger.warning(
                f"REM: No Minimum Necessary policy found for role ::{role}:: "
                f"— denying all fields_Thank_You_But_No"
            )
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Minimum Necessary: no policy for role {role} — all fields denied",
                actor=role,
                details={"role": role, "purpose": purpose},
                qms_status="Thank_You_But_No"
            )
            return {}

        # REM: FULL scope — no filtering applied
        if policy.default_scope == AccessScope.FULL:
            logger.info(
                f"REM: Minimum Necessary FULL scope for ::{role}:: "
                f"— no filtering applied_Thank_You"
            )
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Minimum Necessary: FULL access granted to {role}",
                actor=role,
                details={"role": role, "purpose": purpose, "fields_returned": len(data)},
                qms_status="Thank_You"
            )
            return dict(data)

        # REM: Apply allowed/denied field filtering
        original_fields = set(data.keys())
        filtered = {}

        for field_name, value in data.items():
            # REM: Explicitly denied fields are always stripped
            if field_name in policy.denied_fields:
                continue
            # REM: If allowed_fields is specified, only those fields pass through
            if policy.allowed_fields and field_name not in policy.allowed_fields:
                continue
            filtered[field_name] = value

        removed_fields = original_fields - set(filtered.keys())

        logger.info(
            f"REM: Minimum Necessary filter applied for ::{role}:: "
            f"purpose ::{purpose}:: — {len(removed_fields)} fields removed_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Minimum Necessary: filtered data for {role}",
            actor=role,
            details={
                "role": role,
                "purpose": purpose,
                "scope": policy.default_scope.value,
                "original_field_count": len(original_fields),
                "returned_field_count": len(filtered),
                "removed_fields": sorted(list(removed_fields))
            },
            qms_status="Thank_You"
        )

        return filtered

    def check_access(self, role: str, field_name: str, purpose: str) -> bool:
        """
        REM: Check whether a specific role is allowed to access a specific field.
        REM: Returns True if access is permitted, False otherwise.
        """
        policy = self._policies.get(role)

        if not policy:
            logger.warning(
                f"REM: No policy for role ::{role}:: — access denied for "
                f"field ::{field_name}::_Thank_You_But_No"
            )
            return False

        # REM: FULL scope always has access
        if policy.default_scope == AccessScope.FULL:
            return True

        # REM: Explicitly denied
        if field_name in policy.denied_fields:
            return False

        # REM: Must be in allowed set if allowed set is defined
        if policy.allowed_fields and field_name not in policy.allowed_fields:
            return False

        return True

    def get_policy(self, role: str) -> Optional[MinimumNecessaryPolicy]:
        """REM: Get the policy for a specific role."""
        return self._policies.get(role)

    def list_policies(self) -> List[Dict[str, Any]]:
        """REM: List all registered Minimum Necessary policies."""
        return [p.to_dict() for p in self._policies.values()]


# REM: Global instance for import throughout the application
minimum_necessary = MinimumNecessaryEnforcer()
