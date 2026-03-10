# TelsonBase/core/data_classification.py
# REM: =======================================================================================
# REM: DATA CLASSIFICATION & SENSITIVITY ENFORCEMENT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v5.3.0CC: New feature - Data classification for multi-tenancy
#
# REM: Mission Statement: Classify data by sensitivity level and enforce access controls
# REM: based on classification. Law firms require CONFIDENTIAL as a floor. Financial data
# REM: is always RESTRICTED (attorney-client privilege level). PII is always CONFIDENTIAL.
# REM:
# REM: Classification Levels (ascending sensitivity):
# REM:   PUBLIC      — No restrictions, publicly shareable
# REM:   INTERNAL    — Default for general tenants, internal use only
# REM:   CONFIDENTIAL — Default for law firms, PII, sensitive business data
# REM:   RESTRICTED  — Attorney-client privilege, financial records, trade secrets
# REM: =======================================================================================

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: CLASSIFICATION ENUM
# REM: =======================================================================================

class DataClassification(str, Enum):
    """
    REM: Data sensitivity levels in ascending order.
    REM: RESTRICTED is the highest — attorney-client privilege level.
    """
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


# REM: Ordered list for comparison — index = sensitivity rank
_CLASSIFICATION_ORDER: List[DataClassification] = [
    DataClassification.PUBLIC,
    DataClassification.INTERNAL,
    DataClassification.CONFIDENTIAL,
    DataClassification.RESTRICTED,
]


def classification_rank(classification: DataClassification) -> int:
    """REM: Return the numeric rank of a classification for comparison."""
    return _CLASSIFICATION_ORDER.index(classification)


def at_least(
    classification: DataClassification,
    minimum: DataClassification
) -> bool:
    """REM: Check if a classification meets or exceeds a minimum level."""
    return classification_rank(classification) >= classification_rank(minimum)


# REM: =======================================================================================
# REM: CLASSIFICATION POLICY
# REM: =======================================================================================

@dataclass
class ClassificationPolicy:
    """
    REM: Maps classification levels to the permissions required to access data
    REM: at that level. Used by enforcement middleware to gate access.
    """
    classification: DataClassification
    required_permissions: Set[str] = field(default_factory=set)
    allowed_export: bool = True
    requires_audit_on_access: bool = False
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "classification": self.classification.value,
            "required_permissions": list(self.required_permissions),
            "allowed_export": self.allowed_export,
            "requires_audit_on_access": self.requires_audit_on_access,
            "description": self.description,
        }


# REM: Default policies for each classification level
DEFAULT_POLICIES: Dict[DataClassification, ClassificationPolicy] = {
    DataClassification.PUBLIC: ClassificationPolicy(
        classification=DataClassification.PUBLIC,
        required_permissions={"view:dashboard"},
        allowed_export=True,
        requires_audit_on_access=False,
        description="Public data — no special restrictions",
    ),
    DataClassification.INTERNAL: ClassificationPolicy(
        classification=DataClassification.INTERNAL,
        required_permissions={"view:dashboard", "view:agents"},
        allowed_export=True,
        requires_audit_on_access=False,
        description="Internal use only — authenticated users",
    ),
    DataClassification.CONFIDENTIAL: ClassificationPolicy(
        classification=DataClassification.CONFIDENTIAL,
        required_permissions={"view:dashboard", "view:audit"},
        allowed_export=False,
        requires_audit_on_access=True,
        description="Confidential — PII, law firm default, audit-on-access",
    ),
    DataClassification.RESTRICTED: ClassificationPolicy(
        classification=DataClassification.RESTRICTED,
        required_permissions={"view:dashboard", "view:audit", "security:audit"},
        allowed_export=False,
        requires_audit_on_access=True,
        description="Restricted — attorney-client privilege, financial records",
    ),
}


# REM: =======================================================================================
# REM: DATA TYPE KEYWORDS FOR AUTOMATIC CLASSIFICATION
# REM: =======================================================================================

# REM: Data types that always classify as RESTRICTED
_FINANCIAL_DATA_TYPES: Set[str] = {
    "financial",
    "bank_statement",
    "wire_transfer",
    "escrow",
    "closing_statement",
    "hud1",
    "tax_return",
    "w2",
    "1099",
    "balance_sheet",
}

# REM: Data types that always classify as CONFIDENTIAL
_PII_DATA_TYPES: Set[str] = {
    "pii",
    "ssn",
    "driver_license",
    "passport",
    "medical",
    "health_record",
    "personal_contact",
    "background_check",
}


# REM: =======================================================================================
# REM: CLASSIFICATION FUNCTION
# REM: =======================================================================================

def classify_data(data_type: str, tenant_type: str) -> DataClassification:
    """
    REM: Determine the default classification for a piece of data based on
    REM: its type and the tenant's organization type.
    REM:
    REM: Rules (applied in priority order):
    REM:   1. Financial data → RESTRICTED (regardless of tenant)
    REM:   2. PII data → CONFIDENTIAL (regardless of tenant)
    REM:   3. Law firm + any data → CONFIDENTIAL minimum
    REM:   4. Default → INTERNAL
    """
    data_type_lower = data_type.lower().strip()
    tenant_type_lower = tenant_type.lower().strip()

    # REM: Rule 1 — Financial data is always RESTRICTED
    if data_type_lower in _FINANCIAL_DATA_TYPES:
        logger.info(
            f"REM: Data type ::{data_type}:: classified as RESTRICTED "
            f"(financial data rule)_Thank_You"
        )
        return DataClassification.RESTRICTED

    # REM: Rule 2 — PII data is always CONFIDENTIAL
    if data_type_lower in _PII_DATA_TYPES:
        logger.info(
            f"REM: Data type ::{data_type}:: classified as CONFIDENTIAL "
            f"(PII data rule)_Thank_You"
        )
        return DataClassification.CONFIDENTIAL

    # REM: Rule 3 — Law firms get CONFIDENTIAL as a floor
    if tenant_type_lower == "law_firm":
        logger.info(
            f"REM: Data type ::{data_type}:: classified as CONFIDENTIAL "
            f"(law firm tenant floor)_Thank_You"
        )
        return DataClassification.CONFIDENTIAL

    # REM: Rule 4 — Default
    logger.info(
        f"REM: Data type ::{data_type}:: classified as INTERNAL "
        f"(default rule)_Please"
    )
    return DataClassification.INTERNAL


def get_policy(classification: DataClassification) -> ClassificationPolicy:
    """REM: Get the policy for a given classification level."""
    return DEFAULT_POLICIES.get(classification, DEFAULT_POLICIES[DataClassification.INTERNAL])


def list_policies() -> List[Dict[str, Any]]:
    """REM: List all classification policies."""
    return [p.to_dict() for p in DEFAULT_POLICIES.values()]
