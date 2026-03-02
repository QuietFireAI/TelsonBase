# TelsonBase/tests/test_integration.py
# REM: =======================================================================================
# REM: INTEGRATION TESTS FOR SECURITY FEATURES
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.1.0CC: Added integration tests for:
# REM:   - Federation handshake (invitation → acceptance → message exchange)
# REM:   - Egress gateway blocking
# REM:   - Approval workflow
# REM:   - Cross-agent signed messaging
# REM:   - Key revocation
# REM: =======================================================================================

import threading
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


class TestFederationHandshake:
    """REM: Integration tests for federation trust establishment."""

    def test_full_federation_handshake(self):
        """
        REM: Test complete federation flow:
        1. Instance A creates invitation
        2. Instance B processes invitation
        3. Instance B accepts (generates session key, encrypts with A's public key)
        4. Instance A processes acceptance (decrypts session key)
        5. Both instances can now exchange encrypted messages
        """
        from federation.trust import FederationManager, TrustLevel, TrustStatus

        # REM: Create two instances
        instance_a = FederationManager("instance-a", "Law Firm A")
        instance_b = FederationManager("instance-b", "Law Firm B")

        # REM: Step 1: Instance A creates invitation
        invitation = instance_a.create_trust_invitation(
            trust_level=TrustLevel.STANDARD,
            expires_in_hours=24
        )
        assert "invitation_id" in invitation
        assert "signature" in invitation
        assert invitation["proposed_trust_level"] == "standard"

        # REM: Step 2: Instance B processes invitation
        success, message, relationship = instance_b.process_trust_invitation(invitation)
        assert success, f"Failed to process invitation: {message}"
        assert relationship is not None
        assert relationship.status == TrustStatus.PENDING_INBOUND

        # REM: Step 3: Instance B accepts (returns encrypted session key)
        success, message, relationship, acceptance = instance_b.accept_trust(
            relationship.relationship_id,
            decided_by="admin@lawfirm-b.com"
        )
        assert success, f"Failed to accept trust: {message}"
        assert relationship.status == TrustStatus.ESTABLISHED
        assert acceptance is not None
        assert "encrypted_session_key" in acceptance
        assert "signature" in acceptance

        # REM: Step 4: Instance A processes the acceptance
        # First, Instance A needs to have a relationship record
        # (In real use, A would have stored it when creating the invitation)
        # For this test, we create a pending outbound relationship on A's side
        from federation.trust import TrustRelationship, InstanceIdentity
        rel_a = TrustRelationship(
            relationship_id=relationship.relationship_id,
            remote_identity=instance_b.identity,
            trust_level=TrustLevel.STANDARD,
            status=TrustStatus.PENDING_OUTBOUND
        )
        instance_a._relationships[relationship.relationship_id] = rel_a

        success, message = instance_a.process_trust_acceptance(acceptance)
        assert success, f"Failed to process acceptance: {message}"

        # REM: Verify both sides now have session keys
        rel_a_updated = instance_a._relationships[relationship.relationship_id]
        rel_b_updated = instance_b._relationships[relationship.relationship_id]

        assert rel_a_updated.session_key is not None
        assert rel_b_updated.session_key is not None
        assert rel_a_updated.session_key == rel_b_updated.session_key
        assert rel_a_updated.status == TrustStatus.ESTABLISHED

    def test_federation_with_revocation(self):
        """REM: Test that revoked relationships cannot exchange messages."""
        from federation.trust import FederationManager, TrustLevel, TrustStatus

        instance_a = FederationManager("instance-a", "Org A")
        instance_b = FederationManager("instance-b", "Org B")

        # REM: Establish trust (simplified)
        invitation = instance_a.create_trust_invitation()
        success, _, relationship = instance_b.process_trust_invitation(invitation)
        success, _, relationship, _ = instance_b.accept_trust(relationship.relationship_id)

        # REM: Revoke trust
        result = instance_b.revoke_trust(
            relationship.relationship_id,
            reason="Security policy violation",
            revoked_by="security@org-b.com"
        )
        assert result is True

        # REM: Verify relationship is revoked
        rel = instance_b._relationships[relationship.relationship_id]
        assert rel.status == TrustStatus.REVOKED
        assert rel.session_key is None

        # REM: Attempt to send message should fail
        message = instance_b.send_message(
            relationship.relationship_id,
            source_agent_id="agent-1",
            action="query",
            payload={"test": "data"}
        )
        assert message is None  # Cannot send on revoked relationship


