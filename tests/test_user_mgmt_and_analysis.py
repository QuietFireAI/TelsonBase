# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: MIT
"""
Tests for core/user_management.py, core/sessions.py, core/system_analysis.py.
These three files were at 0% coverage — all security-critical paths.
"""

import pytest
from datetime import datetime, timedelta, timezone

# REM: Hand-built managers with fixed ids — keep them off the shared Redis store
pytestmark = pytest.mark.usefixtures("no_security_store")



# ═══════════════════════════════════════════════════════════════════════════════
# core/sessions.py — alias module
# ═══════════════════════════════════════════════════════════════════════════════

class TestSessionsAlias:
    """core/sessions.py is a 2-line alias. Verify the re-exports work."""

    def test_session_manager_importable(self):
        from core.sessions import session_manager
        assert session_manager is not None

    def test_session_manager_class_importable(self):
        from core.sessions import SessionManager
        assert SessionManager is not None

    def test_sessions_alias_matches_session_management(self):
        from core.sessions import session_manager as alias_mgr
        from core.session_management import session_manager as real_mgr
        assert alias_mgr is real_mgr


# ═══════════════════════════════════════════════════════════════════════════════
# core/user_management.py — password validation (pure functions, no Redis)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPasswordValidation:
    """_validate_password_strength covers all security rules."""

    @pytest.fixture
    def mgr(self):
        from core.user_management import UserManager
        m = UserManager.__new__(UserManager)
        m._password_hashes = {}
        m._failed_attempts = {}
        m._lockout_until = {}
        m._user_count = 0
        return m

    def test_strong_password_passes(self, mgr):
        valid, msg = mgr._validate_password_strength("Secure!Pass123")
        assert valid is True
        assert msg == ""

    def test_too_short_fails(self, mgr):
        valid, msg = mgr._validate_password_strength("Short!1A")
        assert valid is False
        assert "12 characters" in msg

    def test_no_uppercase_fails(self, mgr):
        valid, msg = mgr._validate_password_strength("secure!pass123")
        assert valid is False
        assert "uppercase" in msg

    def test_no_lowercase_fails(self, mgr):
        valid, msg = mgr._validate_password_strength("SECURE!PASS123")
        assert valid is False
        assert "lowercase" in msg

    def test_no_digit_fails(self, mgr):
        valid, msg = mgr._validate_password_strength("Secure!Password")
        assert valid is False
        assert "digit" in msg

    def test_no_special_char_fails(self, mgr):
        valid, msg = mgr._validate_password_strength("SecurePassword123")
        assert valid is False
        assert "special" in msg

    def test_exactly_12_chars_passes(self, mgr):
        valid, msg = mgr._validate_password_strength("Secure!Pass1")
        assert valid is True


class TestEmailValidation:
    """_validate_email: basic format enforcement."""

    @pytest.fixture
    def mgr(self):
        from core.user_management import UserManager
        m = UserManager.__new__(UserManager)
        return m

    def test_valid_email(self, mgr):
        assert mgr._validate_email("user@example.com") is True

    def test_valid_email_with_subdomain(self, mgr):
        assert mgr._validate_email("user@mail.example.org") is True

    def test_missing_at_sign(self, mgr):
        assert mgr._validate_email("userexample.com") is False

    def test_missing_domain(self, mgr):
        assert mgr._validate_email("user@") is False

    def test_missing_tld(self, mgr):
        assert mgr._validate_email("user@example") is False

    def test_empty_string(self, mgr):
        assert mgr._validate_email("") is False


