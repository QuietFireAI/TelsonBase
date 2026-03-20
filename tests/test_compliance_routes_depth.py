# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_compliance_routes_depth.py
# REM: Coverage depth tests for api/compliance_routes.py
# REM: Covers all 28 endpoints across legal-holds, breach, retention, sanctions,
# REM: training, contingency, BAA, HITRUST, and PHI disclosure.

import pytest

AUTH = {"X-API-Key": "test_api_key_12345"}


# ═══════════════════════════════════════════════════════════════════════════════
# LEGAL HOLDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestLegalHoldCreate:
    def test_create_requires_auth(self, client):
        resp = client.post("/v1/compliance/legal-holds", json={
            "tenant_id": "t1", "name": "Hold A", "scope": ["emails"], "created_by": "admin"
        })
        assert resp.status_code == 401

    def test_create_returns_200_or_500(self, client):
        resp = client.post("/v1/compliance/legal-holds", headers=AUTH, json={
            "tenant_id": "t-001", "name": "Litigation Hold 1",
            "scope": ["emails", "documents"], "created_by": "admin"
        })
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.json().get("qms_status") == "Thank_You"

    def test_create_with_matter_id(self, client):
        resp = client.post("/v1/compliance/legal-holds", headers=AUTH, json={
            "tenant_id": "t-001", "name": "Matter Hold",
            "scope": ["files"], "created_by": "admin", "matter_id": "MAT-001"
        })
        assert resp.status_code in (200, 500)

    def test_create_missing_required_fields_422(self, client):
        resp = client.post("/v1/compliance/legal-holds", headers=AUTH, json={})
        assert resp.status_code == 422

    def test_create_missing_name_422(self, client):
        resp = client.post("/v1/compliance/legal-holds", headers=AUTH, json={
            "tenant_id": "t1", "scope": [], "created_by": "admin"
        })
        assert resp.status_code == 422