class TestEgressGatewayBlocking:
    """REM: Integration tests for egress gateway domain filtering."""

    def test_allowed_domain_passes(self):
        """REM: Test that whitelisted domains are allowed."""
        from gateway.egress_proxy import is_domain_allowed

        # REM: Test allowed domains (from default whitelist)
        allowed, domain = is_domain_allowed("https://api.anthropic.com/v1/messages")
        assert allowed is True
        assert domain == "api.anthropic.com"

        allowed, domain = is_domain_allowed("https://api.perplexity.ai/chat")
        assert allowed is True

    def test_blocked_domain_rejected(self):
        """REM: Test that non-whitelisted domains are blocked."""
        from gateway.egress_proxy import is_domain_allowed

        # REM: Test blocked domains
        allowed, domain = is_domain_allowed("https://evil-site.com/steal-data")
        assert allowed is False
        assert domain == "evil-site.com"

        allowed, domain = is_domain_allowed("https://random-api.io/endpoint")
        assert allowed is False

    def test_subdomain_matching(self):
        """REM: Test that subdomains of allowed domains are permitted."""
        from gateway.egress_proxy import is_domain_allowed

        # REM: api.anthropic.com is allowed, so subdomain should work
        allowed, domain = is_domain_allowed("https://v1.api.anthropic.com/messages")
        assert allowed is True


class TestApprovalWorkflow:
    """REM: Integration tests for approval gate workflow."""

    def test_approval_workflow_approve(self):
        """REM: Test full approval workflow with approval."""
        from core.approval import (
            approval_gate, ApprovalRule, ApprovalPriority, ApprovalStatus
        )
        import threading

        # REM: Create a test rule
        test_rule = ApprovalRule(
            rule_id="test-rule-integration",
            name="Test Rule",
            description="Integration test rule",
            action_pattern="delete*",
            priority=ApprovalPriority.HIGH,
            timeout_seconds=10
        )
        approval_gate.add_rule(test_rule)

        # REM: Create approval request
        request = approval_gate.create_request(
            agent_id="test-agent",
            action="delete_file",
            description="Delete test file",
            payload={"path": "/test/file.txt"},
            rule=test_rule
        )
        assert request.status == ApprovalStatus.PENDING

        # REM: Approve in background thread
        def approve_request():
            import time
            time.sleep(0.1)  # Small delay
            approval_gate.approve(
                request.request_id,
                decided_by="admin@test.com",
                notes="Approved for testing"
            )

        thread = threading.Thread(target=approve_request)
        thread.start()

        # REM: Wait for decision
        result = approval_gate.wait_for_decision(request.request_id, timeout=5)
        thread.join()

        assert result.status == ApprovalStatus.APPROVED
        assert result.decided_by == "admin@test.com"

    def test_approval_workflow_reject(self):
        """REM: Test approval workflow with rejection."""
        from core.approval import (
            approval_gate, ApprovalRule, ApprovalPriority, ApprovalStatus
        )
        import threading

        test_rule = ApprovalRule(
            rule_id="test-rule-reject",
            name="Test Reject Rule",
            description="Integration test reject rule",
            action_pattern="dangerous*",
            priority=ApprovalPriority.URGENT,
            timeout_seconds=10
        )
        approval_gate.add_rule(test_rule)

        request = approval_gate.create_request(
            agent_id="test-agent",
            action="dangerous_operation",
            description="Dangerous test operation",
            payload={},
            rule=test_rule
        )

        def reject_request():
            import time
            time.sleep(0.1)
            approval_gate.reject(
                request.request_id,
                decided_by="security@test.com",
                notes="Rejected - too risky"
            )

        thread = threading.Thread(target=reject_request)
        thread.start()

        result = approval_gate.wait_for_decision(request.request_id, timeout=5)
        thread.join()

        assert result.status == ApprovalStatus.REJECTED
        assert result.decided_by == "security@test.com"


