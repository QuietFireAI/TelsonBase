# TelsonBase/core/phi_deidentification.py
# REM: =======================================================================================
# REM: HIPAA SAFE HARBOR DE-IDENTIFICATION
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: HIPAA 45 CFR 164.514 defines the Safe Harbor method of
# REM: de-identification, requiring removal of 18 specific identifiers from PHI.
# REM: De-identified data is no longer considered PHI and may be used without
# REM: individual authorization. This module provides automated detection and
# REM: redaction of the 18 HIPAA identifiers from data records.
#
# REM: Features:
# REM:   - PHIField enum covering all 18 HIPAA Safe Harbor identifiers
# REM:   - Pattern-based auto-detection of PHI fields by name
# REM:   - Redaction with "[REDACTED]" replacement
# REM:   - De-identification verification check
# REM:   - Structured result reporting
# REM:   - Full audit trail for all de-identification actions
# REM:   - QMS-formatted logging throughout
#
# REM: v6.3.0CC: Initial implementation for HIPAA healthcare compliance infrastructure
# REM: =======================================================================================

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


# REM: The sentinel value used to replace identified PHI
REDACTED_VALUE = "[REDACTED]"


class PHIField(str, Enum):
    """
    REM: The 18 HIPAA Safe Harbor identifiers per 45 CFR 164.514(b)(2).
    REM: All 18 must be removed for data to qualify as de-identified.
    """
    NAME = "name"
    ADDRESS = "address"
    DATES = "dates"
    PHONE = "phone"
    FAX = "fax"
    EMAIL = "email"
    SSN = "ssn"
    MRN = "mrn"
    HEALTH_PLAN_ID = "health_plan_id"
    ACCOUNT_NUMBER = "account_number"
    LICENSE_NUMBER = "license_number"
    VEHICLE_ID = "vehicle_id"
    DEVICE_ID = "device_id"
    URL = "url"
    IP_ADDRESS = "ip_address"
    BIOMETRIC = "biometric"
    PHOTO = "photo"
    OTHER_UNIQUE = "other_unique"


# REM: Mapping of common field name patterns to PHIField enum values.
# REM: Used for auto-detection of PHI fields in data records.
# REM: Each key is a lowercase substring to match against field names.
PHI_FIELD_PATTERNS: Dict[str, PHIField] = {
    # REM: Names
    "name": PHIField.NAME,
    "first_name": PHIField.NAME,
    "last_name": PHIField.NAME,
    "patient_name": PHIField.NAME,
    "full_name": PHIField.NAME,
    "given_name": PHIField.NAME,
    "family_name": PHIField.NAME,
    # REM: Address
    "address": PHIField.ADDRESS,
    "street": PHIField.ADDRESS,
    "city": PHIField.ADDRESS,
    "state": PHIField.ADDRESS,
    "zip": PHIField.ADDRESS,
    "zip_code": PHIField.ADDRESS,
    "postal": PHIField.ADDRESS,
    "county": PHIField.ADDRESS,
    # REM: Dates (beyond year)
    "date_of_birth": PHIField.DATES,
    "dob": PHIField.DATES,
    "birth_date": PHIField.DATES,
    "admission_date": PHIField.DATES,
    "discharge_date": PHIField.DATES,
    "death_date": PHIField.DATES,
    # REM: Phone
    "phone": PHIField.PHONE,
    "telephone": PHIField.PHONE,
    "mobile": PHIField.PHONE,
    "cell_phone": PHIField.PHONE,
    # REM: Fax
    "fax": PHIField.FAX,
    "fax_number": PHIField.FAX,
    # REM: Email
    "email": PHIField.EMAIL,
    "email_address": PHIField.EMAIL,
    # REM: SSN
    "ssn": PHIField.SSN,
    "social_security": PHIField.SSN,
    "social_security_number": PHIField.SSN,
    # REM: Medical Record Number
    "mrn": PHIField.MRN,
    "medical_record": PHIField.MRN,
    "medical_record_number": PHIField.MRN,
    # REM: Health Plan ID
    "health_plan_id": PHIField.HEALTH_PLAN_ID,
    "insurance_id": PHIField.HEALTH_PLAN_ID,
    "plan_id": PHIField.HEALTH_PLAN_ID,
    "member_id": PHIField.HEALTH_PLAN_ID,
    # REM: Account Number
    "account_number": PHIField.ACCOUNT_NUMBER,
    "account_num": PHIField.ACCOUNT_NUMBER,
    "acct": PHIField.ACCOUNT_NUMBER,
    # REM: License Number
    "license_number": PHIField.LICENSE_NUMBER,
    "license_num": PHIField.LICENSE_NUMBER,
    "drivers_license": PHIField.LICENSE_NUMBER,
    # REM: Vehicle ID
    "vehicle_id": PHIField.VEHICLE_ID,
    "vin": PHIField.VEHICLE_ID,
    "vehicle_serial": PHIField.VEHICLE_ID,
    # REM: Device ID
    "device_id": PHIField.DEVICE_ID,
    "device_serial": PHIField.DEVICE_ID,
    "device_identifier": PHIField.DEVICE_ID,
    # REM: URL
    "url": PHIField.URL,
    "website": PHIField.URL,
    "web_address": PHIField.URL,
    # REM: IP Address
    "ip_address": PHIField.IP_ADDRESS,
    "ip": PHIField.IP_ADDRESS,
    "ip_addr": PHIField.IP_ADDRESS,
    # REM: Biometric
    "biometric": PHIField.BIOMETRIC,
    "fingerprint": PHIField.BIOMETRIC,
    "retina": PHIField.BIOMETRIC,
    "voiceprint": PHIField.BIOMETRIC,
    # REM: Photo
    "photo": PHIField.PHOTO,
    "photograph": PHIField.PHOTO,
    "image": PHIField.PHOTO,
    "face_image": PHIField.PHOTO,
    # REM: Other unique identifying number
    "other_unique": PHIField.OTHER_UNIQUE,
    "unique_id": PHIField.OTHER_UNIQUE,
    "unique_identifier": PHIField.OTHER_UNIQUE,
}