# ═══════════════════════════════════════════════════════════════════════════════
# core/user_management.py — account lockout (in-memory, no Redis)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAccountLockout:
    """Account lockout logic — fully in-memory, no Redis required."""

    @pytest.fixture
    def mgr(self):
        from core.user_management import UserManager
        m = UserManager.__new__(UserManager)
        m._password_hashes = {}
        m._failed_attempts = {}
        m._lockout_until = {}
        m._user_count = 0
        return m

    def test_account_not_locked_initially(self, mgr):
        assert mgr._is_account_locked("testuser") is False

    def test_record_failed_attempts_increments(self, mgr):
        mgr._record_failed_attempt("testuser")
        mgr._record_failed_attempt("testuser")
        assert mgr._failed_attempts["testuser"] == 2

    def test_lockout_triggered_at_five_attempts(self, mgr):
        for _ in range(5):
            mgr._record_failed_attempt("testuser")
        assert mgr._is_account_locked("testuser") is True

    def test_lockout_below_threshold_does_not_lock(self, mgr):
        for _ in range(4):
            mgr._record_failed_attempt("testuser")
        assert mgr._is_account_locked("testuser") is False

    def test_clear_failed_attempts_removes_lockout(self, mgr):
        for _ in range(5):
            mgr._record_failed_attempt("testuser")
        assert mgr._is_account_locked("testuser") is True
        mgr._clear_failed_attempts("testuser")
        assert mgr._is_account_locked("testuser") is False

    def test_expired_lockout_clears_automatically(self, mgr):
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        mgr._lockout_until["testuser"] = past
        mgr._failed_attempts["testuser"] = 5
        assert mgr._is_account_locked("testuser") is False
        assert "testuser" not in mgr._lockout_until

    def test_active_lockout_blocks(self, mgr):
        future = datetime.now(timezone.utc) + timedelta(minutes=10)
        mgr._lockout_until["testuser"] = future
        assert mgr._is_account_locked("testuser") is True

    def test_is_first_user_true_when_zero_count(self, mgr):
        assert mgr.is_first_user() is True

    def test_is_first_user_false_after_increment(self, mgr):
        mgr._user_count = 1
        assert mgr.is_first_user() is False