class TestCrossAgentMessaging:
    """REM: Integration tests for signed inter-agent messaging."""

    def test_signed_message_flow(self):
        """REM: Test full signed message creation and verification."""
        from core.signing import key_registry, MessageSigner

        # REM: Register two agents
        agent_a_key = key_registry.register_agent("agent-alpha")
        agent_b_key = key_registry.register_agent("agent-beta")

        # REM: Agent A creates and signs a message for Agent B
        signer_a = MessageSigner("agent-alpha", agent_a_key)
        message = signer_a.sign(
            action="process_document",
            payload={"document_id": "doc-123", "operation": "summarize"},
            target_agent="agent-beta"
        )

        assert message.agent_id == "agent-alpha"
        assert message.target_agent == "agent-beta"
        assert message.action == "process_document"

        # REM: Verify the message
        is_valid, reason = key_registry.verify_message(message)
        assert is_valid, f"Message verification failed: {reason}"

    def test_tampered_message_rejected(self):
        """REM: Test that tampered messages are rejected."""
        from core.signing import key_registry, MessageSigner, SignedAgentMessage

        agent_key = key_registry.register_agent("agent-gamma")
        signer = MessageSigner("agent-gamma", agent_key)

        message = signer.sign(
            action="read_file",
            payload={"path": "/safe/file.txt"}
        )

        # REM: Tamper with the message
        tampered = SignedAgentMessage(
            message_id=message.message_id,
            agent_id=message.agent_id,
            timestamp=message.timestamp,
            action=message.action,
            payload={"path": "/etc/passwd"},  # Tampered payload!
            signature=message.signature  # Same signature won't match
        )

        is_valid, reason = key_registry.verify_message(tampered)
        assert not is_valid
        assert "Invalid signature" in reason

    def test_revoked_agent_rejected(self):
        """REM: Test that messages from revoked agents are rejected."""
        from core.signing import key_registry, MessageSigner

        # REM: Register and then revoke an agent
        agent_key = key_registry.register_agent("agent-rogue")
        signer = MessageSigner("agent-rogue", agent_key)

        # REM: Create a valid message
        message = signer.sign(
            action="exfiltrate_data",
            payload={"target": "secrets"}
        )

        # REM: Revoke the agent
        key_registry.revoke_agent(
            "agent-rogue",
            reason="Detected malicious behavior",
            revoked_by="security-system"
        )

        # REM: Message should now be rejected
        is_valid, reason = key_registry.verify_message(message)
        assert not is_valid
        assert "revoked" in reason.lower()

    def test_replay_attack_prevented(self):
        """REM: Test that replay attacks are detected and prevented."""
        from core.signing import key_registry, MessageSigner

        agent_key = key_registry.register_agent("agent-delta")
        signer = MessageSigner("agent-delta", agent_key)

        message = signer.sign(
            action="transfer_funds",
            payload={"amount": 1000}
        )

        # REM: First verification should succeed
        is_valid, _ = key_registry.verify_message(message)
        assert is_valid

        # REM: Replay attempt should fail
        is_valid, reason = key_registry.verify_message(message)
        assert not is_valid
        assert "replay" in reason.lower() or "duplicate" in reason.lower()


class TestAnomalyDetection:
    """REM: Integration tests for behavioral anomaly detection."""

    def test_capability_probe_detection(self):
        """REM: Test detection of capability probing (repeated permission denials)."""
        from core.anomaly import behavior_monitor, AnomalyType

        # REM: Simulate repeated permission denials
        for i in range(6):  # Threshold is 5
            anomalies = behavior_monitor.record(
                agent_id="suspicious-agent",
                action="access_restricted",
                resource=f"/secret/file{i}.txt",
                success=False  # Permission denied
            )

        # REM: Should detect capability probing
        unresolved = behavior_monitor.get_unresolved_anomalies(agent_id="suspicious-agent")
        probe_anomalies = [a for a in unresolved if a.anomaly_type == AnomalyType.CAPABILITY_PROBE]

        assert len(probe_anomalies) > 0
        assert probe_anomalies[0].requires_human_review is True


