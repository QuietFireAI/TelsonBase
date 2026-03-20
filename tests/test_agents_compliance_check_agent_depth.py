# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_agents_compliance_check_agent_depth.py
# REM: Depth coverage for agents/compliance_check_agent.py
# REM: Pure in-memory agent — all tests run without Redis/DB.

import sys
from unittest.mock import MagicMock

if "celery" not in sys.modules:
    _celery_mock = MagicMock()
    _celery_mock.shared_task = lambda *args, **kwargs: (lambda f: f)
    sys.modules["celery"] = _celery_mock

import pytest
from datetime import datetime, timedelta, timezone

from agents.compliance_check_agent import (
    ComplianceCheckAgent,
    ComplianceStatus,
    DisclosureType,
    LicenseStatus,
    OHIO_CE_REQUIREMENTS,
    OHIO_REQUIRED_DISCLOSURES,
    PROTECTED_CLASSES,
    FAIR_HOUSING_RED_FLAGS,
)
from agents.base import AgentRequest


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def agent():
    return ComplianceCheckAgent()


def make_request(action, payload=None):
    return AgentRequest(action=action, payload=payload or {}, requester="test")


# ═══════════════════════════════════════════════════════════════════════════════
# Constants and Enums
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnumsAndConstants:
    def test_license_status_values(self):
        assert LicenseStatus.ACTIVE.value == "active"
        assert LicenseStatus.EXPIRED.value == "expired"
        assert LicenseStatus.EXPIRING_SOON.value == "expiring_soon"
        assert LicenseStatus.SUSPENDED.value == "suspended"
        assert LicenseStatus.PENDING_RENEWAL.value == "pending_renewal"

    def test_compliance_status_values(self):
        assert ComplianceStatus.COMPLIANT.value == "compliant"
        assert ComplianceStatus.WARNING.value == "warning"
        assert ComplianceStatus.VIOLATION.value == "violation"
        assert ComplianceStatus.PENDING_REVIEW.value == "pending_review"

    def test_disclosure_types_exist(self):
        assert DisclosureType.SELLER_DISCLOSURE.value == "seller_disclosure"
        assert DisclosureType.LEAD_PAINT.value == "lead_paint"
        assert DisclosureType.FAIR_HOUSING.value == "fair_housing"
        assert DisclosureType.FLOOD_ZONE.value == "flood_zone"

    def test_ohio_ce_requirements_has_salesperson(self):
        assert "salesperson" in OHIO_CE_REQUIREMENTS
        assert OHIO_CE_REQUIREMENTS["salesperson"]["hours_required"] == 30

    def test_ohio_ce_requirements_has_broker(self):
        assert "broker" in OHIO_CE_REQUIREMENTS
        assert OHIO_CE_REQUIREMENTS["broker"]["renewal_period_years"] == 3

    def test_ohio_ce_requirements_managing_broker_has_management_hours(self):
        assert "managing_broker" in OHIO_CE_REQUIREMENTS
        assert OHIO_CE_REQUIREMENTS["managing_broker"]["management_hours"] == 3

    def test_protected_classes_has_federal_fha(self):
        assert "race" in PROTECTED_CLASSES
        assert "disability" in PROTECTED_CLASSES
        assert "familial_status" in PROTECTED_CLASSES

    def test_protected_classes_has_ohio_additions(self):
        assert "military_status" in PROTECTED_CLASSES
        assert "ancestry" in PROTECTED_CLASSES

    def test_fair_housing_red_flags_non_empty(self):
        assert len(FAIR_HOUSING_RED_FLAGS) > 0

    def test_ohio_required_disclosures_purchase_has_entries(self):
        assert "purchase" in OHIO_REQUIRED_DISCLOSURES
        assert len(OHIO_REQUIRED_DISCLOSURES["purchase"]) > 0

    def test_ohio_required_disclosures_lease_has_entries(self):
        assert "lease" in OHIO_REQUIRED_DISCLOSURES
        assert len(OHIO_REQUIRED_DISCLOSURES["lease"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Initialization and Seeded Data
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentInit:
    def test_agent_name(self, agent):
        assert agent.AGENT_NAME == "compliance_check_agent"

    def test_capabilities_list(self, agent):
        assert isinstance(agent.CAPABILITIES, list)
        assert len(agent.CAPABILITIES) > 0

    def test_requires_approval_for(self, agent):
        assert "override_violation" in agent.REQUIRES_APPROVAL_FOR
        assert "waive_disclosure" in agent.REQUIRES_APPROVAL_FOR
        assert "suspend_license" in agent.REQUIRES_APPROVAL_FOR

    def test_supported_actions(self, agent):
        assert "check_license" in agent.SUPPORTED_ACTIONS
        assert "check_all" in agent.SUPPORTED_ACTIONS
        assert "compliance_report" in agent.SUPPORTED_ACTIONS

    def test_seeded_licenses_exist(self, agent):
        assert len(agent._licenses) == 4

    def test_seeded_active_license(self, agent):
        assert "OH-2024-18834" in agent._licenses
        assert agent._licenses["OH-2024-18834"]["status"] == LicenseStatus.ACTIVE.value

    def test_seeded_expiring_license(self, agent):
        assert "OH-2023-16221" in agent._licenses
        assert agent._licenses["OH-2023-16221"]["status"] == LicenseStatus.EXPIRING_SOON.value

    def test_seeded_expired_license(self, agent):
        assert "OH-2020-11456" in agent._licenses
        assert agent._licenses["OH-2020-11456"]["status"] == LicenseStatus.EXPIRED.value

    def test_seeded_violations(self, agent):
        assert len(agent._violations) >= 1
        assert agent._violations[0]["violation_id"] == "VIO-001"

    def test_seeded_ce_records(self, agent):
        assert "OH-2024-18834" in agent._ce_records
        assert "OH-2023-16221" in agent._ce_records


# ═══════════════════════════════════════════════════════════════════════════════
# execute() — dispatch table
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecuteDispatch:
    def test_unknown_action_raises_value_error(self, agent):
        req = make_request("nonexistent_action")
        with pytest.raises(ValueError, match="Unknown action"):
            agent.execute(req)

    def test_list_licenses_via_execute(self, agent):
        req = make_request("list_licenses")
        result = agent.execute(req)
        assert "licenses" in result

    def test_check_all_via_execute(self, agent):
        req = make_request("check_all")
        result = agent.execute(req)
        assert "overall_status" in result


# ═══════════════════════════════════════════════════════════════════════════════
# _check_license
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckLicense:
    def test_check_active_license(self, agent):
        result = agent._check_license({"license_number": "OH-2024-18834"})
        assert result["compliance_status"] == ComplianceStatus.COMPLIANT.value
        assert result["days_until_expiry"] > 90

    def test_check_expiring_license_returns_warning(self, agent):
        result = agent._check_license({"license_number": "OH-2023-16221"})
        assert result["compliance_status"] == ComplianceStatus.WARNING.value
        assert 0 < result["days_until_expiry"] <= 90

    def test_check_expired_license_returns_violation(self, agent):
        result = agent._check_license({"license_number": "OH-2020-11456"})
        assert result["compliance_status"] == ComplianceStatus.VIOLATION.value
        assert result["days_until_expiry"] < 0

    def test_check_license_not_found_raises(self, agent):
        with pytest.raises(ValueError, match="License not found"):
            agent._check_license({"license_number": "XX-9999-00000"})

    def test_check_license_no_number_raises(self, agent):
        with pytest.raises(ValueError):
            agent._check_license({})

    def test_check_license_returns_license_dict(self, agent):
        result = agent._check_license({"license_number": "OH-2024-18834"})
        assert "license" in result
        assert result["license"]["name"] == "Lisa Chen"

    def test_check_license_returns_days_until_expiry(self, agent):
        result = agent._check_license({"license_number": "OH-2019-09102"})
        assert isinstance(result["days_until_expiry"], int)

    def test_check_expired_updates_status_in_place(self, agent):
        # Expired license should have its status field auto-updated
        result = agent._check_license({"license_number": "OH-2020-11456"})
        assert agent._licenses["OH-2020-11456"]["status"] == LicenseStatus.EXPIRED.value


# ═══════════════════════════════════════════════════════════════════════════════
# _list_licenses
# ═══════════════════════════════════════════════════════════════════════════════

class TestListLicenses:
    def test_list_all_returns_four(self, agent):
        result = agent._list_licenses({})
        assert result["count"] == 4
        assert len(result["licenses"]) == 4

    def test_list_filter_by_status_active(self, agent):
        result = agent._list_licenses({"status": "active"})
        for lic in result["licenses"]:
            assert lic["status"] == "active"

    def test_list_filter_by_brokerage(self, agent):
        result = agent._list_licenses({"brokerage": "RE/MAX North"})
        for lic in result["licenses"]:
            assert lic["brokerage"] == "RE/MAX North"

    def test_list_unmatched_filter_returns_empty(self, agent):
        result = agent._list_licenses({"brokerage": "No Such Brokerage"})
        assert result["count"] == 0

    def test_list_includes_status_summary(self, agent):
        result = agent._list_licenses({})
        assert "status_summary" in result
        assert isinstance(result["status_summary"], dict)

    def test_list_status_summary_has_expired(self, agent):
        result = agent._list_licenses({})
        assert "expired" in result["status_summary"]


# ═══════════════════════════════════════════════════════════════════════════════
# _add_license and _update_license
# ═══════════════════════════════════════════════════════════════════════════════

class TestAddUpdateLicense:
    def test_add_license_minimal(self, agent):
        result = agent._add_license({
            "license_number": "OH-TEST-99001",
            "name": "Test Agent",
            "expiration_date": (datetime.now(timezone.utc) + timedelta(days=400)).isoformat(),
        })
        assert result["status"] == "added"
        assert "OH-TEST-99001" in agent._licenses

    def test_add_license_defaults_to_active(self, agent):
        agent._add_license({
            "license_number": "OH-TEST-99002",
            "expiration_date": (datetime.now(timezone.utc) + timedelta(days=400)).isoformat(),
        })
        assert agent._licenses["OH-TEST-99002"]["status"] == LicenseStatus.ACTIVE.value

    def test_add_license_with_all_fields(self, agent):
        agent._add_license({
            "license_number": "OH-TEST-99003",
            "name": "Full Agent",
            "type": "broker",
            "state": "OH",
            "brokerage": "Test Brokerage",
            "email": "test@brokerage.com",
            "expiration_date": (datetime.now(timezone.utc) + timedelta(days=500)).isoformat(),
        })
        lic = agent._licenses["OH-TEST-99003"]
        assert lic["type"] == "broker"
        assert lic["brokerage"] == "Test Brokerage"

    def test_add_license_no_number_raises(self, agent):
        with pytest.raises(ValueError, match="license_number required"):
            agent._add_license({})

    def test_update_license_name(self, agent):
        agent._add_license({"license_number": "OH-UPD-00001", "name": "Original Name",
                             "expiration_date": (datetime.now(timezone.utc) + timedelta(days=400)).isoformat()})
        result = agent._update_license({"license_number": "OH-UPD-00001", "name": "Updated Name"})
        assert "name" in result["updated_fields"]
        assert agent._licenses["OH-UPD-00001"]["name"] == "Updated Name"

    def test_update_license_not_found_raises(self, agent):
        with pytest.raises(ValueError, match="License not found"):
            agent._update_license({"license_number": "XX-NOTFOUND"})

    def test_update_license_no_number_raises(self, agent):
        with pytest.raises(ValueError):
            agent._update_license({})

    def test_update_license_multiple_fields(self, agent):
        agent._add_license({"license_number": "OH-UPD-00002", "name": "Before",
                             "expiration_date": (datetime.now(timezone.utc) + timedelta(days=400)).isoformat()})
        result = agent._update_license({
            "license_number": "OH-UPD-00002",
            "name": "After",
            "status": "suspended",
            "brokerage": "New Brokerage",
        })
        assert len(result["updated_fields"]) == 3

    def test_update_license_ignores_non_updatable_fields(self, agent):
        agent._add_license({"license_number": "OH-UPD-00003",
                             "expiration_date": (datetime.now(timezone.utc) + timedelta(days=400)).isoformat()})
        result = agent._update_license({
            "license_number": "OH-UPD-00003",
            "license_number_new": "SHOULD-IGNORE",
        })
        assert "license_number_new" not in result["updated_fields"]


# ═══════════════════════════════════════════════════════════════════════════════
# _check_disclosures
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckDisclosures:
    def test_purchase_all_provided(self, agent):
        provided = ["seller_disclosure", "lead_paint", "agency_disclosure", "fair_housing", "flood_zone"]
        result = agent._check_disclosures({
            "transaction_type": "purchase",
            "state": "OH",
            "conditions": {"built_before_1978": True, "in_flood_zone": True},
            "provided": provided,
        })
        assert result["compliant"] is True

    def test_purchase_missing_required_disclosure(self, agent):
        result = agent._check_disclosures({
            "transaction_type": "purchase",
            "state": "OH",
            "conditions": {},
            "provided": [],
        })
        assert result["compliant"] is False
        assert len(result["missing"]) > 0

    def test_purchase_agency_disclosure_always_required(self, agent):
        result = agent._check_disclosures({
            "transaction_type": "purchase",
            "state": "OH",
            "provided": [],
        })
        missing_types = [m["type"] for m in result["missing"]]
        assert "agency_disclosure" in missing_types

    def test_lead_paint_skipped_if_condition_not_met(self, agent):
        result = agent._check_disclosures({
            "transaction_type": "purchase",
            "state": "OH",
            "conditions": {"built_before_1978": False},
            "provided": ["seller_disclosure", "agency_disclosure", "fair_housing"],
        })
        # Lead paint not required when built_before_1978 is False
        disclosure_types = [d["type"] for d in result["disclosures"]]
        assert "lead_paint" not in disclosure_types

    def test_flood_zone_skipped_if_not_in_flood_zone(self, agent):
        result = agent._check_disclosures({
            "transaction_type": "purchase",
            "conditions": {"in_flood_zone": False},
            "provided": [],
        })
        disclosure_types = [d["type"] for d in result["disclosures"]]
        assert "flood_zone" not in disclosure_types

    def test_lease_type(self, agent):
        result = agent._check_disclosures({
            "transaction_type": "lease",
            "state": "OH",
            "provided": ["agency_disclosure", "fair_housing"],
            "conditions": {},
        })
        assert "transaction_type" in result
        assert result["transaction_type"] == "lease"

    def test_returns_total_required_and_provided(self, agent):
        result = agent._check_disclosures({
            "transaction_type": "purchase",
            "provided": ["seller_disclosure"],
        })
        assert "total_required" in result
        assert "total_provided" in result

    def test_provided_disclosure_status_compliant(self, agent):
        result = agent._check_disclosures({
            "transaction_type": "lease",
            "conditions": {},
            "provided": ["agency_disclosure"],
        })
        agency = next(d for d in result["disclosures"] if d["type"] == "agency_disclosure")
        assert agency["status"] == ComplianceStatus.COMPLIANT.value

    def test_unknown_tx_type_returns_empty(self, agent):
        result = agent._check_disclosures({
            "transaction_type": "commercial_lease",
            "provided": [],
        })
        # No requirements defined for unknown type
        assert result["total_required"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# _verify_fair_housing
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyFairHousing:
    def test_clean_text_no_flags(self, agent):
        result = agent._verify_fair_housing({
            "text": "Beautiful 3BR home, updated kitchen, new roof.",
            "listing_id": "L-001",
        })
        assert result["compliance_status"] == ComplianceStatus.COMPLIANT.value
        assert result["flag_count"] == 0

    def test_discriminatory_language_flagged(self, agent):
        result = agent._verify_fair_housing({
            "text": "Great family-friendly neighborhood near churches.",
            "listing_id": "L-002",
        })
        assert result["compliance_status"] == ComplianceStatus.WARNING.value
        assert result["flag_count"] > 0

    def test_no_children_flagged(self, agent):
        result = agent._verify_fair_housing({
            "text": "Adults only community, no children allowed.",
            "listing_id": "L-003",
        })
        assert result["flag_count"] >= 1

    def test_empty_text_raises(self, agent):
        with pytest.raises(ValueError, match="text required"):
            agent._verify_fair_housing({"listing_id": "L-004"})

    def test_returns_protected_classes(self, agent):
        result = agent._verify_fair_housing({"text": "Nice house.", "listing_id": "L-005"})
        assert "protected_classes" in result
        assert "race" in result["protected_classes"]

    def test_returns_disclaimer(self, agent):
        result = agent._verify_fair_housing({"text": "Nice house.", "listing_id": "L-006"})
        assert "disclaimer" in result

    def test_multiple_flags_detected(self, agent):
        result = agent._verify_fair_housing({
            "text": "Good neighborhood, safe area, walking distance to synagogue.",
            "listing_id": "L-007",
        })
        assert result["flag_count"] >= 2

    def test_default_listing_id(self, agent):
        result = agent._verify_fair_housing({"text": "Great home."})
        assert result["listing_id"] == "unknown"

    def test_flags_have_phrase_and_reason(self, agent):
        result = agent._verify_fair_housing({
            "text": "adults only, exclusive area.",
            "listing_id": "L-008",
        })
        if result["flags_found"]:
            flag = result["flags_found"][0]
            assert "phrase" in flag
            assert "reason" in flag


# ═══════════════════════════════════════════════════════════════════════════════
# _check_ce_status
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckCEStatus:
    def test_check_specific_license_with_record(self, agent):
        result = agent._check_ce_status({"license_number": "OH-2024-18834"})
        assert "hours_completed" in result
        assert result["hours_completed"] == 22

    def test_check_specific_license_courses_returned(self, agent):
        result = agent._check_ce_status({"license_number": "OH-2024-18834"})
        assert "courses" in result
        assert len(result["courses"]) > 0

    def test_check_specific_license_no_record(self, agent):
        result = agent._check_ce_status({"license_number": "OH-2020-11456"})
        assert result["status"] == "no_record"

    def test_check_all_records_no_license_filter(self, agent):
        result = agent._check_ce_status({})
        assert "ce_records" in result
        assert result["count"] >= 2

    def test_check_expiring_deadline_warning(self, agent):
        result = agent._check_ce_status({"license_number": "OH-2023-16221"})
        # David Park has 12/30 hours with 45 days left — WARNING
        assert result["compliance_status"] in (
            ComplianceStatus.WARNING.value, ComplianceStatus.VIOLATION.value
        )

    def test_check_hours_remaining_calculated(self, agent):
        result = agent._check_ce_status({"license_number": "OH-2024-18834"})
        expected_remaining = result["hours_required"] - result["hours_completed"]
        assert result["hours_remaining"] == expected_remaining

    def test_all_records_include_days_until_deadline(self, agent):
        result = agent._check_ce_status({})
        for rec in result["ce_records"]:
            assert "days_until_deadline" in rec


# ═══════════════════════════════════════════════════════════════════════════════
# _update_ce_credits
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdateCECredits:
    def test_add_course_to_existing_record(self, agent):
        before = agent._ce_records["OH-2024-18834"]["hours_completed"]
        result = agent._update_ce_credits({
            "license_number": "OH-2024-18834",
            "course_name": "New Test Course",
            "hours": 3,
            "core": False,
        })
        assert result["hours_added"] == 3
        assert agent._ce_records["OH-2024-18834"]["hours_completed"] == before + 3

    def test_add_core_hours(self, agent):
        before_core = agent._ce_records["OH-2024-18834"]["core_hours_completed"]
        agent._update_ce_credits({
            "license_number": "OH-2024-18834",
            "course_name": "Core Course",
            "hours": 3,
            "core": True,
        })
        assert agent._ce_records["OH-2024-18834"]["core_hours_completed"] == before_core + 3

    def test_add_course_creates_new_record_if_missing(self, agent):
        license_num = "OH-NEW-88001"
        agent._add_license({
            "license_number": license_num,
            "name": "New Agent",
            "expiration_date": (datetime.now(timezone.utc) + timedelta(days=400)).isoformat(),
        })
        result = agent._update_ce_credits({
            "license_number": license_num,
            "course_name": "First Course",
            "hours": 4,
        })
        assert license_num in agent._ce_records
        assert result["total_hours"] == 4

    def test_update_ce_no_license_raises(self, agent):
        with pytest.raises(ValueError, match="license_number required"):
            agent._update_ce_credits({})

    def test_update_returns_hours_remaining(self, agent):
        result = agent._update_ce_credits({
            "license_number": "OH-2024-18834",
            "course_name": "Hours Remaining Test",
            "hours": 1,
        })
        assert "hours_remaining" in result

    def test_course_appended_to_courses_list(self, agent):
        before_count = len(agent._ce_records["OH-2024-18834"]["courses"])
        agent._update_ce_credits({
            "license_number": "OH-2024-18834",
            "course_name": "Appended Course",
            "hours": 2,
        })
        after_count = len(agent._ce_records["OH-2024-18834"]["courses"])
        assert after_count == before_count + 1


# ═══════════════════════════════════════════════════════════════════════════════
# _override_violation
# ═══════════════════════════════════════════════════════════════════════════════

class TestOverrideViolation:
    def test_resolve_existing_violation(self, agent):
        # Re-add VIO-001 as unresolved if it was resolved in a prior test
        for v in agent._violations:
            if v["violation_id"] == "VIO-001":
                v["resolved"] = False
        result = agent._override_violation({"violation_id": "VIO-001", "reason": "Test override"})
        assert result["resolved"] is True
        assert result["violation_id"] == "VIO-001"

    def test_resolved_violation_has_timestamp(self, agent):
        for v in agent._violations:
            if v["violation_id"] == "VIO-001":
                v["resolved"] = False
        agent._override_violation({"violation_id": "VIO-001", "reason": "Ts test"})
        viol = next(v for v in agent._violations if v["violation_id"] == "VIO-001")
        assert "resolved_at" in viol

    def test_resolve_non_existent_violation_raises(self, agent):
        with pytest.raises(ValueError, match="Violation not found"):
            agent._override_violation({"violation_id": "VIO-NOTREAL"})

    def test_resolution_reason_stored(self, agent):
        # Add a fresh violation and resolve it
        agent._violations.append({
            "violation_id": "VIO-TEST-001",
            "type": "test",
            "resolved": False,
        })
        agent._override_violation({"violation_id": "VIO-TEST-001", "reason": "Cleared by test"})
        v = next(v for v in agent._violations if v["violation_id"] == "VIO-TEST-001")
        assert v["resolution_reason"] == "Cleared by test"


# ═══════════════════════════════════════════════════════════════════════════════
# _waive_disclosure
# ═══════════════════════════════════════════════════════════════════════════════

class TestWaiveDisclosure:
    def test_waive_returns_waived_true(self, agent):
        result = agent._waive_disclosure({
            "disclosure_type": "lead_paint",
            "reason": "Property post-1978",
            "transaction_id": "TX-001",
        })
        assert result["waived"] is True

    def test_waive_returns_warning(self, agent):
        result = agent._waive_disclosure({"disclosure_type": "flood_zone"})
        assert "warning" in result

    def test_waive_includes_timestamp(self, agent):
        result = agent._waive_disclosure({"disclosure_type": "seller_disclosure"})
        assert "waived_at" in result

    def test_waive_default_reason(self, agent):
        result = agent._waive_disclosure({"disclosure_type": "radon"})
        assert result["waived"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# _compliance_report
# ═══════════════════════════════════════════════════════════════════════════════

class TestComplianceReport:
    def test_report_all_brokerages(self, agent):
        result = agent._compliance_report({})
        assert result["brokerage"] == "All"
        assert "licenses" in result
        assert "continuing_education" in result
        assert "violations" in result

    def test_report_by_brokerage(self, agent):
        result = agent._compliance_report({"brokerage": "RE/MAX North"})
        assert result["brokerage"] == "RE/MAX North"
        assert result["licenses"]["total"] >= 1

    def test_report_license_summary_fields(self, agent):
        result = agent._compliance_report({})
        lic = result["licenses"]
        assert "total" in lic
        assert "active" in lic
        assert "expiring_soon" in lic
        assert "expired" in lic

    def test_report_expired_causes_violation_status(self, agent):
        result = agent._compliance_report({})
        assert result["overall_status"] == ComplianceStatus.VIOLATION.value

    def test_report_ce_summary_fields(self, agent):
        result = agent._compliance_report({})
        ce = result["continuing_education"]
        assert "compliant" in ce
        assert "warning" in ce
        assert "violation" in ce

    def test_report_violations_section(self, agent):
        result = agent._compliance_report({})
        assert "violations" in result
        assert "open" in result["violations"]

    def test_report_unknown_brokerage_returns_empty(self, agent):
        result = agent._compliance_report({"brokerage": "No Such Brokerage Inc"})
        assert result["licenses"]["total"] == 0

    def test_report_has_generated_at(self, agent):
        result = agent._compliance_report({})
        assert "generated_at" in result


# ═══════════════════════════════════════════════════════════════════════════════
# _check_all
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckAll:
    def test_check_all_returns_overall_status(self, agent):
        result = agent._check_all({})
        assert "overall_status" in result

    def test_check_all_returns_deadline_warnings(self, agent):
        result = agent._check_all({})
        assert "deadline_warnings" in result
        assert isinstance(result["deadline_warnings"], list)

    def test_check_all_has_license_summary(self, agent):
        result = agent._check_all({})
        assert "license_summary" in result

    def test_check_all_has_ce_summary(self, agent):
        result = agent._check_all({})
        assert "ce_summary" in result

    def test_check_all_has_open_violations(self, agent):
        result = agent._check_all({})
        assert "open_violations" in result

    def test_check_all_has_checked_at(self, agent):
        result = agent._check_all({})
        assert "checked_at" in result

    def test_check_all_expired_license_in_deadline_warnings(self, agent):
        result = agent._check_all({})
        expired_warnings = [
            w for w in result["deadline_warnings"]
            if w.get("type") == "license_expiration" and w.get("severity") == "violation"
        ]
        assert len(expired_warnings) >= 1

    def test_check_all_warning_count(self, agent):
        result = agent._check_all({})
        assert result["warning_count"] == len(result["deadline_warnings"])

    def test_check_all_ce_deadline_warnings_included(self, agent):
        result = agent._check_all({})
        ce_warnings = [
            w for w in result["deadline_warnings"]
            if w.get("type") == "ce_deadline"
        ]
        # David Park has only 12/30 hours with 45 days remaining — should flag
        assert len(ce_warnings) >= 1
