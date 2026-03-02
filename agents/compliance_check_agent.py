# TelsonBase/agents/compliance_check_agent.py
# REM: =======================================================================================
# REM: COMPLIANCE CHECK AGENT — REAL ESTATE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: Real estate compliance monitoring agent. Tracks license
# REM: expirations, fair housing requirements, required disclosures, regulatory deadlines,
# REM: and continuing education. Demonstrates TelsonBase's audit chain and anomaly
# REM: detection with a compliance use case that brokerages are legally required to manage.
#
# REM: Third Floor agent — specialized industry compliance.
#
# REM: Capabilities:
# REM:   - Track agent/broker license status and expiration dates
# REM:   - Monitor fair housing compliance requirements
# REM:   - Verify required disclosures per transaction type and state
# REM:   - Track continuing education (CE) credits and deadlines
# REM:   - Generate compliance reports per brokerage/agent
# REM:   - Flag compliance violations for human review
#
# REM: QMS Protocol:
# REM:   Compliance_Check_Please → Compliance_Check_Thank_You
# REM:   Compliance_License_Please → Compliance_License_Thank_You
# REM:   Compliance_Disclosure_Please → Compliance_Disclosure_Thank_You
# REM:   Compliance_Override_Please (requires approval) → Compliance_Override_Thank_You
# REM: =======================================================================================

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from agents.base import SecureBaseAgent, AgentRequest
from core.audit import audit, AuditEventType
from core.qms import format_qms, QMSStatus

logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: DOMAIN MODELS
# REM: =======================================================================================

class LicenseStatus(str, Enum):
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"  # Within 90 days
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    PENDING_RENEWAL = "pending_renewal"


class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    WARNING = "warning"       # Issue found, not critical
    VIOLATION = "violation"   # Requires immediate action
    PENDING_REVIEW = "pending_review"


class DisclosureType(str, Enum):
    SELLER_DISCLOSURE = "seller_disclosure"
    LEAD_PAINT = "lead_paint"
    AGENCY_DISCLOSURE = "agency_disclosure"
    FAIR_HOUSING = "fair_housing"
    PROPERTY_CONDITION = "property_condition"
    FLOOD_ZONE = "flood_zone"
    RADON = "radon"
    MOLD = "mold"
    SEX_OFFENDER = "sex_offender_registry"
    HOA = "hoa_disclosure"


# REM: =======================================================================================
# REM: STATE REQUIREMENTS — Ohio as default, extensible
# REM: =======================================================================================

OHIO_REQUIRED_DISCLOSURES = {
    "purchase": [
        {"type": DisclosureType.SELLER_DISCLOSURE.value, "name": "Ohio Residential Property Disclosure Form", "statute": "ORC 5302.30", "required": True},
        {"type": DisclosureType.LEAD_PAINT.value, "name": "Lead-Based Paint Disclosure (pre-1978)", "statute": "42 USC 4852d", "required": True, "condition": "built_before_1978"},
        {"type": DisclosureType.AGENCY_DISCLOSURE.value, "name": "Agency Disclosure Statement", "statute": "ORC 4735.56", "required": True},
        {"type": DisclosureType.FAIR_HOUSING.value, "name": "Fair Housing Notice", "statute": "ORC 4112.02", "required": True},
        {"type": DisclosureType.PROPERTY_CONDITION.value, "name": "Property Condition Addendum", "statute": "ORC 5302.30", "required": False},
        {"type": DisclosureType.FLOOD_ZONE.value, "name": "Flood Zone Disclosure", "statute": "42 USC 4012a", "required": True, "condition": "in_flood_zone"},
    ],
    "lease": [
        {"type": DisclosureType.LEAD_PAINT.value, "name": "Lead-Based Paint Disclosure (pre-1978)", "statute": "42 USC 4852d", "required": True, "condition": "built_before_1978"},
        {"type": DisclosureType.AGENCY_DISCLOSURE.value, "name": "Agency Disclosure Statement", "statute": "ORC 4735.56", "required": True},
        {"type": DisclosureType.FAIR_HOUSING.value, "name": "Fair Housing Notice", "statute": "ORC 4112.02", "required": True},
    ],
}