class TestKeyRevocation:
    """REM: Integration tests for key revocation mechanism."""

    def test_revoked_agent_cannot_reregister(self):
        """REM: Test that revoked agents cannot be re-registered."""
        from core.signing import key_registry

        # REM: Register agent
        key_registry.register_agent("agent-to-revoke")

        # REM: Revoke agent
        result = key_registry.revoke_agent(
            "agent-to-revoke",
            reason="Compromised",
            revoked_by="security"
        )
        assert result is True

        # REM: Attempt to re-register should fail
        with pytest.raises(PermissionError) as exc_info:
            key_registry.register_agent("agent-to-revoke")

        assert "revoked" in str(exc_info.value).lower()

    def test_revocation_can_be_cleared(self):
        """REM: Test that revocation can be explicitly cleared."""
        from core.signing import key_registry

        # REM: Register and revoke
        key_registry.register_agent("agent-clearable")
        key_registry.revoke_agent("agent-clearable", "Test revocation")

        # REM: Clear revocation
        result = key_registry.clear_revocation("agent-clearable", cleared_by="admin")
        assert result is True

        # REM: Should now be able to re-register
        key = key_registry.register_agent("agent-clearable")
        assert key is not None


class TestAuditChain:
    """REM: Integration tests for cryptographic audit log chaining (v4.3.0CC)."""

    def test_audit_chain_creates_entries(self):
        """REM: Test that audit entries are created with hash chain."""
        from core.audit import AuditLogger, AuditEventType

        # REM: Create fresh audit logger
        audit = AuditLogger()

        # REM: Log some events
        audit.log(AuditEventType.SYSTEM_STARTUP, "Test event 1", actor="test")
        audit.log(AuditEventType.SYSTEM_STARTUP, "Test event 2", actor="test")

        # REM: Get chain state
        state = audit.get_chain_state()
        assert state["last_sequence"] >= 2
        assert state["chain_id"] is not None
        assert len(state["last_hash"]) == 64  # SHA-256 hex

    def test_audit_chain_verification(self):
        """REM: Test that audit chain can be verified."""
        from core.audit import AuditLogger, AuditEventType

        audit = AuditLogger()

        # REM: Log several events
        for i in range(5):
            audit.log(AuditEventType.TASK_DISPATCHED, f"Task {i}", actor="test")

        # REM: Verify chain
        result = audit.verify_chain()
        assert result["valid"] is True
        assert result["entries_checked"] >= 5
        assert len(result["breaks"]) == 0

    def test_audit_chain_detects_tampering(self):
        """REM: Test that tampering is detected."""
        from core.audit import AuditLogger, AuditEventType, AuditChainEntry

        audit = AuditLogger()

        # REM: Log events
        audit.log(AuditEventType.TASK_COMPLETED, "Task completed", actor="test")

        # REM: Get entries and tamper with one
        entries = audit.get_recent_entries(10)
        if entries:
            # REM: Modify an entry
            tampered_entries = entries.copy()
            tampered_entries[0]["message"] = "TAMPERED MESSAGE"

            # REM: Verification should fail
            result = audit.verify_chain(tampered_entries)
            assert result["valid"] is False
            assert len(result["breaks"]) > 0

    def test_audit_chain_links_correctly(self):
        """REM: Test that each entry links to previous."""
        from core.audit import AuditLogger, AuditEventType

        audit = AuditLogger()
        initial_entries = len(audit._chain_entries)

        # REM: Log events
        audit.log(AuditEventType.AUTH_SUCCESS, "Login 1", actor="user1")
        audit.log(AuditEventType.AUTH_SUCCESS, "Login 2", actor="user2")

        entries = audit.get_recent_entries(10)

        # REM: Find our new entries (at least 2)
        if len(entries) >= 2:
            # REM: Verify chain link
            for i in range(1, len(entries)):
                assert entries[i]["previous_hash"] == entries[i-1]["entry_hash"]

    def test_audit_chain_concurrent_writes_remain_linear(self):
        """REM: 10 concurrent threads each write 1 audit entry — sequence numbers must be unique."""
        from core.audit import AuditLogger, AuditEventType

        audit = AuditLogger()
        # REM: Snapshot the sequence number before the concurrent writes begin
        initial_seq = audit._chain_state.last_sequence

        errors = []

        def write_entry():
            try:
                audit.log(AuditEventType.SYSTEM_STARTUP, "concurrent linearity test", actor="thread")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=write_entry) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Exceptions during concurrent audit writes: {errors}"

        # REM: Filter the last 50 chain entries to only those written by this test
        all_entries = audit.get_recent_entries(50)
        new_seqs = [e["sequence"] for e in all_entries if e["sequence"] > initial_seq]

        assert len(new_seqs) >= 10, f"Expected at least 10 new entries, got {len(new_seqs)}"
        assert len(new_seqs) == len(set(new_seqs)), (
            f"Duplicate sequence numbers — audit chain not linear under concurrency: {sorted(new_seqs)}"
        )

    def test_audit_export_for_compliance(self):
        """REM: Test compliance export includes verification."""
        from core.audit import AuditLogger, AuditEventType

        audit = AuditLogger()

        # REM: Log events
        audit.log(AuditEventType.TASK_DISPATCHED, "Test task", actor="test")

        # REM: Export
        export = audit.export_chain_for_compliance()

        assert "export_timestamp" in export
        assert "chain_id" in export
        assert "verification" in export
        assert "entries" in export
        assert export["verification"]["valid"] is True


