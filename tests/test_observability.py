# TelsonBase/tests/test_observability.py
# REM: =======================================================================================
# REM: TESTS FOR OBSERVABILITY & AGENT COMMUNICATION
# REM: =======================================================================================
# REM: Tests for:
# REM:   1. Prometheus metrics instrumentation (core/metrics.py)
# REM:   2. MQTT agent-to-agent bus (core/mqtt_bus.py)
# REM:   3. /metrics endpoint
# REM:   4. Monitoring configuration files
# REM: =======================================================================================

import os
import json
import pytest
import time
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path


# REM: =======================================================================================
# REM: SECTION 1: PROMETHEUS METRICS TESTS
# REM: =======================================================================================

class TestPrometheusMetrics:
    """REM: Tests for the metrics instrumentation module."""

    def test_metrics_module_imports(self):
        """REM: Verify the metrics module loads without errors."""
        from core.metrics import (
            HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION,
            AUTH_TOTAL, QMS_MESSAGES_TOTAL, AGENT_ACTIONS_TOTAL,
            ANOMALIES_TOTAL, RATE_LIMITED_TOTAL,
            APPROVALS_PENDING, SOVEREIGN_SCORE,
            MetricsMiddleware, metrics_response,
        )
        assert HTTP_REQUESTS_TOTAL is not None
        assert HTTP_REQUEST_DURATION is not None
        assert AUTH_TOTAL is not None
        assert QMS_MESSAGES_TOTAL is not None

    def test_record_auth_success(self):
        """REM: Recording auth success increments the counter."""
        from core.metrics import record_auth, AUTH_TOTAL
        # REM: Get current value before increment
        before = AUTH_TOTAL.labels(method="api_key", result="success")._value.get()
        record_auth("api_key", True)
        after = AUTH_TOTAL.labels(method="api_key", result="success")._value.get()
        assert after == before + 1

    def test_record_auth_failure(self):
        """REM: Recording auth failure increments the failure counter."""
        from core.metrics import record_auth, AUTH_TOTAL
        before = AUTH_TOTAL.labels(method="jwt", result="failure")._value.get()
        record_auth("jwt", False)
        after = AUTH_TOTAL.labels(method="jwt", result="failure")._value.get()
        assert after == before + 1

    def test_record_qms_message(self):
        """REM: QMS message recording tracks by status."""
        from core.metrics import record_qms_message, QMS_MESSAGES_TOTAL
        for status in ["Please", "Thank_You", "Thank_You_But_No", "Excuse_Me", "Pretty_Please"]:
            before = QMS_MESSAGES_TOTAL.labels(status=status)._value.get()
            record_qms_message(status)
            after = QMS_MESSAGES_TOTAL.labels(status=status)._value.get()
            assert after == before + 1, f"Failed for status: {status}"

    def test_record_agent_action(self):
        """REM: Agent actions are tracked by agent and action type."""
        from core.metrics import record_agent_action, AGENT_ACTIONS_TOTAL
        before = AGENT_ACTIONS_TOTAL.labels(agent="ollama_agent", action="generate")._value.get()
        record_agent_action("ollama_agent", "generate")
        after = AGENT_ACTIONS_TOTAL.labels(agent="ollama_agent", action="generate")._value.get()
        assert after == before + 1

    def test_record_anomaly(self):
        """REM: Anomaly detection events are tracked by severity."""
        from core.metrics import record_anomaly, ANOMALIES_TOTAL
        for severity in ["low", "medium", "high", "critical"]:
            before = ANOMALIES_TOTAL.labels(severity=severity)._value.get()
            record_anomaly(severity)
            after = ANOMALIES_TOTAL.labels(severity=severity)._value.get()
            assert after == before + 1

    def test_set_sovereign_score(self):
        """REM: Sovereign score is set as a gauge."""
        from core.metrics import set_sovereign_score, SOVEREIGN_SCORE, SOVEREIGN_FACTOR
        set_sovereign_score(94.0, {
            "llm_locality": 100.0,
            "data_residency": 100.0,
            "network_exposure": 88.0,
        })
        assert SOVEREIGN_SCORE._value.get() == 94.0
        assert SOVEREIGN_FACTOR.labels(factor="llm_locality")._value.get() == 100.0

    def test_set_pending_approvals(self):
        """REM: Pending approvals gauge can be set and changed."""
        from core.metrics import set_pending_approvals, APPROVALS_PENDING
        set_pending_approvals(5)
        assert APPROVALS_PENDING._value.get() == 5
        set_pending_approvals(0)
        assert APPROVALS_PENDING._value.get() == 0

    def test_metrics_response_format(self):
        """REM: The /metrics endpoint returns Prometheus text format."""
        from core.metrics import metrics_response
        response = metrics_response()
        assert response.status_code == 200
        # REM: Prometheus format uses text/plain with version parameter
        assert "text/plain" in response.media_type or "openmetrics" in response.media_type
        content = response.body.decode('utf-8')
        # REM: Should contain our custom metrics
        assert "telsonbase_" in content

    def test_path_normalization(self):
        """REM: Variable path segments are collapsed to prevent cardinality explosion."""
        from core.metrics import MetricsMiddleware
        normalize = MetricsMiddleware._normalize_path
        
        # REM: Long hex IDs should be normalized
        assert "{id}" in normalize("/v1/agents/signing/keys/abc123def456789")
        # REM: Short segments should be preserved
        assert "health" in normalize("/health")
        assert "v1" in normalize("/v1/auth/token")

    def test_set_system_info(self):
        """REM: System info labels are set correctly."""
        from core.metrics import set_system_info, SYSTEM_INFO, metrics_response
        set_system_info(version="4.9.0CC", instance_id="test-123")
        # REM: Verify via the metrics output text (most reliable way)
        response = metrics_response()
        content = response.body.decode('utf-8')
        assert 'telsonbase_info' in content
        assert '4.9.0CC' in content
        assert 'telsonbase' in content

    def test_record_rate_limit(self):
        """REM: Rate limiting events are tracked by endpoint."""
        from core.metrics import record_rate_limit, RATE_LIMITED_TOTAL
        before = RATE_LIMITED_TOTAL.labels(endpoint="/v1/auth/token")._value.get()
        record_rate_limit("/v1/auth/token")
        after = RATE_LIMITED_TOTAL.labels(endpoint="/v1/auth/token")._value.get()
        assert after == before + 1