OHIO_CE_REQUIREMENTS = {
    "salesperson": {"hours_required": 30, "renewal_period_years": 3, "core_hours": 9},
    "broker": {"hours_required": 30, "renewal_period_years": 3, "core_hours": 9},
    "managing_broker": {"hours_required": 30, "renewal_period_years": 3, "core_hours": 9, "management_hours": 3},
}

# REM: Fair housing protected classes (Federal + Ohio)
PROTECTED_CLASSES = [
    "race", "color", "religion", "sex", "national_origin",     # Federal (FHA)
    "familial_status", "disability",                             # Federal (FHA)
    "military_status", "ancestry",                               # Ohio additions
]

FAIR_HOUSING_RED_FLAGS = [
    "good neighborhood", "safe area", "family-friendly",
    "no children", "adults only", "young professionals",
    "Christian community", "near churches", "ethnic",
    "walking distance to synagogue", "integrated",
    "master bedroom",  # Some MLS systems have moved away from this term
    "exclusive", "prestigious",
]


# REM: =======================================================================================
# REM: COMPLIANCE CHECK AGENT
# REM: =======================================================================================

class ComplianceCheckAgent(SecureBaseAgent):
    """
    REM: Real estate compliance monitoring agent.
    REM: Tracks licenses, disclosures, fair housing, and CE requirements.
    REM: All compliance checks are audit-logged for regulatory proof.
    """

    AGENT_NAME = "compliance_check_agent"

    CAPABILITIES = [
        "filesystem.read:/data/compliance/*",
        "filesystem.write:/data/compliance/*",
        "filesystem.read:/data/transactions/*",
        "external.none",
    ]

    REQUIRES_APPROVAL_FOR = [
        "override_violation",
        "waive_disclosure",
        "suspend_license",
    ]

    SUPPORTED_ACTIONS = [
        "check_license",
        "list_licenses",
        "add_license",
        "update_license",
        "check_disclosures",
        "verify_fair_housing",
        "check_ce_status",
        "update_ce_credits",
        "compliance_report",
        "override_violation",
        "waive_disclosure",
        "check_all",
    ]

    SKIP_QUARANTINE = True

    def __init__(self):
        super().__init__()
        self._licenses: Dict[str, Dict[str, Any]] = {}
        self._ce_records: Dict[str, Dict[str, Any]] = {}
        self._violations: List[Dict[str, Any]] = []
        self._seed_demo_data()

    def _seed_demo_data(self):
        """REM: Pre-populate with realistic Ohio real estate license data."""
        now = datetime.now(timezone.utc)

        # REM: Active agent — license current
        self._licenses["OH-2024-18834"] = {
            "license_number": "OH-2024-18834",
            "name": "Lisa Chen",
            "type": "salesperson",
            "status": LicenseStatus.ACTIVE.value,
            "state": "OH",
            "brokerage": "RE/MAX North",
            "issued_date": (now - timedelta(days=400)).isoformat(),
            "expiration_date": (now + timedelta(days=695)).isoformat(),
            "email": "lchen@remax.example.com",
        }

        # REM: Agent with license expiring soon
        self._licenses["OH-2023-16221"] = {
            "license_number": "OH-2023-16221",
            "name": "David Park",
            "type": "salesperson",
            "status": LicenseStatus.EXPIRING_SOON.value,
            "state": "OH",
            "brokerage": "Keller Williams",
            "issued_date": (now - timedelta(days=1000)).isoformat(),
            "expiration_date": (now + timedelta(days=45)).isoformat(),
            "email": "dpark@kw.example.com",
        }

        # REM: Broker — active, CE due soon
        self._licenses["OH-2019-09102"] = {
            "license_number": "OH-2019-09102",
            "name": "Margaret Sullivan",
            "type": "managing_broker",
            "status": LicenseStatus.ACTIVE.value,
            "state": "OH",
            "brokerage": "RE/MAX North",
            "issued_date": (now - timedelta(days=2000)).isoformat(),
            "expiration_date": (now + timedelta(days=320)).isoformat(),
            "email": "msullivan@remax.example.com",
        }

        # REM: Expired license — violation
        self._licenses["OH-2020-11456"] = {
            "license_number": "OH-2020-11456",
            "name": "James Rivera",
            "type": "salesperson",
            "status": LicenseStatus.EXPIRED.value,
            "state": "OH",
            "brokerage": "RE/MAX North",
            "issued_date": (now - timedelta(days=1500)).isoformat(),
            "expiration_date": (now - timedelta(days=30)).isoformat(),
            "email": "jrivera@remax.example.com",
        }

        # REM: CE records
        self._ce_records["OH-2024-18834"] = {
            "license_number": "OH-2024-18834",
            "name": "Lisa Chen",
            "hours_completed": 22,
            "hours_required": 30,
            "core_hours_completed": 9,
            "core_hours_required": 9,
            "renewal_deadline": (now + timedelta(days=695)).isoformat(),
            "courses": [
                {"name": "Ohio Real Estate Law Update 2025", "hours": 3, "core": True, "completed": (now - timedelta(days=60)).isoformat()},
                {"name": "Fair Housing Compliance", "hours": 3, "core": True, "completed": (now - timedelta(days=90)).isoformat()},
                {"name": "Ethics in Real Estate", "hours": 3, "core": True, "completed": (now - timedelta(days=120)).isoformat()},
                {"name": "Property Management Basics", "hours": 4, "core": False, "completed": (now - timedelta(days=150)).isoformat()},
                {"name": "Digital Marketing for Agents", "hours": 3, "core": False, "completed": (now - timedelta(days=180)).isoformat()},
                {"name": "Commercial RE Fundamentals", "hours": 6, "core": False, "completed": (now - timedelta(days=200)).isoformat()},
            ],
        }

        self._ce_records["OH-2023-16221"] = {
            "license_number": "OH-2023-16221",
            "name": "David Park",
            "hours_completed": 12,
            "hours_required": 30,
            "core_hours_completed": 3,
            "core_hours_required": 9,
            "renewal_deadline": (now + timedelta(days=45)).isoformat(),
            "courses": [
                {"name": "Ohio Real Estate Law Update 2025", "hours": 3, "core": True, "completed": (now - timedelta(days=30)).isoformat()},
                {"name": "Negotiation Strategies", "hours": 4, "core": False, "completed": (now - timedelta(days=200)).isoformat()},
                {"name": "Residential Appraisal Review", "hours": 5, "core": False, "completed": (now - timedelta(days=300)).isoformat()},
            ],
        }

        # REM: Pre-seed a violation for the expired license
        self._violations.append({
            "violation_id": "VIO-001",
            "type": "expired_license",
            "severity": ComplianceStatus.VIOLATION.value,
            "license_number": "OH-2020-11456",
            "agent_name": "James Rivera",
            "description": "License OH-2020-11456 expired 30 days ago. Agent may not conduct real estate transactions.",
            "statute": "ORC 4735.02",
            "detected_at": now.isoformat(),
            "resolved": False,
        })

        logger.info(
            f"REM: Compliance agent seeded with ::{len(self._licenses)}:: licenses, "
            f"::{len(self._violations)}:: violations_Thank_You"
        )

    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        """REM: Execute compliance check action."""
        action = request.action.lower()
        payload = request.payload

        handlers = {
            "check_license": self._check_license,
            "list_licenses": self._list_licenses,
            "add_license": self._add_license,
            "update_license": self._update_license,
            "check_disclosures": self._check_disclosures,
            "verify_fair_housing": self._verify_fair_housing,
            "check_ce_status": self._check_ce_status,
            "update_ce_credits": self._update_ce_credits,
            "compliance_report": self._compliance_report,
            "override_violation": self._override_violation,
            "waive_disclosure": self._waive_disclosure,
            "check_all": self._check_all,
        }

        handler = handlers.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}. Supported: {list(handlers.keys())}")

        result = handler(payload)

        audit.log(
            AuditEventType.AGENT_ACTION,
            format_qms(f"Compliance_{action.title()}", QMSStatus.THANK_YOU,
                       request_id=request.request_id),
            actor=self.AGENT_NAME,
            details={"action": action}
        )

        return result

    # REM: =======================================================================================
    # REM: LICENSE MANAGEMENT
    # REM: =======================================================================================

    def _check_license(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Check a specific license status."""
        license_num = payload.get("license_number")
        if not license_num or license_num not in self._licenses:
            raise ValueError(f"License not found: {license_num}")

        lic = self._licenses[license_num]
        now = datetime.now(timezone.utc)
        expiration = datetime.fromisoformat(lic["expiration_date"])
        days_until_expiry = (expiration - now).days

        # REM: Auto-update status based on dates
        if days_until_expiry < 0:
            lic["status"] = LicenseStatus.EXPIRED.value
            status = ComplianceStatus.VIOLATION.value
            message = f"License expired {abs(days_until_expiry)} days ago"
        elif days_until_expiry <= 90:
            lic["status"] = LicenseStatus.EXPIRING_SOON.value
            status = ComplianceStatus.WARNING.value
            message = f"License expires in {days_until_expiry} days"
        else:
            status = ComplianceStatus.COMPLIANT.value
            message = f"License valid for {days_until_expiry} days"

        return {
            "license": lic,
            "compliance_status": status,
            "message": message,
            "days_until_expiry": days_until_expiry,
        }

    def _list_licenses(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: List all tracked licenses with status summary."""
        status_filter = payload.get("status")
        brokerage_filter = payload.get("brokerage")

        results = []
        for lic in self._licenses.values():
            if status_filter and lic["status"] != status_filter:
                continue
            if brokerage_filter and lic.get("brokerage") != brokerage_filter:
                continue
            results.append(lic)

        status_counts = {}
        for lic in self._licenses.values():
            s = lic["status"]
            status_counts[s] = status_counts.get(s, 0) + 1

        return {
            "licenses": results,
            "count": len(results),
            "status_summary": status_counts,
        }

    def _add_license(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Add a license to tracking."""
        license_num = payload.get("license_number")
        if not license_num:
            raise ValueError("license_number required")

        lic = {
            "license_number": license_num,
            "name": payload.get("name", ""),
            "type": payload.get("type", "salesperson"),
            "status": LicenseStatus.ACTIVE.value,
            "state": payload.get("state", "OH"),
            "brokerage": payload.get("brokerage", ""),
            "issued_date": payload.get("issued_date", datetime.now(timezone.utc).isoformat()),
            "expiration_date": payload.get("expiration_date", ""),
            "email": payload.get("email", ""),
        }

        self._licenses[license_num] = lic
        return {"license_number": license_num, "status": "added"}

    def _update_license(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Update license details."""
        license_num = payload.get("license_number")
        if not license_num or license_num not in self._licenses:
            raise ValueError(f"License not found: {license_num}")

        lic = self._licenses[license_num]
        updatable = ["name", "type", "status", "brokerage", "expiration_date", "email"]
        updated = []
        for field in updatable:
            if field in payload:
                lic[field] = payload[field]
                updated.append(field)

        return {"license_number": license_num, "updated_fields": updated}

    # REM: =======================================================================================
    # REM: DISCLOSURE VERIFICATION
    # REM: =======================================================================================

    def _check_disclosures(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Check required disclosures for a transaction type and conditions."""
        tx_type = payload.get("transaction_type", "purchase")
        state = payload.get("state", "OH")
        conditions = payload.get("conditions", {})
        provided_disclosures = payload.get("provided", [])

        # REM: Get state requirements (Ohio default)
        if state == "OH":
            requirements = OHIO_REQUIRED_DISCLOSURES.get(tx_type, [])
        else:
            requirements = OHIO_REQUIRED_DISCLOSURES.get(tx_type, [])  # Extensible

        required = []
        for req in requirements:
            # REM: Check conditional requirements
            condition = req.get("condition")
            if condition:
                if not conditions.get(condition, False):
                    continue  # Condition not met, skip

            is_provided = req["type"] in provided_disclosures
            required.append({
                "type": req["type"],
                "name": req["name"],
                "statute": req["statute"],
                "required": req["required"],
                "provided": is_provided,
                "status": ComplianceStatus.COMPLIANT.value if is_provided or not req["required"]
                         else ComplianceStatus.VIOLATION.value,
            })

        missing = [r for r in required if r["required"] and not r["provided"]]

        return {
            "transaction_type": tx_type,
            "state": state,
            "disclosures": required,
            "total_required": sum(1 for r in required if r["required"]),
            "total_provided": sum(1 for r in required if r["provided"]),
            "missing": missing,
            "compliant": len(missing) == 0,
        }

    def _waive_disclosure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Waive a disclosure requirement. REQUIRES APPROVAL."""
        disclosure_type = payload.get("disclosure_type")
        reason = payload.get("reason", "No reason provided")
        transaction_id = payload.get("transaction_id", "N/A")

        audit.log(
            AuditEventType.SECURITY_ALERT,
            format_qms("Compliance_Waive_Disclosure", QMSStatus.THANK_YOU,
                       disclosure=disclosure_type, transaction=transaction_id),
            actor=self.AGENT_NAME,
            details={"disclosure_type": disclosure_type, "reason": reason, "transaction_id": transaction_id}
        )

        return {
            "disclosure_type": disclosure_type,
            "waived": True,
            "reason": reason,
            "waived_at": datetime.now(timezone.utc).isoformat(),
            "warning": "Waiving required disclosures may create legal liability.",
        }

    # REM: =======================================================================================
    # REM: FAIR HOUSING COMPLIANCE
    # REM: =======================================================================================

    def _verify_fair_housing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: Scan listing text for fair housing red flags.
        REM: This is a keyword-based check — not a legal opinion.
        """
        text = payload.get("text", "")
        listing_id = payload.get("listing_id", "unknown")

        if not text:
            raise ValueError("text required — provide listing description to check")

        text_lower = text.lower()
        flags_found = []

        for flag in FAIR_HOUSING_RED_FLAGS:
            if flag.lower() in text_lower:
                flags_found.append({
                    "phrase": flag,
                    "reason": "Potentially discriminatory language per Fair Housing Act",
                })

        status = ComplianceStatus.COMPLIANT.value if not flags_found else ComplianceStatus.WARNING.value

        if flags_found:
            audit.log(
                AuditEventType.SECURITY_ALERT,
                format_qms("Compliance_FairHousing_Flag", QMSStatus.THANK_YOU,
                           listing=listing_id, flags=len(flags_found)),
                actor=self.AGENT_NAME,
                details={"listing_id": listing_id, "flags": flags_found}
            )

        return {
            "listing_id": listing_id,
            "compliance_status": status,
            "flags_found": flags_found,
            "flag_count": len(flags_found),
            "protected_classes": PROTECTED_CLASSES,
            "disclaimer": "This is an automated keyword check, not legal advice. Consult a fair housing attorney for compliance guidance.",
        }

    # REM: =======================================================================================
    # REM: CONTINUING EDUCATION
    # REM: =======================================================================================

    def _check_ce_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Check continuing education status for a licensee."""
        license_num = payload.get("license_number")

        if license_num and license_num in self._ce_records:
            record = self._ce_records[license_num]
        elif license_num:
            return {
                "license_number": license_num,
                "status": "no_record",
                "message": "No CE records found for this license number.",
            }
        else:
            # REM: Return all CE records
            results = []
            for num, rec in self._ce_records.items():
                hours_remaining = rec["hours_required"] - rec["hours_completed"]
                core_remaining = rec["core_hours_required"] - rec["core_hours_completed"]
                deadline = datetime.fromisoformat(rec["renewal_deadline"])
                days_until = (deadline - datetime.now(timezone.utc)).days

                status = ComplianceStatus.COMPLIANT.value
                if hours_remaining > 0 and days_until < 90:
                    status = ComplianceStatus.WARNING.value
                if hours_remaining > 0 and days_until < 30:
                    status = ComplianceStatus.VIOLATION.value

                results.append({
                    "license_number": num,
                    "name": rec["name"],
                    "hours_completed": rec["hours_completed"],
                    "hours_required": rec["hours_required"],
                    "hours_remaining": hours_remaining,
                    "core_remaining": core_remaining,
                    "days_until_deadline": days_until,
                    "status": status,
                })
            return {"ce_records": results, "count": len(results)}

        hours_remaining = record["hours_required"] - record["hours_completed"]
        core_remaining = record["core_hours_required"] - record["core_hours_completed"]
        deadline = datetime.fromisoformat(record["renewal_deadline"])
        days_until = (deadline - datetime.now(timezone.utc)).days

        status = ComplianceStatus.COMPLIANT.value
        if hours_remaining > 0 and days_until < 90:
            status = ComplianceStatus.WARNING.value
        if hours_remaining > 0 and days_until < 30:
            status = ComplianceStatus.VIOLATION.value

        return {
            "license_number": license_num,
            "name": record["name"],
            "hours_completed": record["hours_completed"],
            "hours_required": record["hours_required"],
            "hours_remaining": hours_remaining,
            "core_hours_completed": record["core_hours_completed"],
            "core_hours_required": record["core_hours_required"],
            "core_remaining": core_remaining,
            "courses": record["courses"],
            "renewal_deadline": record["renewal_deadline"],
            "days_until_deadline": days_until,
            "compliance_status": status,
        }

    def _update_ce_credits(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Record completed CE course."""
        license_num = payload.get("license_number")
        if not license_num:
            raise ValueError("license_number required")

        if license_num not in self._ce_records:
            self._ce_records[license_num] = {
                "license_number": license_num,
                "name": self._licenses.get(license_num, {}).get("name", "Unknown"),
                "hours_completed": 0,
                "hours_required": 30,
                "core_hours_completed": 0,
                "core_hours_required": 9,
                "renewal_deadline": (datetime.now(timezone.utc) + timedelta(days=1095)).isoformat(),
                "courses": [],
            }

        record = self._ce_records[license_num]
        course = {
            "name": payload.get("course_name", "Unnamed Course"),
            "hours": payload.get("hours", 0),
            "core": payload.get("core", False),
            "completed": payload.get("completed_date", datetime.now(timezone.utc).isoformat()),
        }

        record["courses"].append(course)
        record["hours_completed"] += course["hours"]
        if course["core"]:
            record["core_hours_completed"] += course["hours"]

        return {
            "license_number": license_num,
            "course_added": course["name"],
            "hours_added": course["hours"],
            "total_hours": record["hours_completed"],
            "hours_remaining": record["hours_required"] - record["hours_completed"],
        }

    # REM: =======================================================================================
    # REM: VIOLATION MANAGEMENT
    # REM: =======================================================================================

    def _override_violation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Override/resolve a violation. REQUIRES APPROVAL."""
        violation_id = payload.get("violation_id")
        reason = payload.get("reason", "No reason provided")

        for v in self._violations:
            if v["violation_id"] == violation_id:
                v["resolved"] = True
                v["resolved_at"] = datetime.now(timezone.utc).isoformat()
                v["resolution_reason"] = reason

                audit.log(
                    AuditEventType.SECURITY_ALERT,
                    format_qms("Compliance_Override_Violation", QMSStatus.THANK_YOU,
                               violation=violation_id),
                    actor=self.AGENT_NAME,
                    details={"violation_id": violation_id, "reason": reason}
                )

                return {"violation_id": violation_id, "resolved": True, "reason": reason}

        raise ValueError(f"Violation not found: {violation_id}")

    # REM: =======================================================================================
    # REM: REPORTING
    # REM: =======================================================================================

    def _compliance_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Generate a brokerage-wide compliance report."""
        brokerage = payload.get("brokerage")

        # REM: License summary
        licenses = list(self._licenses.values())
        if brokerage:
            licenses = [l for l in licenses if l.get("brokerage") == brokerage]

        active = sum(1 for l in licenses if l["status"] == LicenseStatus.ACTIVE.value)
        expiring = sum(1 for l in licenses if l["status"] == LicenseStatus.EXPIRING_SOON.value)
        expired = sum(1 for l in licenses if l["status"] == LicenseStatus.EXPIRED.value)

        # REM: CE summary
        ce_compliant = 0
        ce_warning = 0
        ce_violation = 0
        for lic in licenses:
            ce = self._ce_records.get(lic["license_number"])
            if ce:
                remaining = ce["hours_required"] - ce["hours_completed"]
                deadline = datetime.fromisoformat(ce["renewal_deadline"])
                days = (deadline - datetime.now(timezone.utc)).days
                if remaining <= 0:
                    ce_compliant += 1
                elif days < 30:
                    ce_violation += 1
                elif days < 90:
                    ce_warning += 1
                else:
                    ce_compliant += 1

        # REM: Open violations
        open_violations = [v for v in self._violations if not v["resolved"]]

        overall = ComplianceStatus.COMPLIANT.value
        if expiring > 0 or ce_warning > 0:
            overall = ComplianceStatus.WARNING.value
        if expired > 0 or ce_violation > 0 or open_violations:
            overall = ComplianceStatus.VIOLATION.value

        return {
            "brokerage": brokerage or "All",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "overall_status": overall,
            "licenses": {
                "total": len(licenses),
                "active": active,
                "expiring_soon": expiring,
                "expired": expired,
            },
            "continuing_education": {
                "compliant": ce_compliant,
                "warning": ce_warning,
                "violation": ce_violation,
            },
            "violations": {
                "open": len(open_violations),
                "details": open_violations,
            },
        }

    def _check_all(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Run all compliance checks and return a comprehensive status."""
        license_report = self._compliance_report(payload)
        deadline_warnings = []

        now = datetime.now(timezone.utc)
        for lic in self._licenses.values():
            exp = datetime.fromisoformat(lic["expiration_date"])
            days = (exp - now).days
            if days <= 90:
                deadline_warnings.append({
                    "type": "license_expiration",
                    "license_number": lic["license_number"],
                    "name": lic["name"],
                    "days_remaining": days,
                    "severity": "violation" if days < 0 else "warning",
                })

        for num, ce in self._ce_records.items():
            remaining = ce["hours_required"] - ce["hours_completed"]
            if remaining > 0:
                deadline = datetime.fromisoformat(ce["renewal_deadline"])
                days = (deadline - now).days
                if days <= 90:
                    deadline_warnings.append({
                        "type": "ce_deadline",
                        "license_number": num,
                        "name": ce["name"],
                        "hours_remaining": remaining,
                        "days_remaining": days,
                        "severity": "violation" if days < 30 else "warning",
                    })

        return {
            "checked_at": now.isoformat(),
            "overall_status": license_report["overall_status"],
            "license_summary": license_report["licenses"],
            "ce_summary": license_report["continuing_education"],
            "open_violations": license_report["violations"]["open"],
            "deadline_warnings": deadline_warnings,
            "warning_count": len(deadline_warnings),
        }


# REM: =======================================================================================
# REM: CELERY TASKS
# REM: =======================================================================================

from celery import shared_task

_agent_instance = None


def _get_agent():
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ComplianceCheckAgent()
    return _agent_instance


@shared_task(name="compliance_check_agent.execute")
def execute_action(action: str, payload: dict = None):
    """REM: Generic Celery task for compliance check actions."""
    agent = _get_agent()
    request = AgentRequest(action=action, payload=payload or {}, requester="celery")
    response = agent.handle_request(request)
    return {"success": response.success, "result": response.result, "error": response.error}


@shared_task(name="compliance_check_agent.daily_check")
def daily_compliance_check():
    """REM: Scheduled task — daily compliance sweep."""
    agent = _get_agent()
    request = AgentRequest(action="check_all", payload={}, requester="celery:beat")
    response = agent.handle_request(request)
    return response.result


@shared_task(name="compliance_check_agent.health")
def health():
    """REM: Health check."""
    agent = _get_agent()
    return agent.heartbeat()


# REM: =======================================================================================
# REM: EXPORTS
# REM: =======================================================================================

__all__ = ["ComplianceCheckAgent"]