@dataclass
class DeidentificationResult:
    """
    REM: Result of a de-identification operation, including statistics
    REM: and metadata for compliance reporting.
    """
    original_field_count: int
    removed_field_count: int
    remaining_fields: List[str]
    method: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "original_field_count": self.original_field_count,
            "removed_field_count": self.removed_field_count,
            "remaining_fields": self.remaining_fields,
            "method": self.method,
            "timestamp": self.timestamp
        }


class PHIDeidentifier:
    """
    REM: De-identifies data records using the HIPAA Safe Harbor method.
    REM: Maps field names to PHI identifier categories and replaces
    REM: identified PHI with "[REDACTED]". All actions are audit-logged.
    """

    def __init__(self):
        # REM: Use the global pattern mapping
        self._patterns: Dict[str, PHIField] = dict(PHI_FIELD_PATTERNS)

        logger.info("REM: PHIDeidentifier initialized with Safe Harbor patterns_Thank_You")

    def _detect_phi_field(self, field_name: str) -> Optional[PHIField]:
        """
        REM: Detect whether a field name matches a known PHI identifier pattern.
        REM: Uses case-insensitive matching against the pattern dictionary.
        """
        normalized = field_name.lower().strip()

        # REM: Exact match first
        if normalized in self._patterns:
            return self._patterns[normalized]

        # REM: Substring match — check if any pattern is contained in the field name
        for pattern, phi_field in self._patterns.items():
            if pattern in normalized:
                return phi_field

        return None

    def deidentify_record(
        self,
        data: Dict[str, Any],
        method: str = "safe_harbor"
    ) -> Tuple[Dict[str, Any], DeidentificationResult]:
        """
        REM: De-identify a data record using the specified method.
        REM: Currently supports "safe_harbor" (HIPAA 45 CFR 164.514(b)).
        REM: Returns the de-identified record and a result summary.
        """
        now = datetime.now(timezone.utc)
        original_field_count = len(data)
        redacted_fields: List[str] = []

        # REM: Create a copy to avoid mutating the original
        deidentified = {}

        for field_name, value in data.items():
            phi_field = self._detect_phi_field(field_name)
            if phi_field is not None:
                # REM: Replace PHI with redaction sentinel
                deidentified[field_name] = REDACTED_VALUE
                redacted_fields.append(field_name)
            elif isinstance(value, dict):
                # REM: Recursively de-identify nested objects — handles PHI in agent memory contexts
                nested_deidentified, nested_result = self.deidentify_record(value, method)
                deidentified[field_name] = nested_deidentified
                if nested_result.removed_field_count > 0:
                    redacted_fields.append(f"{field_name}.*")
            elif isinstance(value, list):
                # REM: De-identify each dict element in lists (agent tool results, structured outputs)
                deidentified_list = []
                for item in value:
                    if isinstance(item, dict):
                        nested_deidentified, _ = self.deidentify_record(item, method)
                        deidentified_list.append(nested_deidentified)
                    else:
                        deidentified_list.append(item)
                deidentified[field_name] = deidentified_list
            else:
                deidentified[field_name] = value

        remaining_fields = [f for f in deidentified.keys() if deidentified[f] != REDACTED_VALUE]

        result = DeidentificationResult(
            original_field_count=original_field_count,
            removed_field_count=len(redacted_fields),
            remaining_fields=sorted(remaining_fields),
            method=method,
            timestamp=now.isoformat()
        )

        logger.info(
            f"REM: De-identification complete — {len(redacted_fields)} of "
            f"{original_field_count} fields redacted via ::{method}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"PHI de-identification performed: {len(redacted_fields)} fields redacted",
            actor="system",
            details={
                "method": method,
                "original_field_count": original_field_count,
                "redacted_field_count": len(redacted_fields),
                "redacted_fields": sorted(redacted_fields),
                "remaining_fields": sorted(remaining_fields),
                "hipaa_reference": "45 CFR 164.514(b) — Safe Harbor Method"
            },
            qms_status="Thank_You"
        )

        return deidentified, result

    def is_deidentified(self, data: Dict[str, Any]) -> bool:
        """
        REM: Check whether a data record contains any detectable PHI patterns.
        REM: Returns True if no PHI patterns are found (data appears de-identified).
        REM: Returns False if any field matches a known PHI identifier pattern
        REM: and its value is not already "[REDACTED]".
        """
        for field_name, value in data.items():
            phi_field = self._detect_phi_field(field_name)
            if phi_field is not None and value != REDACTED_VALUE:
                logger.info(
                    f"REM: PHI detected in field ::{field_name}:: "
                    f"(category ::{phi_field.value}::) — data is NOT de-identified_Thank_You_But_No"
                )
                return False

        return True

    def get_phi_fields_in_record(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        REM: Identify which fields in a record match PHI patterns.
        REM: Returns a mapping of field_name -> PHIField category.
        """
        found = {}
        for field_name in data.keys():
            phi_field = self._detect_phi_field(field_name)
            if phi_field is not None:
                found[field_name] = phi_field.value
        return found

    def list_safe_harbor_identifiers(self) -> List[Dict[str, str]]:
        """REM: List all 18 HIPAA Safe Harbor identifiers for reference."""
        return [
            {"identifier": phi.value, "enum": phi.name}
            for phi in PHIField
        ]


# REM: Global instance for import throughout the application
phi_deidentifier = PHIDeidentifier()