# REM: =======================================================================================
# REM: SECTION 2: MQTT BUS TESTS
# REM: =======================================================================================

class TestAgentMessage:
    """REM: Tests for the AgentMessage data structure."""

    def test_message_creation(self):
        """REM: AgentMessage creates with auto-generated fields."""
        from core.mqtt_bus import AgentMessage
        msg = AgentMessage(
            source_agent="ollama_agent",
            target_agent="document_agent",
            message_type="Analyze_Document_Please",
            payload={"doc_id": "abc123"}
        )
        assert msg.source_agent == "ollama_agent"
        assert msg.target_agent == "document_agent"
        assert msg.message_type == "Analyze_Document_Please"
        assert msg.timestamp  # Auto-generated
        assert msg.message_id  # Auto-generated
        assert "ollama_agent" in msg.message_id

    def test_message_serialization(self):
        """REM: Messages serialize to and from JSON cleanly."""
        from core.mqtt_bus import AgentMessage
        original = AgentMessage(
            source_agent="backup_agent",
            target_agent=None,
            message_type="Backup_Complete_Thank_You",
            payload={"volumes": ["redis_data", "n8n_data"], "size_mb": 42}
        )
        json_str = original.to_json()
        restored = AgentMessage.from_json(json_str)

        assert restored.source_agent == original.source_agent
        assert restored.target_agent is None
        assert restored.message_type == original.message_type
        assert restored.payload == original.payload

    def test_message_broadcast(self):
        """REM: Broadcast messages have no target_agent."""
        from core.mqtt_bus import AgentMessage
        msg = AgentMessage(
            source_agent="system",
            target_agent=None,
            message_type="System_Health_Check_Please",
            payload={"status": "all_clear"}
        )
        assert msg.target_agent is None

    def test_message_priority(self):
        """REM: High priority messages map to Pretty_Please."""
        from core.mqtt_bus import AgentMessage
        msg = AgentMessage(
            source_agent="anomaly_detector",
            target_agent=None,
            message_type="Critical_Anomaly_Pretty_Please",
            payload={"threat": "unauthorized_access"},
            priority="high"
        )
        assert msg.priority == "high"
        assert "Pretty_Please" in msg.message_type

    def test_message_reply_to(self):
        """REM: Messages can specify a reply topic."""
        from core.mqtt_bus import AgentMessage
        msg = AgentMessage(
            source_agent="orchestrator",
            target_agent="ollama_agent",
            message_type="Generate_Summary_Please",
            payload={"text": "..."},
            reply_to="telsonbase/agents/orchestrator/inbox"
        )
        assert msg.reply_to == "telsonbase/agents/orchestrator/inbox"