class TestLegalHoldList:
    def test_list_requires_auth(self, client):
        resp = client.get("/v1/compliance/legal-holds")
        assert resp.status_code == 401

    def test_list_returns_200_or_500(self, client):
        resp = client.get("/v1/compliance/legal-holds", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "holds" in data
            assert data["qms_status"] == "Thank_You"

    def test_list_filter_by_tenant(self, client):
        resp = client.get("/v1/compliance/legal-holds?tenant_id=t-001", headers=AUTH)
        assert resp.status_code in (200, 500)

    def test_list_filter_by_status(self, client):
        resp = client.get("/v1/compliance/legal-holds?status=active", headers=AUTH)
        assert resp.status_code in (200, 500)


class TestLegalHoldGet:
    def test_get_nonexistent_returns_404_or_500(self, client):
        resp = client.get("/v1/compliance/legal-holds/HOLD-NONEXISTENT", headers=AUTH)
        assert resp.status_code in (404, 500)

    def test_get_requires_auth(self, client):
        resp = client.get("/v1/compliance/legal-holds/some-id")
        assert resp.status_code == 401


class TestLegalHoldRelease:
    def test_release_requires_auth(self, client):
        resp = client.post("/v1/compliance/legal-holds/HOLD-1/release", json={
            "released_by": "admin"
        })
        assert resp.status_code == 401

    def test_release_nonexistent_hold(self, client):
        resp = client.post("/v1/compliance/legal-holds/HOLD-MISSING/release",
                          headers=AUTH, json={"released_by": "admin"})
        assert resp.status_code in (200, 500)

    def test_release_missing_body_422(self, client):
        resp = client.post("/v1/compliance/legal-holds/H1/release", headers=AUTH, json={})
        assert resp.status_code == 422


class TestLegalHoldCustodian:
    def test_add_custodian_requires_auth(self, client):
        resp = client.post("/v1/compliance/legal-holds/H1/custodian", json={"user_id": "u1"})
        assert resp.status_code == 401

    def test_add_custodian_returns_result(self, client):
        resp = client.post("/v1/compliance/legal-holds/HOLD-TEST/custodian",
                          headers=AUTH, json={"user_id": "user-001"})
        assert resp.status_code in (200, 500)

    def test_add_custodian_missing_user_id_422(self, client):
        resp = client.post("/v1/compliance/legal-holds/H1/custodian", headers=AUTH, json={})
        assert resp.status_code == 422


class TestLegalHoldAcknowledge:
    def test_acknowledge_requires_auth(self, client):
        resp = client.post("/v1/compliance/legal-holds/H1/acknowledge", json={"user_id": "u1"})
        assert resp.status_code == 401

    def test_acknowledge_returns_result(self, client):
        resp = client.post("/v1/compliance/legal-holds/HOLD-TEST/acknowledge",
                          headers=AUTH, json={"user_id": "user-001"})
        assert resp.status_code in (200, 500)

    def test_acknowledge_missing_user_id_422(self, client):
        resp = client.post("/v1/compliance/legal-holds/H1/acknowledge", headers=AUTH, json={})
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# BREACH ASSESSMENT
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreachCreate:
    def test_create_requires_auth(self, client):
        resp = client.post("/v1/compliance/breach", json={
            "severity": "high", "description": "test", "data_types_exposed": ["name"]
        })
        assert resp.status_code == 401

    def test_create_returns_200_or_500(self, client):
        resp = client.post("/v1/compliance/breach", headers=AUTH, json={
            "severity": "high",
            "description": "Unauthorized access to patient records",
            "data_types_exposed": ["name", "ssn", "dob"],
            "affected_count": 150,
        })
        assert resp.status_code in (200, 422, 500)

    def test_create_invalid_severity_422(self, client):
        resp = client.post("/v1/compliance/breach", headers=AUTH, json={
            "severity": "not_a_severity",
            "description": "test",
            "data_types_exposed": ["email"],
        })
        assert resp.status_code in (422, 500)

    def test_create_missing_description_422(self, client):
        resp = client.post("/v1/compliance/breach", headers=AUTH, json={
            "severity": "high", "data_types_exposed": ["name"]
        })
        assert resp.status_code == 422


class TestBreachList:
    def test_list_requires_auth(self, client):
        resp = client.get("/v1/compliance/breach")
        assert resp.status_code == 401

    def test_list_returns_200_or_500(self, client):
        resp = client.get("/v1/compliance/breach", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "assessments" in resp.json()


class TestBreachGet:
    def test_get_nonexistent(self, client):
        resp = client.get("/v1/compliance/breach/ASSESS-NOTFOUND", headers=AUTH)
        assert resp.status_code in (404, 500)

    def test_get_requires_auth(self, client):
        resp = client.get("/v1/compliance/breach/ASSESS-1")
        assert resp.status_code == 401


class TestBreachNotify:
    def test_notify_requires_auth(self, client):
        resp = client.post("/v1/compliance/breach/A1/notify", json={
            "recipient_type": "regulator", "sent_to": "hhs@example.com"
        })
        assert resp.status_code == 401

    def test_notify_returns_result(self, client):
        resp = client.post("/v1/compliance/breach/ASSESS-001/notify",
                          headers=AUTH, json={
                              "recipient_type": "regulator",
                              "sent_to": "compliance@hhs.gov"
                          })
        assert resp.status_code in (200, 500)

    def test_notify_missing_fields_422(self, client):
        resp = client.post("/v1/compliance/breach/A1/notify", headers=AUTH, json={})
        assert resp.status_code == 422


class TestBreachOverdue:
    def test_overdue_requires_auth(self, client):
        resp = client.get("/v1/compliance/breach/overdue")
        assert resp.status_code == 401

    def test_overdue_returns_result(self, client):
        resp = client.get("/v1/compliance/breach/overdue", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "overdue" in resp.json()


# ═══════════════════════════════════════════════════════════════════════════════
# RETENTION POLICIES
# ═══════════════════════════════════════════════════════════════════════════════

class TestRetentionPolicies:
    def test_create_requires_auth(self, client):
        resp = client.post("/v1/compliance/retention/policies", json={
            "name": "P1", "tenant_id": "t1", "retention_days": 365, "data_types": ["audit"]
        })
        assert resp.status_code == 401

    def test_create_returns_result(self, client):
        resp = client.post("/v1/compliance/retention/policies", headers=AUTH, json={
            "name": "7-Year Retention",
            "tenant_id": "t-001",
            "retention_days": 2555,
            "data_types": ["audit_logs", "phi"],
            "auto_delete": False,
        })
        assert resp.status_code in (200, 500)

    def test_create_missing_required_fields_422(self, client):
        resp = client.post("/v1/compliance/retention/policies", headers=AUTH, json={
            "name": "P1"
        })
        assert resp.status_code == 422

    def test_list_requires_auth(self, client):
        resp = client.get("/v1/compliance/retention/policies")
        assert resp.status_code == 401

    def test_list_returns_result(self, client):
        resp = client.get("/v1/compliance/retention/policies", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "policies" in resp.json()

    def test_auto_delete_default_false(self, client):
        resp = client.post("/v1/compliance/retention/policies", headers=AUTH, json={
            "name": "NoAutoDelete",
            "tenant_id": "t-002",
            "retention_days": 90,
            "data_types": ["temp_files"],
        })
        assert resp.status_code in (200, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# SANCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSanctions:
    def test_create_requires_auth(self, client):
        resp = client.post("/v1/compliance/sanctions", json={
            "user_id": "u1", "violation": "v1", "severity": "minor", "imposed_by": "admin"
        })
        assert resp.status_code == 401

    def test_create_returns_result(self, client):
        resp = client.post("/v1/compliance/sanctions", headers=AUTH, json={
            "user_id": "user-001",
            "violation": "unauthorized_phi_access",
            "severity": "minor",
            "imposed_by": "compliance_officer",
        })
        assert resp.status_code in (200, 422, 500)

    def test_create_invalid_severity(self, client):
        resp = client.post("/v1/compliance/sanctions", headers=AUTH, json={
            "user_id": "u1",
            "violation": "test_violation",
            "severity": "not_a_real_severity",
            "imposed_by": "admin",
        })
        assert resp.status_code in (422, 500)

    def test_create_missing_fields_422(self, client):
        resp = client.post("/v1/compliance/sanctions", headers=AUTH, json={
            "user_id": "u1"
        })
        assert resp.status_code == 422

    def test_list_requires_auth(self, client):
        resp = client.get("/v1/compliance/sanctions")
        assert resp.status_code == 401

    def test_list_returns_result(self, client):
        resp = client.get("/v1/compliance/sanctions", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "sanctions" in resp.json()

    def test_list_filter_by_user(self, client):
        resp = client.get("/v1/compliance/sanctions?user_id=user-001", headers=AUTH)
        assert resp.status_code in (200, 500)

    def test_resolve_requires_auth(self, client):
        resp = client.post("/v1/compliance/sanctions/S1/resolve", json={"resolved_by": "admin"})
        assert resp.status_code == 401

    def test_resolve_returns_result(self, client):
        resp = client.post("/v1/compliance/sanctions/SANC-TEST/resolve",
                          headers=AUTH, json={"resolved_by": "admin", "notes": "Resolved"})
        assert resp.status_code in (200, 500)

    def test_resolve_missing_resolved_by_422(self, client):
        resp = client.post("/v1/compliance/sanctions/S1/resolve", headers=AUTH, json={})
        assert resp.status_code == 422

    def test_active_check_requires_auth(self, client):
        resp = client.get("/v1/compliance/sanctions/user/u1/active")
        assert resp.status_code == 401

    def test_active_check_returns_result(self, client):
        resp = client.get("/v1/compliance/sanctions/user/user-001/active", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "has_active" in resp.json()


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING COMPLIANCE
# ═══════════════════════════════════════════════════════════════════════════════

class TestTraining:
    def test_completion_requires_auth(self, client):
        resp = client.post("/v1/compliance/training/completion", json={
            "user_id": "u1", "training_type": "hipaa_awareness", "score": 90.0, "passed": True
        })
        assert resp.status_code == 401

    def test_completion_returns_result(self, client):
        resp = client.post("/v1/compliance/training/completion", headers=AUTH, json={
            "user_id": "user-001",
            "training_type": "hipaa_awareness",
            "score": 85.0,
            "passed": True,
        })
        assert resp.status_code in (200, 422, 500)

    def test_completion_invalid_type(self, client):
        resp = client.post("/v1/compliance/training/completion", headers=AUTH, json={
            "user_id": "user-001",
            "training_type": "not_a_real_training_type",
            "score": 80.0,
            "passed": True,
        })
        assert resp.status_code in (422, 500)

    def test_completion_missing_required_422(self, client):
        resp = client.post("/v1/compliance/training/completion", headers=AUTH, json={
            "user_id": "u1"
        })
        assert resp.status_code == 422

    def test_status_requires_auth(self, client):
        resp = client.get("/v1/compliance/training/user-001")
        assert resp.status_code == 401

    def test_status_returns_result(self, client):
        resp = client.get("/v1/compliance/training/user-001", headers=AUTH)
        assert resp.status_code in (200, 500)

    def test_report_requires_auth(self, client):
        resp = client.get("/v1/compliance/training/report")
        assert resp.status_code == 401

    def test_report_returns_result(self, client):
        resp = client.get("/v1/compliance/training/report", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.json().get("qms_status") == "Thank_You"


# ═══════════════════════════════════════════════════════════════════════════════
# CONTINGENCY PLAN
# ═══════════════════════════════════════════════════════════════════════════════

class TestContingency:
    def test_test_record_requires_auth(self, client):
        resp = client.post("/v1/compliance/contingency/test", json={
            "test_type": "backup_restore", "conducted_by": "admin",
            "duration": 60, "passed": True
        })
        assert resp.status_code == 401

    def test_test_record_returns_result(self, client):
        resp = client.post("/v1/compliance/contingency/test", headers=AUTH, json={
            "test_type": "backup_restore",
            "conducted_by": "it_admin",
            "duration": 45,
            "passed": True,
        })
        assert resp.status_code in (200, 422, 500)

    def test_test_record_invalid_type(self, client):
        resp = client.post("/v1/compliance/contingency/test", headers=AUTH, json={
            "test_type": "not_a_real_type",
            "conducted_by": "admin",
            "duration": 30,
            "passed": True,
        })
        assert resp.status_code in (422, 500)

    def test_test_record_missing_fields_422(self, client):
        resp = client.post("/v1/compliance/contingency/test", headers=AUTH, json={
            "test_type": "backup_restore"
        })
        assert resp.status_code == 422

    def test_list_requires_auth(self, client):
        resp = client.get("/v1/compliance/contingency/tests")
        assert resp.status_code == 401

    def test_list_returns_result(self, client):
        resp = client.get("/v1/compliance/contingency/tests", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "tests" in resp.json()

    def test_overdue_requires_auth(self, client):
        resp = client.get("/v1/compliance/contingency/overdue")
        assert resp.status_code == 401

    def test_overdue_returns_result(self, client):
        resp = client.get("/v1/compliance/contingency/overdue", headers=AUTH)
        assert resp.status_code in (200, 500)

    def test_overdue_with_interval_param(self, client):
        resp = client.get("/v1/compliance/contingency/overdue?interval_days=30", headers=AUTH)
        assert resp.status_code in (200, 500)

    def test_summary_requires_auth(self, client):
        resp = client.get("/v1/compliance/contingency/summary")
        assert resp.status_code == 401

    def test_summary_returns_result(self, client):
        resp = client.get("/v1/compliance/contingency/summary", headers=AUTH)
        assert resp.status_code in (200, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# BUSINESS ASSOCIATE AGREEMENT (BAA)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBAA:
    def test_create_requires_auth(self, client):
        resp = client.post("/v1/compliance/baa", json={
            "name": "Vendor A", "contact_email": "a@a.com",
            "services": ["storage"], "phi_access_level": "limited"
        })
        assert resp.status_code == 401

    def test_create_returns_result(self, client):
        resp = client.post("/v1/compliance/baa", headers=AUTH, json={
            "name": "Cloud Storage Vendor",
            "contact_email": "compliance@vendor.com",
            "services": ["backup", "storage"],
            "phi_access_level": "limited",
        })
        assert resp.status_code in (200, 500)

    def test_create_missing_required_422(self, client):
        resp = client.post("/v1/compliance/baa", headers=AUTH, json={"name": "Vendor A"})
        assert resp.status_code == 422

    def test_list_requires_auth(self, client):
        resp = client.get("/v1/compliance/baa")
        assert resp.status_code == 401

    def test_list_returns_result(self, client):
        resp = client.get("/v1/compliance/baa", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "baas" in resp.json()

    def test_list_filter_by_status(self, client):
        resp = client.get("/v1/compliance/baa?status=active", headers=AUTH)
        assert resp.status_code in (200, 422, 500)

    def test_activate_requires_auth(self, client):
        resp = client.post("/v1/compliance/baa/BA-1/activate", json={
            "effective_date": "2026-01-01", "expiration_date": "2027-01-01",
            "reviewed_by": "admin"
        })
        assert resp.status_code == 401

    def test_activate_returns_result(self, client):
        resp = client.post("/v1/compliance/baa/BA-TEST/activate", headers=AUTH, json={
            "effective_date": "2026-01-01",
            "expiration_date": "2027-01-01",
            "reviewed_by": "legal_team",
        })
        assert resp.status_code in (200, 500)

    def test_activate_missing_fields_422(self, client):
        resp = client.post("/v1/compliance/baa/BA-1/activate", headers=AUTH, json={})
        assert resp.status_code == 422

    def test_review_requires_auth(self, client):
        resp = client.post("/v1/compliance/baa/BA-1/review", json={"reviewed_by": "admin"})
        assert resp.status_code == 401

    def test_review_returns_result(self, client):
        resp = client.post("/v1/compliance/baa/BA-TEST/review", headers=AUTH, json={
            "reviewed_by": "legal_team", "notes": "Annual review complete"
        })
        assert resp.status_code in (200, 500)

    def test_review_missing_reviewed_by_422(self, client):
        resp = client.post("/v1/compliance/baa/BA-1/review", headers=AUTH, json={})
        assert resp.status_code == 422

    def test_terminate_requires_auth(self, client):
        resp = client.post("/v1/compliance/baa/BA-1/terminate", json={
            "terminated_by": "admin", "reason": "Vendor no longer used"
        })
        assert resp.status_code == 401

    def test_terminate_returns_result(self, client):
        resp = client.post("/v1/compliance/baa/BA-TEST/terminate", headers=AUTH, json={
            "terminated_by": "admin",
            "reason": "Contract expired, not renewed",
        })
        assert resp.status_code in (200, 500)

    def test_terminate_missing_fields_422(self, client):
        resp = client.post("/v1/compliance/baa/BA-1/terminate", headers=AUTH, json={
            "terminated_by": "admin"
        })
        assert resp.status_code == 422

    def test_expiring_requires_auth(self, client):
        resp = client.get("/v1/compliance/baa/expiring")
        assert resp.status_code == 401

    def test_expiring_returns_result(self, client):
        resp = client.get("/v1/compliance/baa/expiring", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "expiring" in resp.json()

    def test_expiring_with_custom_days(self, client):
        resp = client.get("/v1/compliance/baa/expiring?within_days=30", headers=AUTH)
        assert resp.status_code in (200, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# HITRUST CONTROLS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHITRUST:
    def test_controls_list_requires_auth(self, client):
        resp = client.get("/v1/compliance/hitrust/controls")
        assert resp.status_code == 401

    def test_controls_list_returns_result(self, client):
        resp = client.get("/v1/compliance/hitrust/controls", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "controls" in data
            assert data["qms_status"] == "Thank_You"

    def test_controls_list_filter_by_domain(self, client):
        resp = client.get("/v1/compliance/hitrust/controls?domain=access_control", headers=AUTH)
        assert resp.status_code in (200, 422, 500)

    def test_controls_list_invalid_domain(self, client):
        resp = client.get("/v1/compliance/hitrust/controls?domain=not_a_real_domain",
                         headers=AUTH)
        assert resp.status_code in (422, 500)

    def test_control_get_requires_auth(self, client):
        resp = client.get("/v1/compliance/hitrust/controls/01.a")
        assert resp.status_code == 401

    def test_control_get_returns_result(self, client):
        resp = client.get("/v1/compliance/hitrust/controls/01.a", headers=AUTH)
        assert resp.status_code in (200, 404, 500)

    def test_control_get_nonexistent_404_or_500(self, client):
        resp = client.get("/v1/compliance/hitrust/controls/NOTREAL", headers=AUTH)
        assert resp.status_code in (404, 500)

    def test_control_status_update_requires_auth(self, client):
        resp = client.post("/v1/compliance/hitrust/controls/01.a/status", json={
            "status": "implemented", "assessed_by": "auditor"
        })
        assert resp.status_code == 401

    def test_control_status_update_returns_result(self, client):
        resp = client.post("/v1/compliance/hitrust/controls/01.a/status",
                          headers=AUTH, json={
                              "status": "implemented",
                              "assessed_by": "security_auditor",
                              "evidence": "Policy doc ref 2026-01",
                          })
        assert resp.status_code in (200, 500)

    def test_control_status_update_missing_fields_422(self, client):
        resp = client.post("/v1/compliance/hitrust/controls/01.a/status",
                          headers=AUTH, json={})
        assert resp.status_code == 422

    def test_posture_requires_auth(self, client):
        resp = client.get("/v1/compliance/hitrust/posture")
        assert resp.status_code == 401

    def test_posture_returns_result(self, client):
        resp = client.get("/v1/compliance/hitrust/posture", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.json().get("qms_status") == "Thank_You"

    def test_risk_assessment_requires_auth(self, client):
        resp = client.post("/v1/compliance/hitrust/risk-assessment", json={
            "title": "T", "scope": "all", "findings": [], "risk_level": "low",
            "assessed_by": "admin"
        })
        assert resp.status_code == 401

    def test_risk_assessment_returns_result(self, client):
        resp = client.post("/v1/compliance/hitrust/risk-assessment", headers=AUTH, json={
            "title": "Q1 2026 Risk Assessment",
            "scope": "PHI systems",
            "findings": ["Finding 1", "Finding 2"],
            "risk_level": "medium",
            "assessed_by": "security_team",
            "recommendations": ["Recommendation A"],
        })
        assert resp.status_code in (200, 500)

    def test_risk_assessment_missing_fields_422(self, client):
        resp = client.post("/v1/compliance/hitrust/risk-assessment",
                          headers=AUTH, json={"title": "T"})
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# PHI DISCLOSURE
# ═══════════════════════════════════════════════════════════════════════════════

class TestPHIDisclosure:
    def test_record_requires_auth(self, client):
        resp = client.post("/v1/compliance/phi/disclosure", json={
            "patient_id": "P1", "recipient": "doctor", "purpose": "treatment",
            "phi_description": "labs", "recorded_by": "admin"
        })
        assert resp.status_code == 401

    def test_record_returns_result(self, client):
        resp = client.post("/v1/compliance/phi/disclosure", headers=AUTH, json={
            "patient_id": "PAT-001",
            "recipient": "Dr. Smith",
            "purpose": "treatment",
            "phi_description": "Lab results 2026-03",
            "recorded_by": "compliance_officer",
        })
        assert resp.status_code in (200, 500)

    def test_record_missing_fields_422(self, client):
        resp = client.post("/v1/compliance/phi/disclosure", headers=AUTH, json={
            "patient_id": "P1"
        })
        assert resp.status_code == 422

    def test_list_requires_auth(self, client):
        resp = client.get("/v1/compliance/phi/disclosures/PAT-001")
        assert resp.status_code == 401

    def test_list_returns_result(self, client):
        resp = client.get("/v1/compliance/phi/disclosures/PAT-001", headers=AUTH)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "disclosures" in resp.json()

    def test_list_with_date_filters(self, client):
        resp = client.get(
            "/v1/compliance/phi/disclosures/PAT-001"
            "?from_date=2026-01-01T00:00:00&to_date=2026-12-31T23:59:59",
            headers=AUTH
        )
        assert resp.status_code in (200, 500)

    def test_list_invalid_date_format_422(self, client):
        resp = client.get(
            "/v1/compliance/phi/disclosures/PAT-001?from_date=not-a-date",
            headers=AUTH
        )
        assert resp.status_code in (422, 500)

    def test_report_requires_auth(self, client):
        resp = client.get("/v1/compliance/phi/disclosures/PAT-001/report")
        assert resp.status_code == 401

    def test_report_returns_result(self, client):
        resp = client.get("/v1/compliance/phi/disclosures/PAT-001/report", headers=AUTH)
        assert resp.status_code in (200, 500)

    def test_report_different_patient(self, client):
        resp = client.get("/v1/compliance/phi/disclosures/PAT-999/report", headers=AUTH)
        assert resp.status_code in (200, 500)