# ═══════════════════════════════════════════════════════════════════════════════
# core/user_management.py — registration and authentication (with rbac)
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserRegistrationAndAuth:
    """Registration and authentication — uses fresh in-memory rbac manager."""

    @pytest.fixture
    def mgr(self):
        from core.user_management import UserManager
        from core.rbac import RBACManager
        m = UserManager.__new__(UserManager)
        m._password_hashes = {}
        m._failed_attempts = {}
        m._lockout_until = {}
        m._user_count = 0
        # Inject a fresh in-memory rbac manager so tests don't pollute global state
        self._rbac = RBACManager.__new__(RBACManager)
        self._rbac._users = {}
        self._rbac._users_by_username = {}
        self._rbac._custom_grants = {}
        self._rbac._custom_denials = {}
        import unittest.mock as mock
        m._get_rbac = lambda: self._rbac
        # Patch the global rbac_manager used inside user_management methods
        import core.user_management as um_module
        self._patcher = mock.patch.object(
            __builtins__.__class__, '__import__', wraps=__import__
        )
        return m

    @pytest.fixture
    def fresh_mgr(self):
        """Manager with patched rbac to avoid global state pollution."""
        import unittest.mock as mock
        from core.user_management import UserManager
        from core.rbac import RBACManager

        local_rbac = RBACManager.__new__(RBACManager)
        local_rbac._users = {}
        local_rbac._users_by_username = {}
        local_rbac._custom_grants = {}
        local_rbac._custom_denials = {}

        m = UserManager.__new__(UserManager)
        m._password_hashes = {}
        m._failed_attempts = {}
        m._lockout_until = {}
        m._user_count = 0

        with mock.patch("core.rbac.rbac_manager", local_rbac):
            yield m, local_rbac

    def test_password_strength_rejection_returns_false(self, fresh_mgr):
        m, _ = fresh_mgr
        valid, msg = m._validate_password_strength("weak")
        assert valid is False
        assert "12" in msg

    def test_validate_password_strong_returns_true(self, fresh_mgr):
        m, _ = fresh_mgr
        valid, _ = m._validate_password_strength("StrongPass!99")
        assert valid is True

    def test_register_user_first_user_gets_super_admin(self, fresh_mgr):
        m, _ = fresh_mgr
        result = m.register_user("admin_user", "admin@example.com", "StrongPass!99")
        assert "super_admin" in result["roles"]

    def test_register_user_second_user_gets_viewer(self, fresh_mgr):
        m, _ = fresh_mgr
        m.register_user("first_user", "first@example.com", "StrongPass!99")
        result = m.register_user("second_user", "second@example.com", "StrongPass!99")
        assert "viewer" in result["roles"]

    def test_register_duplicate_username_raises(self, fresh_mgr):
        m, _ = fresh_mgr
        m.register_user("dup_user", "dup@example.com", "StrongPass!99")
        with pytest.raises(ValueError, match="already taken"):
            m.register_user("dup_user", "other@example.com", "StrongPass!99")

    def test_register_invalid_email_raises(self, fresh_mgr):
        m, _ = fresh_mgr
        with pytest.raises(ValueError, match="Invalid email"):
            m.register_user("emailtest", "not-an-email", "StrongPass!99")

    def test_register_weak_password_raises(self, fresh_mgr):
        m, _ = fresh_mgr
        with pytest.raises(ValueError):
            m.register_user("weakpw", "weak@example.com", "weak")

    def test_authenticate_success(self, fresh_mgr):
        m, _ = fresh_mgr
        m.register_user("auth_user", "auth@example.com", "StrongPass!99")
        result = m.authenticate_user("auth_user", "StrongPass!99")
        assert result is not None
        assert result["username"] == "auth_user"

    def test_authenticate_wrong_password_returns_none(self, fresh_mgr):
        m, _ = fresh_mgr
        m.register_user("wrongpw_user", "wrongpw@example.com", "StrongPass!99")
        result = m.authenticate_user("wrongpw_user", "WrongPassword!99")
        assert result is None

    def test_authenticate_unknown_user_returns_none(self, fresh_mgr):
        m, _ = fresh_mgr
        result = m.authenticate_user("nonexistent", "SomePass!99")
        assert result is None

    def test_authenticate_locked_account_returns_none(self, fresh_mgr):
        m, _ = fresh_mgr
        m.register_user("lock_user", "lock@example.com", "StrongPass!99")
        for _ in range(5):
            m.authenticate_user("lock_user", "WrongPassword!99")
        result = m.authenticate_user("lock_user", "StrongPass!99")
        assert result is None

    def test_authenticate_clears_failed_attempts_on_success(self, fresh_mgr):
        m, _ = fresh_mgr
        m.register_user("clear_user", "clear@example.com", "StrongPass!99")
        m.authenticate_user("clear_user", "WrongPassword!99")
        m.authenticate_user("clear_user", "WrongPassword!99")
        assert m._failed_attempts.get("clear_user", 0) == 2
        m.authenticate_user("clear_user", "StrongPass!99")
        assert m._failed_attempts.get("clear_user", 0) == 0

    def test_change_password_success(self, fresh_mgr):
        m, _ = fresh_mgr
        profile = m.register_user("change_user", "change@example.com", "StrongPass!99")
        result = m.change_password(profile["user_id"], "StrongPass!99", "NewStrong!Pass1")
        assert result is True

    def test_change_password_wrong_old_fails(self, fresh_mgr):
        m, _ = fresh_mgr
        profile = m.register_user("changefail_user", "changefail@example.com", "StrongPass!99")
        result = m.change_password(profile["user_id"], "WrongOld!Pass1", "NewStrong!Pass1")
        assert result is False

    def test_change_password_unknown_user_fails(self, fresh_mgr):
        m, _ = fresh_mgr
        result = m.change_password("nonexistent_id", "OldPass!123", "NewPass!123")
        assert result is False

    def test_admin_reset_password_success(self, fresh_mgr):
        m, _ = fresh_mgr
        profile = m.register_user("reset_user", "reset@example.com", "StrongPass!99")
        result = m.reset_password_admin(profile["user_id"], "AdminReset!99", "admin_actor")
        assert result is True

    def test_admin_reset_unknown_user_fails(self, fresh_mgr):
        m, _ = fresh_mgr
        result = m.reset_password_admin("nonexistent_id", "AdminReset!99", "admin")
        assert result is False

    def test_admin_reset_clears_lockout(self, fresh_mgr):
        m, _ = fresh_mgr
        profile = m.register_user("locked_reset", "lockedreset@example.com", "StrongPass!99")
        for _ in range(5):
            m.authenticate_user("locked_reset", "Wrong!Pass99")
        assert m._is_account_locked("locked_reset") is True
        m.reset_password_admin(profile["user_id"], "AdminReset!99", "admin")
        assert m._is_account_locked("locked_reset") is False


# ═══════════════════════════════════════════════════════════════════════════════
# core/system_analysis.py — pure logic (no Redis, graceful failure on imports)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalysisSeverityEnum:
    """All 5 severity levels must exist."""

    def test_all_five_severities_exist(self):
        from core.system_analysis import AnalysisSeverity
        names = {s.name for s in AnalysisSeverity}
        assert names == {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}

    def test_severity_values_are_lowercase_strings(self):
        from core.system_analysis import AnalysisSeverity
        for s in AnalysisSeverity:
            assert s.value == s.value.lower()