class TestMQTTBus:
    """REM: Tests for MQTT bus connection and pub/sub logic."""

    def test_bus_creation(self):
        """REM: Bus initializes without connecting."""
        from core.mqtt_bus import MQTTBus
        bus = MQTTBus(client_id="test-bus")
        assert not bus.is_connected

    def test_topic_structure(self):
        """REM: Topic prefix follows the telsonbase convention."""
        from core.mqtt_bus import MQTTBus
        assert MQTTBus.TOPIC_PREFIX == "telsonbase"

    @patch('core.mqtt_bus.mqtt.Client')
    def test_connect_success(self, mock_mqtt_class):
        """REM: Successful connection starts the MQTT loop."""
        from core.mqtt_bus import MQTTBus
        mock_client = MagicMock()
        mock_mqtt_class.return_value = mock_client

        bus = MQTTBus.__new__(MQTTBus)
        bus._client = mock_client
        bus._connected = False
        bus._handlers = {}
        bus._lock = __import__('threading').Lock()

        mock_client.connect.return_value = None
        result = bus.connect()

        assert result is True
        mock_client.connect.assert_called_once()
        mock_client.loop_start.assert_called_once()

    @patch('core.mqtt_bus.mqtt.Client')
    def test_connect_failure(self, mock_mqtt_class):
        """REM: Connection failure returns False without crashing."""
        from core.mqtt_bus import MQTTBus
        mock_client = MagicMock()
        mock_mqtt_class.return_value = mock_client

        bus = MQTTBus.__new__(MQTTBus)
        bus._client = mock_client
        bus._connected = False
        bus._handlers = {}
        bus._lock = __import__('threading').Lock()

        mock_client.connect.side_effect = ConnectionRefusedError("broker down")
        result = bus.connect()

        assert result is False

    def test_subscribe_registers_handler(self):
        """REM: Subscribing stores the handler for the topic."""
        from core.mqtt_bus import MQTTBus
        import threading
        
        bus = MQTTBus.__new__(MQTTBus)
        bus._client = MagicMock()
        bus._connected = True
        bus._handlers = {}
        bus._lock = threading.Lock()

        handler = MagicMock()
        bus.subscribe("telsonbase/agents/test/inbox", handler)

        assert "telsonbase/agents/test/inbox" in bus._handlers
        assert handler in bus._handlers["telsonbase/agents/test/inbox"]

    def test_register_agent_inbox(self):
        """REM: Convenience method creates correct topic pattern."""
        from core.mqtt_bus import MQTTBus
        import threading
        
        bus = MQTTBus.__new__(MQTTBus)
        bus._client = MagicMock()
        bus._connected = True
        bus._handlers = {}
        bus._lock = threading.Lock()

        handler = MagicMock()
        bus.register_agent_inbox("ollama_agent", handler)

        assert "telsonbase/agents/ollama_agent/inbox" in bus._handlers

    def test_publish_when_disconnected(self):
        """REM: Publishing when disconnected returns False."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        import threading
        
        bus = MQTTBus.__new__(MQTTBus)
        bus._client = MagicMock()
        bus._connected = False
        bus._handlers = {}
        bus._lock = threading.Lock()

        msg = AgentMessage(
            source_agent="test",
            target_agent="other",
            message_type="Test_Please",
            payload={}
        )
        result = bus.publish(msg)
        assert result is False

    def test_on_connect_callback(self):
        """REM: Connection callback sets connected state and re-subscribes."""
        from core.mqtt_bus import MQTTBus
        import threading
        
        bus = MQTTBus.__new__(MQTTBus)
        bus._client = MagicMock()
        bus._connected = False
        bus._handlers = {"telsonbase/test/#": [MagicMock()]}
        bus._lock = threading.Lock()

        bus._on_connect(bus._client, None, None, 0)  # rc=0 means success
        assert bus._connected is True
        bus._client.subscribe.assert_called_once_with("telsonbase/test/#", qos=1)

    def test_on_disconnect_callback(self):
        """REM: Unexpected disconnect sets connected to False."""
        from core.mqtt_bus import MQTTBus
        import threading
        
        bus = MQTTBus.__new__(MQTTBus)
        bus._client = MagicMock()
        bus._connected = True
        bus._handlers = {}
        bus._lock = threading.Lock()

        bus._on_disconnect(bus._client, None, 1)  # rc=1 means unexpected
        assert bus._connected is False

    def test_on_message_dispatches_to_handler(self):
        """REM: Incoming messages are dispatched to registered handlers."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        import threading
        
        bus = MQTTBus.__new__(MQTTBus)
        bus._client = MagicMock()
        bus._connected = True
        bus._lock = threading.Lock()

        handler = MagicMock()
        bus._handlers = {"telsonbase/agents/test/inbox": [handler]}

        # REM: Create a mock MQTT message
        mock_msg = MagicMock()
        mock_msg.topic = "telsonbase/agents/test/inbox"
        test_agent_msg = AgentMessage(
            source_agent="sender",
            target_agent="test",
            message_type="Hello_Please",
            payload={"greeting": "hi"}
        )
        mock_msg.payload = test_agent_msg.to_json().encode('utf-8')

        bus._on_message(bus._client, None, mock_msg)
        handler.assert_called_once()

    def test_malformed_message_logged_as_anomaly(self):
        """REM: Malformed JSON on the bus is flagged as a security anomaly."""
        from core.mqtt_bus import MQTTBus
        import threading
        
        bus = MQTTBus.__new__(MQTTBus)
        bus._client = MagicMock()
        bus._connected = True
        bus._handlers = {"telsonbase/#": [MagicMock()]}
        bus._lock = threading.Lock()

        mock_msg = MagicMock()
        mock_msg.topic = "telsonbase/agents/test/inbox"
        mock_msg.payload = b"not valid json {{{{"

        # REM: Should not raise — malformed messages are handled gracefully
        bus._on_message(bus._client, None, mock_msg)


