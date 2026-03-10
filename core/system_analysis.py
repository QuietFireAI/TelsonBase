# TelsonBase/core/system_analysis.py
# REM: =======================================================================================
# REM: SYSTEM-WIDE SECURITY ANALYSIS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.3.0CC: New feature - Comprehensive system security analysis
#
# REM: Mission Statement: Provide a single trigger for comprehensive security analysis
# REM: across all agents, federation relationships, anomaly patterns, and compliance status.
# REM: =======================================================================================

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


class AnalysisSeverity(str, Enum):
    """REM: Severity of analysis findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class AnalysisFinding:
    """REM: A single finding from system analysis."""
    category: str
    severity: AnalysisSeverity
    title: str
    description: str
    affected_resource: Optional[str] = None
    recommendation: Optional[str] = None
    auto_remediated: bool = False


@dataclass
class SystemAnalysisReport:
    """REM: Complete system analysis report."""
    report_id: str
    timestamp: datetime
    triggered_by: str
    duration_seconds: float
    findings: List[AnalysisFinding]
    summary: Dict[str, Any]
    agent_health: Dict[str, Any]
    federation_health: Dict[str, Any]
    security_posture: Dict[str, Any]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp.isoformat(),
            "triggered_by": self.triggered_by,
            "duration_seconds": self.duration_seconds,
            "finding_count": len(self.findings),
            "findings_by_severity": {
                sev.value: len([f for f in self.findings if f.severity == sev])
                for sev in AnalysisSeverity
            },
            "findings": [
                {
                    "category": f.category,
                    "severity": f.severity.value,
                    "title": f.title,
                    "description": f.description,
                    "affected_resource": f.affected_resource,
                    "recommendation": f.recommendation,
                    "auto_remediated": f.auto_remediated
                }
                for f in self.findings
            ],
            "summary": self.summary,
            "agent_health": self.agent_health,
            "federation_health": self.federation_health,
            "security_posture": self.security_posture,
            "recommendations": self.recommendations
        }


class SystemAnalyzer:
    """
    REM: Performs comprehensive system-wide security analysis.
    """

    def __init__(self):
        self._last_report: Optional[SystemAnalysisReport] = None
        self._report_history: List[SystemAnalysisReport] = []

    def run_full_analysis(
        self,
        triggered_by: str = "system",
        auto_remediate: bool = False
    ) -> SystemAnalysisReport:
        """
        REM: Run comprehensive system-wide security analysis.

        Args:
            triggered_by: Who/what triggered the analysis
            auto_remediate: Whether to automatically fix issues

        Returns:
            Complete analysis report
        """
        import time
        import uuid

        logger.info(f"REM: Starting system-wide analysis triggered by ::{triggered_by}::_Please")
        start_time = time.time()

        findings: List[AnalysisFinding] = []
        recommendations: List[str] = []

        # REM: Analyze agents
        agent_health = self._analyze_agents(findings, auto_remediate)

        # REM: Analyze trust levels and re-verification
        self._analyze_trust_levels(findings, auto_remediate)

        # REM: Analyze federation
        federation_health = self._analyze_federation(findings)

        # REM: Analyze anomalies
        self._analyze_anomalies(findings)

        # REM: Analyze rate limiting
        self._analyze_rate_limits(findings)

        # REM: Analyze delegations
        self._analyze_delegations(findings)

        # REM: Calculate security posture
        security_posture = self._calculate_security_posture(findings)

        # REM: Generate recommendations
        recommendations = self._generate_recommendations(findings, security_posture)

        duration = time.time() - start_time

        # REM: Build summary
        summary = {
            "total_findings": len(findings),
            "critical_findings": len([f for f in findings if f.severity == AnalysisSeverity.CRITICAL]),
            "high_findings": len([f for f in findings if f.severity == AnalysisSeverity.HIGH]),
            "auto_remediated": len([f for f in findings if f.auto_remediated]),
            "analysis_duration_seconds": round(duration, 2)
        }

        report = SystemAnalysisReport(
            report_id=f"analysis_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(timezone.utc),
            triggered_by=triggered_by,
            duration_seconds=round(duration, 2),
            findings=findings,
            summary=summary,
            agent_health=agent_health,
            federation_health=federation_health,
            security_posture=security_posture,
            recommendations=recommendations
        )

        self._last_report = report
        self._report_history.append(report)

        # REM: Keep only last 50 reports
        if len(self._report_history) > 50:
            self._report_history = self._report_history[-50:]

        logger.info(
            f"REM: System analysis complete - {len(findings)} findings, "
            f"{summary['critical_findings']} critical_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"System-wide security analysis completed",
            actor=triggered_by,
            details=summary,
            qms_status="Thank_You"
        )

        return report

    def _analyze_agents(
        self,
        findings: List[AnalysisFinding],
        auto_remediate: bool
    ) -> Dict[str, Any]:
        """REM: Analyze agent health and security."""
        try:
            from core.signing import key_registry
            from core.trust_levels import AgentTrustLevel, trust_manager

            records = trust_manager.get_all_records()
            health = {
                "total_agents": len(records),
                "by_trust_level": {},
                "unhealthy_agents": [],
                "revoked_agents": len(key_registry._revoked_agents) if hasattr(key_registry, '_revoked_agents') else 0
            }

            for level in AgentTrustLevel:
                health["by_trust_level"][level.value] = len(trust_manager.get_agents_by_level(level))

            for record in records:
                # REM: Check for concerning metrics
                if record.success_rate() < 0.7 and record.total_actions > 10:
                    findings.append(AnalysisFinding(
                        category="agent_health",
                        severity=AnalysisSeverity.HIGH,
                        title=f"Low success rate for agent {record.agent_id}",
                        description=f"Agent has {record.success_rate():.1%} success rate over {record.total_actions} actions",
                        affected_resource=record.agent_id,
                        recommendation="Review agent configuration and consider demotion"
                    ))
                    health["unhealthy_agents"].append(record.agent_id)

                if record.anomalies_triggered > 5:
                    findings.append(AnalysisFinding(
                        category="agent_behavior",
                        severity=AnalysisSeverity.CRITICAL if record.anomalies_triggered > 10 else AnalysisSeverity.HIGH,
                        title=f"High anomaly count for agent {record.agent_id}",
                        description=f"Agent has triggered {record.anomalies_triggered} anomalies",
                        affected_resource=record.agent_id,
                        recommendation="Investigate anomaly patterns and consider quarantine"
                    ))

                # REM: Check re-verification status
                if not record.reverification_passed:
                    findings.append(AnalysisFinding(
                        category="trust_verification",
                        severity=AnalysisSeverity.MEDIUM,
                        title=f"Agent {record.agent_id} failed re-verification",
                        description=f"Agent has failed {record.reverification_failures} re-verifications",
                        affected_resource=record.agent_id,
                        recommendation="Review agent behavior and promotion status"
                    ))

            return health

        except Exception as e:
            logger.error(f"REM: Agent analysis failed: {e}_Thank_You_But_No")
            findings.append(AnalysisFinding(
                category="system_error",
                severity=AnalysisSeverity.MEDIUM,
                title="Agent analysis incomplete",
                description=str(e)
            ))
            return {"error": str(e)}

    def _analyze_trust_levels(
        self,
        findings: List[AnalysisFinding],
        auto_remediate: bool
    ):
        """REM: Analyze trust levels and run re-verification."""
        try:
            from core.trust_levels import trust_manager

            # REM: Get re-verification status
            status = trust_manager.get_reverification_status()

            if status["due_for_reverification"] > 0:
                findings.append(AnalysisFinding(
                    category="trust_verification",
                    severity=AnalysisSeverity.MEDIUM,
                    title=f"{status['due_for_reverification']} agents due for re-verification",
                    description="Agents have not been re-verified within the required interval",
                    recommendation="Run system re-verification"
                ))

                if auto_remediate:
                    result = trust_manager.run_system_reverification()
                    findings[-1].auto_remediated = True
                    findings[-1].description += f" (Auto-remediated: {result['verified']} verified, {result['failed']} failed)"

            if status["recently_failed"] > 0:
                findings.append(AnalysisFinding(
                    category="trust_verification",
                    severity=AnalysisSeverity.HIGH,
                    title=f"{status['recently_failed']} agents recently failed re-verification",
                    description="These agents have been demoted due to failing behavioral checks",
                    recommendation="Review demoted agents and investigate root causes"
                ))

        except Exception as e:
            logger.error(f"REM: Trust level analysis failed: {e}_Thank_You_But_No")

    def _analyze_federation(self, findings: List[AnalysisFinding]) -> Dict[str, Any]:
        """REM: Analyze federation relationships."""
        try:
            from federation.trust import federation_manager

            relationships = federation_manager.get_all_relationships()
            health = {
                "total_relationships": len(relationships),
                "established": 0,
                "pending": 0,
                "revoked": 0
            }

            for rel in relationships:
                status = rel.get("status", "unknown")
                if status == "established":
                    health["established"] += 1
                elif "pending" in status:
                    health["pending"] += 1
                elif status == "revoked":
                    health["revoked"] += 1

            if health["pending"] > 0:
                findings.append(AnalysisFinding(
                    category="federation",
                    severity=AnalysisSeverity.LOW,
                    title=f"{health['pending']} pending federation requests",
                    description="Federation relationships awaiting completion",
                    recommendation="Review and complete pending federation handshakes"
                ))

            return health

        except Exception as e:
            logger.error(f"REM: Federation analysis failed: {e}_Thank_You_But_No")
            return {"error": str(e)}

    def _analyze_anomalies(self, findings: List[AnalysisFinding]):
        """REM: Analyze anomaly patterns."""
        try:
            from core.anomaly import behavior_monitor

            summary = behavior_monitor.get_dashboard_summary()

            if summary.get("total_unresolved", 0) > 10:
                findings.append(AnalysisFinding(
                    category="anomaly_backlog",
                    severity=AnalysisSeverity.HIGH,
                    title=f"{summary['total_unresolved']} unresolved anomalies",
                    description="Significant backlog of unresolved anomalies",
                    recommendation="Prioritize anomaly resolution, especially critical ones"
                ))

            critical = summary.get("by_severity", {}).get("critical", 0)
            if critical > 0:
                findings.append(AnalysisFinding(
                    category="critical_anomalies",
                    severity=AnalysisSeverity.CRITICAL,
                    title=f"{critical} critical anomalies detected",
                    description="Critical anomalies require immediate attention",
                    recommendation="Investigate and resolve critical anomalies immediately"
                ))

        except Exception as e:
            logger.error(f"REM: Anomaly analysis failed: {e}_Thank_You_But_No")

    def _analyze_rate_limits(self, findings: List[AnalysisFinding]):
        """REM: Analyze rate limiting status."""
        try:
            from core.rate_limiting import rate_limiter

            stats = rate_limiter.get_all_rate_stats()

            if stats.get("agents_in_cooldown", 0) > 0:
                findings.append(AnalysisFinding(
                    category="rate_limiting",
                    severity=AnalysisSeverity.MEDIUM,
                    title=f"{stats['agents_in_cooldown']} agents in rate limit cooldown",
                    description="Agents are being rate limited",
                    recommendation="Review rate limit configurations and agent behavior"
                ))

            if stats.get("total_limited", 0) > 100:
                findings.append(AnalysisFinding(
                    category="rate_limiting",
                    severity=AnalysisSeverity.LOW,
                    title=f"High rate limit hit count: {stats['total_limited']}",
                    description="Many requests have been rate limited",
                    recommendation="Consider adjusting rate limits or investigating abuse"
                ))

        except Exception as e:
            logger.error(f"REM: Rate limit analysis failed: {e}_Thank_You_But_No")

    def _analyze_delegations(self, findings: List[AnalysisFinding]):
        """REM: Analyze capability delegations."""
        try:
            from core.delegation import delegation_manager

            stats = delegation_manager.get_delegation_stats()

            if stats.get("active", 0) > 20:
                findings.append(AnalysisFinding(
                    category="delegations",
                    severity=AnalysisSeverity.LOW,
                    title=f"High number of active delegations: {stats['active']}",
                    description="Many capability delegations are active",
                    recommendation="Review delegations for necessity and security"
                ))

            # REM: Clean up expired delegations
            expired = delegation_manager.cleanup_expired()
            if expired > 0:
                findings.append(AnalysisFinding(
                    category="delegations",
                    severity=AnalysisSeverity.INFO,
                    title=f"Cleaned up {expired} expired delegations",
                    description="Expired delegations were automatically removed",
                    auto_remediated=True
                ))

        except Exception as e:
            logger.error(f"REM: Delegation analysis failed: {e}_Thank_You_But_No")

    def _calculate_security_posture(self, findings: List[AnalysisFinding]) -> Dict[str, Any]:
        """REM: Calculate overall security posture score."""
        # REM: Start with 100, deduct for findings
        score = 100

        for finding in findings:
            if finding.severity == AnalysisSeverity.CRITICAL:
                score -= 20
            elif finding.severity == AnalysisSeverity.HIGH:
                score -= 10
            elif finding.severity == AnalysisSeverity.MEDIUM:
                score -= 5
            elif finding.severity == AnalysisSeverity.LOW:
                score -= 2

        score = max(0, min(100, score))

        if score >= 90:
            rating = "EXCELLENT"
        elif score >= 75:
            rating = "GOOD"
        elif score >= 50:
            rating = "FAIR"
        elif score >= 25:
            rating = "POOR"
        else:
            rating = "CRITICAL"

        return {
            "score": score,
            "rating": rating,
            "critical_issues": len([f for f in findings if f.severity == AnalysisSeverity.CRITICAL]),
            "high_issues": len([f for f in findings if f.severity == AnalysisSeverity.HIGH])
        }

    def _generate_recommendations(
        self,
        findings: List[AnalysisFinding],
        security_posture: Dict[str, Any]
    ) -> List[str]:
        """REM: Generate prioritized recommendations."""
        recommendations = []

        # REM: Critical findings first
        critical = [f for f in findings if f.severity == AnalysisSeverity.CRITICAL]
        if critical:
            recommendations.append("IMMEDIATE: Address critical security findings")
            for f in critical:
                if f.recommendation:
                    recommendations.append(f"  - {f.recommendation}")

        # REM: High findings
        high = [f for f in findings if f.severity == AnalysisSeverity.HIGH]
        if high:
            recommendations.append("HIGH PRIORITY: Address high severity findings")

        # REM: Posture-based recommendations
        if security_posture["score"] < 50:
            recommendations.append("Consider a full security review")
        if security_posture["score"] < 75:
            recommendations.append("Schedule regular security assessments")

        return recommendations

    def get_last_report(self) -> Optional[Dict[str, Any]]:
        """REM: Get the last analysis report."""
        if self._last_report:
            return self._last_report.to_dict()
        return None

    def get_report_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """REM: Get recent analysis reports."""
        return [r.to_dict() for r in self._report_history[-limit:]]


# REM: Global system analyzer instance
system_analyzer = SystemAnalyzer()
