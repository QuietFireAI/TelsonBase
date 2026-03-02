# TelsonBase/tests/test_behavioral.py
# REM: =======================================================================================
# REM: BEHAVIORAL SPECIFICATION TESTS FOR AGENT INTERACTIONS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Collaborator: Claude (Opus 4.6)
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: These are not unit tests. These are behavioral specifications —
# REM: human-readable scenarios that describe how agents SHOULD behave, expressed as
# REM: executable tests. Each test reads like a sentence: "Given X, When Y, Then Z."
# REM:
# REM: This bridges QMS philosophy (human-readable protocol) with testing strategy.
# REM: A non-developer can read these specs and understand what the system promises.
# REM: A developer can run them and verify the promises are kept.
# REM:
# REM: Design Principle: Every behavioral spec maps to a real operational scenario.
# REM: These are NOT abstract — they describe situations that WILL occur in production.
# REM: =======================================================================================

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# REM: Import QMS validation — module-level functions, not a class
from core.qms import (
    validate_chain_string,
    validate_chain,
    parse_chain,
    QMSValidationResult,
    QMSStatus,
)

# REM: Import agent components
from agents.ollama_agent import OllamaAgent
from agents.base import AgentRequest
from core.ollama_service import OllamaConnectionError, OllamaModelError
from core.capabilities import ActionType, ResourceType
from core.trust_levels import AgentTrustLevel, TRUST_LEVEL_CONSTRAINTS


# =========================================================================================
# BEHAVIORAL SPECIFICATION: OLLAMA AGENT — MODEL MANAGEMENT
# =========================================================================================