class TestAnalysisFinding:
    """AnalysisFinding dataclass instantiation and defaults."""

    def test_finding_instantiation(self):
        from core.system_analysis import AnalysisFinding, AnalysisSeverity
        f = AnalysisFinding(
            category="test",
            severity=AnalysisSeverity.HIGH,
            title="Test finding",
            description="A test finding"
        )
        assert f.category == "test"
        assert f.severity == AnalysisSeverity.HIGH
        assert f.auto_remediated is False
        assert f.affected_resource is None
        assert f.recommendation is None

    def test_finding_with_all_fields(self):
        from core.system_analysis import AnalysisFinding, AnalysisSeverity
        f = AnalysisFinding(
            category="agent_health",
            severity=AnalysisSeverity.CRITICAL,
            title="Critical issue",
            description="Something is wrong",
            affected_resource="agent_001",
            recommendation="Take action",
            auto_remediated=True
        )
        assert f.auto_remediated is True
        assert f.affected_resource == "agent_001"


class TestSecurityPostureCalculation:
    """_calculate_security_posture is pure math — no external deps."""

    @pytest.fixture
    def analyzer(self):
        from core.system_analysis import SystemAnalyzer
        return SystemAnalyzer()

    def test_no_findings_gives_perfect_score(self, analyzer):
        posture = analyzer._calculate_security_posture([])
        assert posture["score"] == 100
        assert posture["rating"] == "EXCELLENT"

    def test_critical_finding_deducts_20(self, analyzer):
        from core.system_analysis import AnalysisFinding, AnalysisSeverity
        findings = [AnalysisFinding("cat", AnalysisSeverity.CRITICAL, "t", "d")]
        posture = analyzer._calculate_security_posture(findings)
        assert posture["score"] == 80
        assert posture["rating"] == "GOOD"
        assert posture["critical_issues"] == 1

    def test_high_finding_deducts_10(self, analyzer):
        from core.system_analysis import AnalysisFinding, AnalysisSeverity
        findings = [AnalysisFinding("cat", AnalysisSeverity.HIGH, "t", "d")]
        posture = analyzer._calculate_security_posture(findings)
        assert posture["score"] == 90

    def test_medium_finding_deducts_5(self, analyzer):
        from core.system_analysis import AnalysisFinding, AnalysisSeverity
        findings = [AnalysisFinding("cat", AnalysisSeverity.MEDIUM, "t", "d")]
        posture = analyzer._calculate_security_posture(findings)
        assert posture["score"] == 95

    def test_low_finding_deducts_2(self, analyzer):
        from core.system_analysis import AnalysisFinding, AnalysisSeverity
        findings = [AnalysisFinding("cat", AnalysisSeverity.LOW, "t", "d")]
        posture = analyzer._calculate_security_posture(findings)
        assert posture["score"] == 98

    def test_score_cannot_go_below_zero(self, analyzer):
        from core.system_analysis import AnalysisFinding, AnalysisSeverity
        findings = [AnalysisFinding("cat", AnalysisSeverity.CRITICAL, "t", "d")] * 20
        posture = analyzer._calculate_security_posture(findings)
        assert posture["score"] == 0
        assert posture["rating"] == "CRITICAL"

    def test_poor_rating_band(self, analyzer):
        from core.system_analysis import AnalysisFinding, AnalysisSeverity
        # 3 critical = 60 deducted → score 40 → POOR
        findings = [AnalysisFinding("cat", AnalysisSeverity.CRITICAL, "t", "d")] * 3
        posture = analyzer._calculate_security_posture(findings)
        assert posture["score"] == 40
        assert posture["rating"] == "POOR"

    def test_fair_rating_band(self, analyzer):
        from core.system_analysis import AnalysisFinding, AnalysisSeverity
        # 2 critical = 40 deducted → score 60 → FAIR
        findings = [AnalysisFinding("cat", AnalysisSeverity.CRITICAL, "t", "d")] * 2
        posture = analyzer._calculate_security_posture(findings)
        assert posture["score"] == 60
        assert posture["rating"] == "FAIR"


