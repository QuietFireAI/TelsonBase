# TelsonBase/tests/test_capabilities.py
# REM: =======================================================================================
# REM: TESTS FOR CAPABILITY-BASED PERMISSION SYSTEM
# REM: =======================================================================================

import pytest

from core.capabilities import (
    Capability,
    CapabilitySet,
    CapabilityEnforcer,
    ResourceType,
    ActionType,
    CAPABILITY_PROFILES
)


class TestCapability:
    """REM: Tests for Capability class."""
    
    def test_parse_simple_capability(self):
        """REM: Test parsing a simple capability string."""
        cap = Capability.from_string("filesystem.read:/data/*")
        
        assert cap.resource == ResourceType.FILESYSTEM
        assert cap.action == ActionType.READ
        assert cap.scope == "/data/*"
    
    def test_parse_none_capability(self):
        """REM: Test parsing a 'none' capability."""
        cap = Capability.from_string("external.none")
        
        assert cap.resource == ResourceType.EXTERNAL
        assert cap.action == ActionType.NONE
    
    def test_capability_matches_exact(self):
        """REM: Test exact scope matching."""
        cap = Capability.from_string("filesystem.read:/data/file.txt")
        
        assert cap.matches(ResourceType.FILESYSTEM, ActionType.READ, "/data/file.txt")
        assert not cap.matches(ResourceType.FILESYSTEM, ActionType.READ, "/data/other.txt")
    
    def test_capability_matches_glob(self):
        """REM: Test glob pattern matching."""
        cap = Capability.from_string("filesystem.read:/data/*")
        
        assert cap.matches(ResourceType.FILESYSTEM, ActionType.READ, "/data/file.txt")
        assert cap.matches(ResourceType.FILESYSTEM, ActionType.READ, "/data/subdir/file.txt")
        assert not cap.matches(ResourceType.FILESYSTEM, ActionType.READ, "/other/file.txt")
    
    def test_capability_matches_wildcard(self):
        """REM: Test wildcard scope."""
        cap = Capability.from_string("ollama.execute:*")
        
        assert cap.matches(ResourceType.OLLAMA, ActionType.EXECUTE, "llama3")
        assert cap.matches(ResourceType.OLLAMA, ActionType.EXECUTE, "mistral")
    
    def test_capability_wrong_resource(self):
        """REM: Test that wrong resource type doesn't match."""
        cap = Capability.from_string("filesystem.read:/data/*")
        
        assert not cap.matches(ResourceType.EXTERNAL, ActionType.READ, "/data/file.txt")
    
    def test_capability_wrong_action(self):
        """REM: Test that wrong action type doesn't match."""
        cap = Capability.from_string("filesystem.read:/data/*")
        
        assert not cap.matches(ResourceType.FILESYSTEM, ActionType.WRITE, "/data/file.txt")
    
    def test_capability_to_string(self):
        """REM: Test string representation."""
        cap = Capability(
            resource=ResourceType.FILESYSTEM,
            action=ActionType.READ,
            scope="/data/*"
        )
        
        assert str(cap) == "filesystem.read:/data/*"


class TestCapabilitySet:
    """REM: Tests for CapabilitySet class."""
    
    def test_permits_allowed(self):
        """REM: Test that allowed capabilities are permitted."""
        cap_set = CapabilitySet.from_strings([
            "filesystem.read:/data/*",
            "filesystem.write:/app/backups/*"
        ])
        
        assert cap_set.permits(ResourceType.FILESYSTEM, ActionType.READ, "/data/file.txt")
        assert cap_set.permits(ResourceType.FILESYSTEM, ActionType.WRITE, "/app/backups/backup.tar")
    
    def test_permits_denied_not_in_list(self):
        """REM: Test that unlisted capabilities are denied."""
        cap_set = CapabilitySet.from_strings([
            "filesystem.read:/data/*"
        ])
        
        # REM: Write not allowed
        assert not cap_set.permits(ResourceType.FILESYSTEM, ActionType.WRITE, "/data/file.txt")
        # REM: Different path not allowed
        assert not cap_set.permits(ResourceType.FILESYSTEM, ActionType.READ, "/other/file.txt")
    
    def test_deny_takes_precedence(self):
        """REM: Test that deny rules override allow rules."""
        cap_set = CapabilitySet.from_strings([
            "filesystem.read:/data/*",           # Allow all of /data/
            "!filesystem.read:/data/secret/*"    # But deny /data/secret/
        ])
        
        assert cap_set.permits(ResourceType.FILESYSTEM, ActionType.READ, "/data/file.txt")
        assert not cap_set.permits(ResourceType.FILESYSTEM, ActionType.READ, "/data/secret/passwords.txt")
    
    def test_default_deny(self):
        """REM: Test that default is deny when no rules match."""
        cap_set = CapabilitySet()
        
        assert not cap_set.permits(ResourceType.FILESYSTEM, ActionType.READ, "/any/path")


class TestCapabilityEnforcer:
    """REM: Tests for CapabilityEnforcer class."""
    
    def test_register_and_check(self):
        """REM: Test registering agent and checking permissions."""
        enforcer = CapabilityEnforcer()
        enforcer.register_agent("test_agent", [
            "filesystem.read:/data/*",
            "external.none"
        ])
        
        # REM: Should be permitted
        assert enforcer.check_permission(
            "test_agent",
            ResourceType.FILESYSTEM,
            ActionType.READ,
            "/data/file.txt"
        )
        
        # REM: Should be denied (external.none)
        assert not enforcer.check_permission(
            "test_agent",
            ResourceType.EXTERNAL,
            ActionType.READ,
            "api.example.com"
        )
    
    def test_unknown_agent_denied(self):
        """REM: Test that unknown agents are denied."""
        enforcer = CapabilityEnforcer()
        
        assert not enforcer.check_permission(
            "unknown_agent",
            ResourceType.FILESYSTEM,
            ActionType.READ,
            "/data/file.txt"
        )
    
    def test_capability_profiles(self):
        """REM: Test that predefined profiles are valid."""
        for profile_name, capabilities in CAPABILITY_PROFILES.items():
            # REM: Should not raise exceptions
            cap_set = CapabilitySet.from_strings(capabilities)
            assert cap_set is not None
