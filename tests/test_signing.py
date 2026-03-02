# TelsonBase/tests/test_signing.py
# REM: =======================================================================================
# REM: TESTS FOR CRYPTOGRAPHIC MESSAGE SIGNING
# REM: =======================================================================================

import pytest
from datetime import datetime, timezone, timedelta
import uuid

from core.signing import (
    SignedAgentMessage,
    AgentKeyRegistry,
    MessageSigner,
    REPLAY_WINDOW_SECONDS
)


class TestSignedAgentMessage:
    """REM: Tests for SignedAgentMessage class."""
    
    def test_create_message(self):
        """REM: Test basic message creation."""
        msg = SignedAgentMessage(
            message_id="test-001",
            agent_id="agent_a",
            action="test_action",
            payload={"key": "value"},
            signature="dummy_sig"
        )
        
        assert msg.message_id == "test-001"
        assert msg.agent_id == "agent_a"
        assert msg.action == "test_action"
        assert msg.payload == {"key": "value"}
    
    def test_signing_payload_deterministic(self):
        """REM: Test that signing payload is deterministic."""
        msg = SignedAgentMessage(
            message_id="test-001",
            agent_id="agent_a",
            timestamp=datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc),
            action="test",
            payload={"b": 2, "a": 1},  # Out of order
            signature="dummy"
        )
        
        payload1 = msg.get_signing_payload()
        payload2 = msg.get_signing_payload()
        
        # REM: Must be identical for signature verification
        assert payload1 == payload2
    
    def test_message_expiration(self):
        """REM: Test message expiration detection."""
        # REM: Fresh message should not be expired
        fresh_msg = SignedAgentMessage(
            message_id="test-001",
            agent_id="agent_a",
            action="test",
            payload={},
            signature="dummy"
        )
        assert not fresh_msg.is_expired()
        
        # REM: Old message should be expired
        old_msg = SignedAgentMessage(
            message_id="test-002",
            agent_id="agent_a",
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=REPLAY_WINDOW_SECONDS + 100),
            action="test",
            payload={},
            signature="dummy"
        )
        assert old_msg.is_expired()


class TestAgentKeyRegistry:
    """REM: Tests for AgentKeyRegistry class."""
    
    def test_register_agent(self):
        """REM: Test agent registration."""
        registry = AgentKeyRegistry()
        key = registry.register_agent("agent_a")
        
        assert key is not None
        assert len(key) == 32  # 256 bits
        assert registry.get_key("agent_a") == key
    
    def test_register_with_existing_key(self):
        """REM: Test registration with pre-existing key."""
        registry = AgentKeyRegistry()
        existing_key = b"0" * 32
        
        returned_key = registry.register_agent("agent_a", secret_key=existing_key)
        
        assert returned_key == existing_key
        assert registry.get_key("agent_a") == existing_key
    
    def test_revoke_agent(self):
        """REM: Test agent revocation."""
        registry = AgentKeyRegistry()
        registry.register_agent("agent_a")
        
        assert registry.revoke_agent("agent_a") is True
        assert registry.get_key("agent_a") is None
    
    def test_revoke_nonexistent_agent(self):
        """REM: Test revoking agent that doesn't exist."""
        registry = AgentKeyRegistry()
        assert registry.revoke_agent("nonexistent") is False
    
    def test_verify_valid_message(self):
        """REM: Test verification of valid signed message."""
        registry = AgentKeyRegistry()
        key = registry.register_agent("agent_a")
        signer = MessageSigner("agent_a", key)
        
        msg = signer.sign(
            action="test_action",
            payload={"data": "test"}
        )
        
        is_valid, reason = registry.verify_message(msg)
        assert is_valid is True
        assert reason == "Valid"
    
    def test_verify_invalid_signature(self):
        """REM: Test rejection of invalid signature."""
        registry = AgentKeyRegistry()
        registry.register_agent("agent_a")
        
        # REM: Create message with wrong signature
        msg = SignedAgentMessage(
            message_id=str(uuid.uuid4()),
            agent_id="agent_a",
            action="test",
            payload={},
            signature="definitely_wrong_signature"
        )
        
        is_valid, reason = registry.verify_message(msg)
        assert is_valid is False
        assert "Invalid signature" in reason
    
    def test_verify_unknown_agent(self):
        """REM: Test rejection of message from unknown agent."""
        registry = AgentKeyRegistry()
        
        msg = SignedAgentMessage(
            message_id=str(uuid.uuid4()),
            agent_id="unknown_agent",
            action="test",
            payload={},
            signature="any_sig"
        )
        
        is_valid, reason = registry.verify_message(msg)
        assert is_valid is False
        assert "Unknown agent" in reason
    
    def test_replay_attack_prevention(self):
        """REM: Test that duplicate message IDs are rejected."""
        registry = AgentKeyRegistry()
        key = registry.register_agent("agent_a")
        signer = MessageSigner("agent_a", key)
        
        msg = signer.sign(action="test", payload={})
        
        # REM: First verification should succeed
        is_valid1, _ = registry.verify_message(msg)
        assert is_valid1 is True
        
        # REM: Second verification of same message should fail (replay)
        is_valid2, reason = registry.verify_message(msg)
        assert is_valid2 is False
        assert "replay" in reason.lower()


class TestMessageSigner:
    """REM: Tests for MessageSigner class."""
    
    def test_sign_message(self):
        """REM: Test message signing."""
        signer = MessageSigner("agent_a", b"0" * 32)
        
        msg = signer.sign(
            action="test_action",
            payload={"key": "value"},
            target_agent="agent_b"
        )
        
        assert msg.agent_id == "agent_a"
        assert msg.action == "test_action"
        assert msg.payload == {"key": "value"}
        assert msg.target_agent == "agent_b"
        assert msg.signature != ""
        assert msg.message_id is not None
    
    def test_signature_changes_with_payload(self):
        """REM: Test that different payloads produce different signatures."""
        signer = MessageSigner("agent_a", b"0" * 32)
        
        msg1 = signer.sign(action="test", payload={"value": 1})
        msg2 = signer.sign(action="test", payload={"value": 2})
        
        assert msg1.signature != msg2.signature