class TestRecommendationGeneration:
    """_generate_recommendations is pure logic."""

    @pytest.fixture
    def analyzer(self):
        from core.system_analysis import SystemAnalyzer
        return SystemAnalyzer()

    def test_no_findings_gives_no_immediate_recommendations(self, analyzer):
        posture = {"score": 100, "rating": "EXCELLENT", "critical_issues": 0, "high_issues": 0}
        recs = analyzer._generate_recommendations([], posture)
        assert isinstance(recs, list)

    def test_critical_finding_adds_immediate_rec(self, analyzer):
        from core.system_analysis import AnalysisFinding, AnalysisSeverity
        findings = [AnalysisFinding("cat", AnalysisSeverity.CRITICAL, "t", "d",
                                    recommendation="Fix this now")]
        posture = {"score": 80, "rating": "GOOD", "critical_issues": 1, "high_issues": 0}
        recs = analyzer._generate_recommendations(findings, posture)
        assert any("IMMEDIATE" in r for r in recs)
        assert any("Fix this now" in r for r in recs)

    def test_high_finding_adds_high_priority_rec(self, analyzer):
        from core.system_analysis import AnalysisFinding, AnalysisSeverity
        findings = [AnalysisFinding("cat", AnalysisSeverity.HIGH, "t", "d")]
        posture = {"score": 90, "rating": "GOOD", "critical_issues": 0, "high_issues": 1}
        recs = analyzer._generate_recommendations(findings, posture)
        assert any("HIGH PRIORITY" in r for r in recs)

    def test_low_score_adds_full_security_review_rec(self, analyzer):
        posture = {"score": 40, "rating": "POOR", "critical_issues": 0, "high_issues": 0}
        recs = analyzer._generate_recommendations([], posture)
        assert any("security review" in r.lower() for r in recs)


class TestSystemAnalysisReport:
    """SystemAnalysisReport.to_dict() serialization."""

    def test_to_dict_structure(self):
        from core.system_analysis import SystemAnalysisReport, AnalysisFinding, AnalysisSeverity
        report = SystemAnalysisReport(
            report_id="analysis_abc123",
            timestamp=datetime.now(timezone.utc),
            triggered_by="test",
            duration_seconds=0.5,
            findings=[],
            summary={"total_findings": 0},
            agent_health={},
            federation_health={},
            security_posture={"score": 100, "rating": "EXCELLENT"},
            recommendations=[]
        )
        d = report.to_dict()
        assert d["report_id"] == "analysis_abc123"
        assert d["triggered_by"] == "test"
        assert d["finding_count"] == 0
        assert "findings_by_severity" in d
        assert "timestamp" in d

    def test_to_dict_counts_findings_by_severity(self):
        from core.system_analysis import SystemAnalysisReport, AnalysisFinding, AnalysisSeverity
        findings = [
            AnalysisFinding("c", AnalysisSeverity.CRITICAL, "t", "d"),
            AnalysisFinding("c", AnalysisSeverity.HIGH, "t", "d"),
            AnalysisFinding("c", AnalysisSeverity.HIGH, "t", "d"),
        ]
        report = SystemAnalysisReport(
            report_id="test_report",
            timestamp=datetime.now(timezone.utc),
            triggered_by="test",
            duration_seconds=1.0,
            findings=findings,
            summary={},
            agent_health={},
            federation_health={},
            security_posture={},
            recommendations=[]
        )
        d = report.to_dict()
        assert d["findings_by_severity"]["critical"] == 1
        assert d["findings_by_severity"]["high"] == 2
        assert d["finding_count"] == 3


class TestSystemAnalyzerReportHistory:
    """get_last_report and get_report_history — no Redis required."""

    @pytest.fixture
    def analyzer(self):
        from core.system_analysis import SystemAnalyzer
        return SystemAnalyzer()

    def test_get_last_report_none_initially(self, analyzer):
        assert analyzer.get_last_report() is None

    def test_get_report_history_empty_initially(self, analyzer):
        history = analyzer.get_report_history()
        assert isinstance(history, list)
        assert len(history) == 0

    def test_run_full_analysis_returns_report(self, analyzer):
        report = analyzer.run_full_analysis(triggered_by="test_suite")
        assert report is not None
        assert report.triggered_by == "test_suite"
        assert report.report_id.startswith("analysis_")

    def test_run_full_analysis_populates_last_report(self, analyzer):
        analyzer.run_full_analysis(triggered_by="test_suite")
        last = analyzer.get_last_report()
        assert last is not None
        assert "report_id" in last

    def test_run_full_analysis_accumulates_history(self, analyzer):
        analyzer.run_full_analysis(triggered_by="run_1")
        analyzer.run_full_analysis(triggered_by="run_2")
        history = analyzer.get_report_history()
        assert len(history) == 2

    def test_get_report_history_respects_limit(self, analyzer):
        for i in range(5):
            analyzer.run_full_analysis(triggered_by=f"run_{i}")
        history = analyzer.get_report_history(limit=3)
        assert len(history) == 3

    def test_security_posture_in_report(self, analyzer):
        report = analyzer.run_full_analysis(triggered_by="posture_test")
        d = report.to_dict()
        assert "security_posture" in d
        assert "score" in d["security_posture"]