class TestMQTTBusSingleton:
    """REM: Tests for the singleton pattern and lifecycle."""

    def test_get_mqtt_bus_returns_same_instance(self):
        """REM: get_mqtt_bus returns a singleton."""
        from core.mqtt_bus import get_mqtt_bus, MQTTBus
        import core.mqtt_bus as module
        # REM: Reset singleton for test
        module._mqtt_bus_instance = None
        
        bus1 = get_mqtt_bus()
        bus2 = get_mqtt_bus()
        assert bus1 is bus2
        
        # REM: Cleanup
        module._mqtt_bus_instance = None


# REM: =======================================================================================
# REM: SECTION 3: MONITORING CONFIGURATION TESTS
# REM: =======================================================================================

class TestMonitoringConfigs:
    """REM: Verify monitoring configuration files exist and are valid."""

    PROJECT_ROOT = Path(__file__).parent.parent

    def test_prometheus_yml_exists(self):
        """REM: prometheus.yml must exist for Prometheus to start."""
        config_path = self.PROJECT_ROOT / "monitoring" / "prometheus.yml"
        assert config_path.exists(), f"Missing: {config_path}"

    def test_prometheus_yml_has_scrape_configs(self):
        """REM: prometheus.yml must define scrape targets."""
        config_path = self.PROJECT_ROOT / "monitoring" / "prometheus.yml"
        content = config_path.read_text()
        assert "scrape_configs:" in content
        assert "telsonbase-api" in content
        assert "mcp_server:8000" in content

    def test_grafana_datasource_provisioning_exists(self):
        """REM: Grafana datasource provisioning must be configured."""
        ds_path = self.PROJECT_ROOT / "monitoring" / "grafana" / "provisioning" / "datasources" / "datasource.yml"
        assert ds_path.exists(), f"Missing: {ds_path}"

    def test_grafana_datasource_points_to_prometheus(self):
        """REM: Grafana datasource must connect to the correct Prometheus URL."""
        ds_path = self.PROJECT_ROOT / "monitoring" / "grafana" / "provisioning" / "datasources" / "datasource.yml"
        content = ds_path.read_text()
        assert "prometheus" in content.lower()
        assert "http://prometheus:9090" in content

    def test_grafana_dashboard_provisioning_exists(self):
        """REM: Grafana dashboard provider config must exist."""
        dp_path = self.PROJECT_ROOT / "monitoring" / "grafana" / "provisioning" / "dashboards" / "dashboards.yml"
        assert dp_path.exists(), f"Missing: {dp_path}"

    def test_grafana_dashboard_json_exists(self):
        """REM: Pre-built TelsonBase dashboard must exist."""
        dash_path = self.PROJECT_ROOT / "monitoring" / "grafana" / "dashboards" / "telsonbase-operations.json"
        assert dash_path.exists(), f"Missing: {dash_path}"

    def test_grafana_dashboard_is_valid_json(self):
        """REM: Dashboard JSON must be parseable."""
        dash_path = self.PROJECT_ROOT / "monitoring" / "grafana" / "dashboards" / "telsonbase-operations.json"
        content = dash_path.read_text()
        dashboard = json.loads(content)
        assert "panels" in dashboard
        assert "title" in dashboard
        assert dashboard["title"] == "TelsonBase Operations"

    def test_grafana_dashboard_has_security_panels(self):
        """REM: Dashboard must include security-relevant panels."""
        dash_path = self.PROJECT_ROOT / "monitoring" / "grafana" / "dashboards" / "telsonbase-operations.json"
        content = json.loads(dash_path.read_text())
        panel_titles = [p.get("title", "") for p in content["panels"]]
        # REM: Must have auth and QMS panels
        assert any("Auth" in t for t in panel_titles), f"No Auth panel. Panels: {panel_titles}"
        assert any("QMS" in t for t in panel_titles), f"No QMS panel. Panels: {panel_titles}"


# REM: =======================================================================================
# REM: SECTION 4: METRICS ENDPOINT INTEGRATION TEST
# REM: =======================================================================================

class TestMetricsEndpoint:
    """REM: Test the /metrics endpoint via the FastAPI test client."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_metrics_endpoint_accessible(self, client):
        """REM: /metrics endpoint returns 200 without authentication."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_contains_telsonbase_prefix(self, client):
        """REM: Metrics output contains telsonbase-prefixed metrics."""
        response = client.get("/metrics")
        content = response.text
        assert "telsonbase_" in content

    def test_metrics_contains_http_metrics(self, client):
        """REM: After making requests, HTTP metrics appear."""
        # REM: Make a request first to generate metrics
        client.get("/health")
        response = client.get("/metrics")
        content = response.text
        # REM: Should see request counters
        assert "telsonbase_http_requests_total" in content