class TestThreatResponse:
    """REM: Integration tests for automated threat response (v4.3.0CC)."""

    def test_threat_response_engine_initialization(self):
        """REM: Test threat response engine initializes correctly."""
        from core.threat_response import ThreatResponseEngine, ThreatLevel

        engine = ThreatResponseEngine()

        # REM: Check default indicators exist
        assert len(engine._indicators) > 0
        assert "ti_critical_anomaly_burst" in engine._indicators

        # REM: Check default policies exist
        assert ThreatLevel.CRITICAL in engine._policies
        assert ThreatLevel.HIGH in engine._policies

    def test_threat_stats(self):
        """REM: Test threat statistics collection."""
        from core.threat_response import ThreatResponseEngine

        engine = ThreatResponseEngine()
        stats = engine.get_threat_stats()

        assert "total_threats" in stats
        assert "last_24h" in stats
        assert "by_level" in stats

    def test_indicator_enable_disable(self):
        """REM: Test enabling/disabling threat indicators."""
        from core.threat_response import ThreatResponseEngine

        engine = ThreatResponseEngine()
        indicator_id = "ti_critical_anomaly_burst"

        # REM: Initially enabled
        assert engine._indicators[indicator_id].enabled is True

        # REM: Disable
        engine.disable_indicator(indicator_id)
        assert engine._indicators[indicator_id].enabled is False

        # REM: Re-enable
        engine.enable_indicator(indicator_id)
        assert engine._indicators[indicator_id].enabled is True


class TestSecureStorage:
    """REM: Integration tests for encryption at rest (v4.3.0CC)."""

    def test_secure_storage_encryption(self):
        """REM: Test data encryption/decryption."""
        from core.secure_storage import SecureStorageManager

        # REM: Initialize with test key
        storage = SecureStorageManager(
            encryption_key="test_key_for_unit_testing_only",
            salt="test_salt_12345"
        )

        # REM: Encrypt and decrypt
        plaintext = "sensitive data"
        encrypted = storage.encrypt(plaintext)
        decrypted = storage.decrypt(encrypted)

        assert decrypted.decode('utf-8') == plaintext
        assert encrypted != plaintext.encode()

    def test_secure_storage_string_methods(self):
        """REM: Test string encryption helpers."""
        from core.secure_storage import SecureStorageManager

        storage = SecureStorageManager(
            encryption_key="test_key_12345",
            salt="test_salt_12345"
        )

        plaintext = "my secret password"
        encrypted = storage.encrypt_string(plaintext)
        decrypted = storage.decrypt_string(encrypted)

        assert decrypted == plaintext
        assert encrypted != plaintext  # Should be base64

    def test_secure_storage_dict_encryption(self):
        """REM: Test dictionary field encryption."""
        from core.secure_storage import SecureStorageManager

        storage = SecureStorageManager(
            encryption_key="test_key_12345",
            salt="test_salt_12345"
        )

        data = {
            "agent_id": "test_agent",
            "signing_key": "secret_key_value",
            "public_info": "not_sensitive"
        }

        # REM: Encrypt sensitive keys
        encrypted = storage.encrypt_dict(data, ["signing_key"])

        # REM: Verify encryption marker
        assert encrypted.get("_signing_key_encrypted") is True
        assert encrypted["signing_key"] != "secret_key_value"
        assert encrypted["public_info"] == "not_sensitive"

        # REM: Decrypt
        decrypted = storage.decrypt_dict(encrypted, ["signing_key"])
        assert decrypted["signing_key"] == "secret_key_value"