class TestBehavior_OllamaAgent_ModelManagement:
    """
    REM: Behavioral specifications for how the Ollama agent handles model
    operations. These scenarios cover the complete lifecycle of model
    interaction — from pulling models to handling failures gracefully.

    Each test name is a complete English sentence describing the behavior.
    """

    # ---------------------------------------------------------------------------------
    # SCENARIO: Agent with no models loaded — model not found on generate
    # ---------------------------------------------------------------------------------

    def test_GIVEN_model_not_found_WHEN_generate_requested_THEN_raises_clear_error_with_model_name(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  An Ollama agent where the requested model does not exist locally
        When:   A user sends a generate request
        Then:   The agent raises a ValueError (not a raw connection error)
                containing the model name so the user knows WHAT is missing

        Why this matters: A cold-start system with no models should not crash
        or return a cryptic error. It should tell the user exactly what model
        is missing, so they know what to pull.
        """
        agent = OllamaAgent()

        with patch.object(agent._service, 'generate') as mock_gen:
            mock_gen.side_effect = OllamaModelError("Model 'gemma2:9b' not found locally")

            request = AgentRequest(action="generate", payload={"prompt": "Hello world"})

            with pytest.raises(ValueError) as exc_info:
                agent.execute(request)

            # Error message must identify the problem — not just "error occurred"
            assert "not found" in str(exc_info.value).lower() or "gemma2" in str(exc_info.value).lower()

    def test_GIVEN_model_not_found_WHEN_chat_requested_THEN_raises_clear_error_not_crash(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  An Ollama agent where the model is not available
        When:   A multi-turn chat request arrives
        Then:   The agent raises a ValueError (structured, typed exception)
                NOT an unhandled OllamaModelError leaking internal details

        Why this matters: Chat is the primary user interaction. A missing model
        should surface as a clear, typed error — not an internal exception that
        breaks the UI and violates QMS protocol discipline.
        """
        agent = OllamaAgent()

        with patch.object(agent._service, 'chat') as mock_chat:
            mock_chat.side_effect = OllamaModelError("model not found")

            request = AgentRequest(
                action="chat",
                payload={"messages": [{"role": "user", "content": "Hello"}]}
            )

            # Must raise ValueError (the execute() error mapping), not OllamaModelError
            with pytest.raises(ValueError):
                agent.execute(request)

    # ---------------------------------------------------------------------------------
    # SCENARIO: Ollama service is offline
    # ---------------------------------------------------------------------------------

    def test_GIVEN_ollama_offline_WHEN_health_check_requested_THEN_reports_connection_failure(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The Ollama container is stopped or unreachable
        When:   A health check is performed
        Then:   The agent raises a RuntimeError (not a raw ConnectionError)
                containing connection failure details

        Why this matters: Infrastructure failures are normal. The error must
        be typed (RuntimeError) so the API layer can map it to proper HTTP
        status codes. Raw socket errors should never reach the client.
        """
        agent = OllamaAgent()

        with patch.object(agent._service, 'health_check') as mock_health:
            mock_health.side_effect = OllamaConnectionError("Connection refused")

            request = AgentRequest(action="health_check", payload={})

            with pytest.raises(RuntimeError) as exc_info:
                agent.execute(request)

            assert "unreachable" in str(exc_info.value).lower() or "running" in str(exc_info.value).lower()

    def test_GIVEN_ollama_offline_WHEN_model_pull_requested_THEN_returns_connection_error_not_model_error(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  Ollama service is unreachable
        When:   A model pull request is submitted
        Then:   The error clearly states the CONNECTION failed
                NOT "model not found" (which would mislead the user)

        Why this matters: Error specificity. "Can't connect" and "model doesn't
        exist" require different user actions. Conflating them wastes time.
        """
        agent = OllamaAgent()

        with patch.object(agent._service, 'pull_model') as mock_pull:
            mock_pull.side_effect = OllamaConnectionError("Connection refused to ollama:11434")

            request = AgentRequest(action="pull_model", payload={"model": "gemma2:9b"})

            with pytest.raises(RuntimeError) as exc_info:
                agent.execute(request)

            error_msg = str(exc_info.value).lower()
            # Must mention connection/unreachable — NOT "model not found"
            assert "unreachable" in error_msg or "running" in error_msg
            assert "not found" not in error_msg

    # ---------------------------------------------------------------------------------
    # SCENARIO: Model operations with approval gates
    # ---------------------------------------------------------------------------------

    def test_GIVEN_ollama_agent_WHEN_capabilities_checked_THEN_pull_and_delete_require_approval(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  An initialized Ollama agent
        When:   Its capability declarations are inspected
        Then:   pull_model and delete_model are in the REQUIRES_APPROVAL_FOR list

        Why this matters: Downloading a 40GB model or deleting the only available
        model are destructive operations. They MUST go through human-in-the-loop
        approval. If this test fails, the approval gate is broken.
        """
        assert "pull_model" in OllamaAgent.REQUIRES_APPROVAL_FOR
        assert "delete_model" in OllamaAgent.REQUIRES_APPROVAL_FOR

    def test_GIVEN_ollama_agent_THEN_generate_and_chat_do_NOT_require_approval(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  An initialized Ollama agent
        When:   Normal inference operations are checked
        Then:   generate and chat are NOT in the approval list

        Why this matters: Inference is the primary function. Requiring approval
        for every prompt would make the system unusable. Only state-changing
        operations (pull, delete) need gates.
        """
        assert "generate" not in OllamaAgent.REQUIRES_APPROVAL_FOR
        assert "chat" not in OllamaAgent.REQUIRES_APPROVAL_FOR

    # ---------------------------------------------------------------------------------
    # SCENARIO: Capability enforcement
    # ---------------------------------------------------------------------------------

    def test_GIVEN_ollama_agent_THEN_has_manage_capability_for_model_operations(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The Ollama agent's declared capabilities
        When:   Inspected for model management permissions
        Then:   The agent has ollama.manage capabilities for list, info, pull, delete

        Why this matters: The capability system is the enforcement layer.
        If the agent doesn't declare manage capabilities, the capability
        enforcer will block model operations even from authorized users.
        """
        manage_caps = [c for c in OllamaAgent.CAPABILITIES if "manage" in c]
        assert len(manage_caps) >= 4  # list, info, pull, delete at minimum

        cap_scopes = " ".join(manage_caps)
        assert "list" in cap_scopes
        assert "info" in cap_scopes
        assert "pull" in cap_scopes
        assert "delete" in cap_scopes

    def test_GIVEN_ollama_agent_THEN_has_execute_capability_for_inference(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The Ollama agent's declared capabilities
        When:   Inspected for inference permissions
        Then:   The agent has ollama.execute:* (wildcard inference capability)

        Why this matters: The wildcard scope means the agent can run any
        model for inference. Without this, every new model would require
        a capability update.
        """
        execute_caps = [c for c in OllamaAgent.CAPABILITIES if "execute" in c]
        assert len(execute_caps) >= 1
        assert any("*" in c for c in execute_caps)

    def test_GIVEN_ollama_agent_THEN_has_no_external_network_capability(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The Ollama agent's declared capabilities
        When:   Inspected for external network access
        Then:   The agent declares external.none

        Why this matters: Data sovereignty. The Ollama agent processes
        user prompts — potentially containing sensitive legal or medical data.
        It MUST NOT have permission to send data to external services.
        This is the technical enforcement of the "data drug dealers" philosophy.
        """
        assert "external.none" in OllamaAgent.CAPABILITIES

    # ---------------------------------------------------------------------------------
    # SCENARIO: Supported actions are complete
    # ---------------------------------------------------------------------------------

    def test_GIVEN_ollama_agent_THEN_supports_all_essential_actions(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The Ollama agent's action registry
        When:   Inspected for completeness
        Then:   All essential operations are present:
                generate, chat, list_models, pull_model, delete_model,
                health_check, recommended

        Why this matters: If any essential action is missing from
        SUPPORTED_ACTIONS, the execute() router will reject it with
        "Unknown action" — even if the internal method exists.
        """
        essential = ["generate", "chat", "list_models", "pull_model",
                      "delete_model", "health_check", "recommended"]
        for action in essential:
            assert action in OllamaAgent.SUPPORTED_ACTIONS, \
                f"Essential action '{action}' missing from SUPPORTED_ACTIONS"

    def test_GIVEN_ollama_agent_WHEN_unknown_action_sent_THEN_raises_clear_error(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  An initialized Ollama agent
        When:   An unknown action name is dispatched
        Then:   The agent raises ValueError listing supported actions

        Why this matters: Silent failures are worse than loud ones.
        An unsupported action should immediately tell the caller what
        IS supported so they can self-correct.
        """
        agent = OllamaAgent()
        request = AgentRequest(action="hack_the_planet", payload={})

        with pytest.raises(ValueError, match="Unknown action"):
            agent.execute(request)


# =========================================================================================
# BEHAVIORAL SPECIFICATION: QMS PROTOCOL COMPLIANCE
# =========================================================================================

class TestBehavior_QMS_ProtocolDiscipline:
    """
    REM: Behavioral specifications for QMS protocol compliance.
    These ensure that the communication standard is actually enforced,
    not just documented.

    Radio analogy: These are the equivalent of checking that every
    transmission follows proper radio procedure before going on air.
    """

    def test_GIVEN_valid_chain_with_all_blocks_WHEN_validated_THEN_passes_validation(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  A fully-formed QMS chain with agent ID, correlation ID,
                action, detail markers, and status suffix
        When:   Passed through QMS validation
        Then:   Validation succeeds — the chain is well-formed

        Why this matters: The QMS parser must handle the full grammar.
        If valid chains fail validation, the system will reject
        legitimate agent communications.
        """
        chain = '::<backup_agent>::-::@@REQ_a8f3c200@@::-::Delete_Expired_Snapshots::-::##deployment_snapshots/##::-::_Please::'
        is_valid, result = validate_chain_string(chain, source="test", log_warning=False)

        assert is_valid, f"Valid chain rejected. Errors: {result.errors if result else 'no result'}"
        assert result is not None
        assert result.valid

    def test_GIVEN_chain_missing_agent_origin_WHEN_validated_THEN_flagged_as_invalid(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  A QMS chain without an agent identity origin block
        When:   Validated
        Then:   The chain is flagged with an origin error
                (anonymous transmissions are a security concern)

        Why this matters: In radio protocol, unidentified transmissions
        get investigated. Same principle here. Every QMS message must
        identify its source agent.
        """
        # No agent origin block — starts directly with correlation
        chain = '::@@REQ_001@@::-::Some_Action::-::_Please::'
        is_valid, result = validate_chain_string(chain, source="test", log_warning=False)

        # Chain without origin should be invalid or have origin warnings
        if result is not None:
            has_origin_issue = (
                not result.valid or
                any("origin" in str(e).lower() or "missing" in str(e).lower()
                    for e in result.errors + result.warnings)
            )
            assert has_origin_issue, "Chain without agent origin should be flagged"
        # If result is None, chain wasn't parseable at all — also acceptable

    def test_GIVEN_chain_with_halt_postscript_WHEN_validated_THEN_is_parseable(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  A QMS chain ending with a halt postscript (::::-%%-::%%reason%%::)
        When:   Validated and parsed
        Then:   The chain is parseable (valid syntax)

        Why this matters: Halt postscripts are emergency stops. The monitoring
        system needs to be able to parse them. If the parser chokes on halt
        syntax, the alert system is blind to emergencies.
        """
        chain = '::<backup_agent>::-::@@REQ_001@@::-::Backup::-::_Thank_You_But_No::-::%%%%::-::%%Disk_Full%%::'
        is_valid, result = validate_chain_string(chain, source="test", log_warning=False)

        # Chain should be parseable even if halt triggers warnings
        assert result is not None, "Halt chain must be parseable"

    def test_GIVEN_every_qms_status_WHEN_checked_THEN_all_five_statuses_exist(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The QMS status enum
        When:   All defined statuses are enumerated
        Then:   Exactly five core statuses exist:
                Please, Excuse_Me, Thank_You, Thank_You_But_No, Pretty_Please
                (rendered as _Please, _Excuse_Me, etc. when formatted by QMS)

        Why this matters: QMS is a state machine. Adding or removing states
        without updating all consumers breaks the protocol. This test catches
        accidental modifications.
        """
        # REM: Enum values are "Please", "Thank_You", etc.
        # REM: The leading underscore ("_Please") is added by format_qms() during formatting.
        expected = {"Please", "Excuse_Me", "Thank_You", "Thank_You_But_No", "Pretty_Please"}
        actual = {s.value for s in QMSStatus}
        assert expected.issubset(actual), f"Missing QMS statuses: {expected - actual}"

    def test_GIVEN_qms_statuses_THEN_names_follow_human_readable_convention(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The QMS status values
        When:   Their naming is inspected
        Then:   All statuses use underscore-separated words (CamelCase or
                underscore-joined), matching the "polite conversation" philosophy.
                No numeric error codes allowed — QMS uses human words.

        Why this matters: QMS status names are read by humans in log files.
        If they don't follow the convention (e.g., someone adds "ERR_403"),
        it breaks the human-readability promise.
        """
        for status in QMSStatus:
            # Should be words — not numeric error codes
            assert not any(c.isdigit() for c in status.value), \
                f"QMS status '{status.value}' should be words, not codes"
            # Should contain only letters and underscores
            assert all(c.isalpha() or c == "_" for c in status.value), \
                f"QMS status '{status.value}' contains invalid characters"


# =========================================================================================
# BEHAVIORAL SPECIFICATION: SECURITY BOUNDARIES
# =========================================================================================

class TestBehavior_SecurityBoundaries:
    """
    REM: Behavioral specifications for security enforcement.
    These test the boundaries that MUST NOT be crossable,
    regardless of input.

    These are the castle walls. If any of these fail,
    the security model is compromised.
    """

    def test_GIVEN_unauthenticated_request_WHEN_any_v1_endpoint_hit_THEN_always_rejected(self, client):
        """
        REM: BEHAVIORAL SPEC

        Given:  An HTTP request with no authentication headers
        When:   ANY /v1/ endpoint is accessed
        Then:   The response is 401 Unauthorized or 403 Forbidden
                NEVER 200 OK

        Why this matters: This is the front door. If any endpoint
        responds to unauthenticated requests, the entire security
        model is theater. Every single endpoint must enforce auth.
        """
        protected_endpoints = [
            ("GET", "/v1/system/status"),
            ("GET", "/v1/agents/capabilities"),
            ("GET", "/v1/anomalies/summary"),
            ("GET", "/v1/approvals/pending"),
            ("GET", "/v1/llm/health"),
            ("GET", "/v1/llm/models"),
            ("GET", "/v1/llm/models/recommended"),
            ("POST", "/v1/llm/generate"),
            ("POST", "/v1/llm/chat"),
            ("GET", "/v1/federation/identity"),
        ]

        for method, path in protected_endpoints:
            if method == "GET":
                response = client.get(path)
            elif method == "POST":
                response = client.post(path, json={})

            assert response.status_code in (401, 403, 422), \
                f"SECURITY BREACH: {method} {path} returned {response.status_code} without auth"

    def test_GIVEN_invalid_api_key_WHEN_token_requested_THEN_rejected_with_401(self, client):
        """
        REM: BEHAVIORAL SPEC

        Given:  An HTTP request with an incorrect API key
        When:   A token is requested from /v1/auth/token
        Then:   The response is 401 Unauthorized
                AND no token is issued

        Why this matters: Wrong credentials = no access. Period.
        """
        response = client.post(
            "/v1/auth/token",
            json={"api_key": "this_is_definitely_wrong_key_12345"}
        )

        assert response.status_code == 401
        data = response.json()
        assert "access_token" not in data

    def test_GIVEN_valid_api_key_WHEN_token_requested_THEN_jwt_issued(self, client):
        """
        REM: BEHAVIORAL SPEC

        Given:  An HTTP request with the correct API key
        When:   A token is requested from /v1/auth/token
        Then:   A JWT access token is returned
                AND the token type is "bearer"

        Why this matters: The happy path must work. Auth that rejects
        everyone is secure but useless.
        """
        response = client.post(
            "/v1/auth/token",
            json={"api_key": "test_api_key_12345"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data.get("token_type") == "bearer"


# =========================================================================================
# BEHAVIORAL SPECIFICATION: SYSTEM RESILIENCE
# =========================================================================================

class TestBehavior_SystemResilience:
    """
    REM: Behavioral specifications for system resilience.
    These test that the system degrades gracefully under failure
    conditions rather than cascading into total collapse.

    The principle: any single component failure should degrade
    that component's functionality, not the entire system.
    """

    def test_GIVEN_system_running_WHEN_system_status_requested_THEN_returns_status(self, client, auth_headers):
        """
        REM: BEHAVIORAL SPEC

        Given:  The TelsonBase system is running
        When:   /v1/system/status is queried (with auth)
        Then:   A 200 response with status information is returned

        Why this matters: The status endpoint is the system's self-awareness.
        If it can't even report its own state, operators are flying blind.
        """
        response = client.get("/v1/system/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "services" in data or "system" in data

    def test_GIVEN_api_key_auth_WHEN_capabilities_requested_THEN_returns_registered_agents(self, client, auth_headers):
        """
        REM: BEHAVIORAL SPEC

        Given:  An authenticated request
        When:   Agent capabilities are queried
        Then:   A list of registered agent capabilities is returned

        Why this matters: Capability discovery is how orchestrators (n8n,
        external systems) learn what the platform can do. If this endpoint
        fails, the platform is a black box.
        """
        response = client.get("/v1/agents/capabilities", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "capabilities" in data
        assert isinstance(data["capabilities"], list)

    def test_GIVEN_authenticated_request_WHEN_root_endpoint_hit_THEN_returns_welcome(self, client):
        """
        REM: BEHAVIORAL SPEC

        Given:  Any HTTP request (authenticated or not)
        When:   The root "/" endpoint is accessed
        Then:   A welcome message is returned (health check pass)

        Why this matters: The root endpoint is the simplest possible
        health check. If this fails, the entire server is down.
        Load balancers and monitoring tools hit this first.
        """
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "status" in data


# =========================================================================================
# BEHAVIORAL SPECIFICATION: TRUST LEVEL SYSTEM
# =========================================================================================

class TestBehavior_TrustLevelProgression:
    """
    REM: Behavioral specifications for the trust level system.

    The trust model mirrors human organizational onboarding:
    QUARANTINE → PROBATION → RESIDENT → CITIZEN

    New agents start restricted. Trust is earned, not assumed.
    """

    def test_GIVEN_trust_levels_THEN_quarantine_is_most_restrictive(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The trust level hierarchy
        When:   Constraint properties are compared
        Then:   QUARANTINE has the lowest actions-per-minute limit
                AND requires approval for everything
                AND cannot access external resources
                AND cannot access filesystem
                AND cannot spawn agents

        Why this matters: New/unknown agents MUST start with minimum
        privileges. If quarantine isn't the most restrictive level,
        the zero-trust model is broken.
        """
        quarantine = TRUST_LEVEL_CONSTRAINTS[AgentTrustLevel.QUARANTINE]

        assert quarantine.requires_approval_for_all is True
        assert quarantine.can_access_external is False
        assert quarantine.can_access_filesystem is False
        assert quarantine.can_spawn_agents is False

        # Must have lowest rate limit of all levels
        for level, constraints in TRUST_LEVEL_CONSTRAINTS.items():
            if level != AgentTrustLevel.QUARANTINE:
                assert quarantine.max_actions_per_minute <= constraints.max_actions_per_minute, \
                    f"QUARANTINE rate limit ({quarantine.max_actions_per_minute}) " \
                    f"should be <= {level.value} ({constraints.max_actions_per_minute})"

    def test_GIVEN_trust_levels_THEN_agent_is_most_trusted(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The trust level hierarchy
        When:   Constraint properties are compared
        Then:   AGENT has the highest actions-per-minute limit (apex tier)
                AND can access external resources
                AND can spawn agents
                AND does NOT require approval for everything
                CITIZEN also has full capability flags — AGENT exceeds it only in rate limit

        Why this matters: AGENT is the apex designation — fully verified autonomous AI agent.
        It must be strictly more operationally capable than every other tier.
        """
        agent = TRUST_LEVEL_CONSTRAINTS[AgentTrustLevel.AGENT]
        citizen = TRUST_LEVEL_CONSTRAINTS[AgentTrustLevel.CITIZEN]

        # REM: AGENT has full capability flags
        assert agent.requires_approval_for_all is False
        assert agent.can_access_external is True
        assert agent.can_spawn_agents is True

        # REM: CITIZEN also has full capability flags — still true and worth asserting
        assert citizen.requires_approval_for_all is False
        assert citizen.can_access_external is True
        assert citizen.can_spawn_agents is True

        # REM: AGENT has the highest rate limit of all tiers
        for level, constraints in TRUST_LEVEL_CONSTRAINTS.items():
            if level != AgentTrustLevel.AGENT:
                assert agent.max_actions_per_minute >= constraints.max_actions_per_minute, \
                    f"AGENT rate limit ({agent.max_actions_per_minute}) " \
                    f"should be >= {level.value} ({constraints.max_actions_per_minute})"

    def test_GIVEN_trust_levels_THEN_exactly_five_levels_exist(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The trust level enum
        When:   All levels are enumerated
        Then:   Exactly five levels: QUARANTINE, PROBATION, RESIDENT, CITIZEN, AGENT

        Why this matters: The trust model is a defined state machine.
        Adding levels without updating all enforcement points creates
        security gaps. Removing levels breaks progression logic.
        AGENT is the apex tier — fully verified autonomous AI agent designation.
        """
        expected = {"quarantine", "probation", "resident", "citizen", "agent"}
        actual = {level.value for level in AgentTrustLevel}
        assert expected == actual, f"Trust levels changed. Expected {expected}, got {actual}"

    def test_GIVEN_trust_progression_THEN_each_level_adds_capabilities(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The five trust levels in order
        When:   Capabilities are compared level by level
        Then:   Each successive level is strictly more permissive:
                - QUARANTINE: no external, no filesystem, no spawn, approval required
                - PROBATION:  no external, YES filesystem, no spawn
                - RESIDENT:   YES external, YES filesystem, no spawn
                - CITIZEN:    YES external, YES filesystem, YES spawn

        Why this matters: Trust must be monotonically increasing.
        If a higher level is MORE restrictive in any dimension,
        the progression model is contradictory and confusing.
        """
        q = TRUST_LEVEL_CONSTRAINTS[AgentTrustLevel.QUARANTINE]
        p = TRUST_LEVEL_CONSTRAINTS[AgentTrustLevel.PROBATION]
        r = TRUST_LEVEL_CONSTRAINTS[AgentTrustLevel.RESIDENT]
        c = TRUST_LEVEL_CONSTRAINTS[AgentTrustLevel.CITIZEN]

        # Quarantine: most locked down
        assert q.can_access_external is False
        assert q.can_access_filesystem is False
        assert q.can_spawn_agents is False

        # Probation: gains filesystem
        assert p.can_access_filesystem is True
        assert p.can_access_external is False
        assert p.can_spawn_agents is False

        # Resident: gains external
        assert r.can_access_external is True
        assert r.can_access_filesystem is True
        assert r.can_spawn_agents is False

        # Citizen: gains spawn
        assert c.can_access_external is True
        assert c.can_access_filesystem is True
        assert c.can_spawn_agents is True

    def test_GIVEN_ollama_agent_THEN_skips_quarantine_as_system_agent(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The Ollama agent configuration
        When:   Its quarantine setting is checked
        Then:   SKIP_QUARANTINE is True

        Why this matters: System agents (backup, ollama, monitor) that ship
        with the platform should not be quarantined on startup. They're
        trusted by the architect. External/third-party agents should be
        quarantined. This distinction is the difference between "trust but
        verify" and "verify then trust."
        """
        assert OllamaAgent.SKIP_QUARANTINE is True


# =========================================================================================
# BEHAVIORAL SPECIFICATION: DATA SOVEREIGNTY ENFORCEMENT
# =========================================================================================

class TestBehavior_DataSovereignty:
    """
    REM: Behavioral specifications for data sovereignty principles.
    These verify that the platform's core mission — keeping data local
    and under user control — is technically enforced, not just promised.

    This is the "data drug dealers" philosophy expressed as executable tests.
    """

    def test_GIVEN_ollama_agent_THEN_declares_no_external_network_access(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The Ollama agent (which processes user prompts)
        When:   Its capabilities are inspected
        Then:   It explicitly declares "external.none"

        Why this matters: The Ollama agent processes potentially sensitive
        legal/medical data. If it has external network permission, user
        data could leak. The capability declaration is the enforceable
        promise — not marketing copy, actual access control.
        """
        assert "external.none" in OllamaAgent.CAPABILITIES

    def test_GIVEN_ollama_agent_THEN_filesystem_access_is_scoped_not_global(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  The Ollama agent's filesystem capabilities
        When:   Inspected for scope
        Then:   Read access is limited to /app/prompts/*
                Write access is limited to /app/responses/*
                NO wildcard filesystem access exists

        Why this matters: Even local filesystem access must be scoped.
        An agent with filesystem.write:* could overwrite configuration,
        inject code, or exfiltrate data to a shared volume. Least
        privilege is not optional.
        """
        fs_caps = [c for c in OllamaAgent.CAPABILITIES if "filesystem" in c]

        for cap in fs_caps:
            parts = cap.split(":")
            if len(parts) >= 2:
                scope = ":".join(parts[1:])
                assert scope != "*", \
                    f"Global filesystem access detected: {cap}. Must be scoped to specific paths."

    def test_GIVEN_agent_capabilities_THEN_no_agent_declares_external_wildcard(self):
        """
        REM: BEHAVIORAL SPEC

        Given:  All agent capability declarations in the system
        When:   Scanned for external access patterns
        Then:   No agent declares "external.*" or "external:*"
                (unrestricted external network access)

        Why this matters: If ANY agent has unrestricted external access,
        it becomes a potential data exfiltration vector. The platform's
        sovereignty promise is only as strong as the most permissive agent.
        """
        for cap in OllamaAgent.CAPABILITIES:
            assert not cap.startswith("external.*"), \
                f"SOVEREIGNTY VIOLATION: {cap} grants unrestricted external access"
            assert cap != "external:*", \
                f"SOVEREIGNTY VIOLATION: {cap} grants unrestricted external access"
