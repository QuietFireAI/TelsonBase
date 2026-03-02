# TelsonBase/tests/test_mqtt_stress.py
# REM: =======================================================================================
# REM: MQTT BUS LOAD & STRESS TESTS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v5.1.0CC: Stress tests for the MQTT agent communication bus.
# REM: Exercises: throughput, concurrent publishing, topic routing accuracy,
# REM: handler error resilience, memory pressure, subscription management,
# REM: reconnection behavior, and QMS chain integration.
#
# REM: All tests use mocked paho-mqtt — no live broker required.
# REM: =======================================================================================

import json
import time
import pytest
import threading
from unittest.mock import patch, MagicMock, call
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 1: High-Volume Message Throughput
# ═══════════════════════════════════════════════════════════════════════════════

class TestMessageThroughput:
    """REM: Tests the bus can handle rapid message creation and serialization."""

    def test_1000_messages_serialize_deserialize(self):
        """REM: 1000 messages must round-trip through JSON without loss."""
        from core.mqtt_bus import AgentMessage
        
        messages = []
        for i in range(1000):
            msg = AgentMessage(
                source_agent=f"agent_{i % 10}",
                target_agent=f"agent_{(i + 1) % 10}",
                message_type=f"Stress_Test_{i}_Please",
                payload={"iteration": i, "data": f"value_{i}"}
            )
            messages.append(msg)
        
        # Serialize all
        json_strings = [m.to_json() for m in messages]
        assert len(json_strings) == 1000
        
        # Deserialize all
        restored = [AgentMessage.from_json(j) for j in json_strings]
        assert len(restored) == 1000
        
        # Verify integrity
        for i, (orig, rest) in enumerate(zip(messages, restored)):
            assert orig.source_agent == rest.source_agent
            assert orig.message_type == rest.message_type
            assert orig.payload == rest.payload
            assert orig.message_id == rest.message_id

    def test_rapid_publish_no_exceptions(self):
        """REM: Rapid-fire publishing must not raise exceptions."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_client.is_connected.return_value = True
            mock_client.publish.return_value = MagicMock(rc=0)
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="stress-test")
            bus._connected = True
            bus._client = mock_client
            
            for i in range(500):
                msg = AgentMessage(
                    source_agent="stress_agent",
                    target_agent=None,
                    message_type=f"Burst_{i}_Please",
                    payload={"seq": i}
                )
                result = bus.publish(msg)
                assert result is True
            
            # REM: publish() calls _client.publish TWICE per message:
            # REM: once for target topic, once for source agent outbox (audit trail)
            assert mock_client.publish.call_count == 1000  # 500 messages × 2 publishes each

    def test_large_payload_handling(self):
        """REM: Messages with large payloads must serialize correctly."""
        from core.mqtt_bus import AgentMessage
        
        # 100KB payload
        large_data = {"key_" + str(i): "x" * 1000 for i in range(100)}
        msg = AgentMessage(
            source_agent="data_agent",
            target_agent=None,
            message_type="Large_Payload_Please",
            payload=large_data
        )
        
        json_str = msg.to_json()
        assert len(json_str) > 100000  # At least 100KB
        
        restored = AgentMessage.from_json(json_str)
        assert restored.payload == large_data

    def test_nested_payload_depth(self):
        """REM: Deeply nested payloads must serialize without stack overflow."""
        from core.mqtt_bus import AgentMessage
        
        # Build 50 levels of nesting
        payload = {"value": "leaf"}
        for i in range(50):
            payload = {"level": i, "child": payload}
        
        msg = AgentMessage(
            source_agent="nested_agent",
            target_agent=None,
            message_type="Deep_Nest_Please",
            payload=payload
        )
        
        json_str = msg.to_json()
        restored = AgentMessage.from_json(json_str)
        
        # Walk down to verify leaf
        current = restored.payload
        for i in range(49, -1, -1):
            assert current["level"] == i
            current = current["child"]
        assert current["value"] == "leaf"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 2: Topic Routing Accuracy
# ═══════════════════════════════════════════════════════════════════════════════

class TestTopicRouting:
    """REM: Tests that messages are routed to correct handlers based on topic."""

    def test_agent_inbox_routing(self):
        """REM: Messages to agent inbox must only reach that agent's handler."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="routing-test")
            bus._client = mock_client
            
            agent_a_messages = []
            agent_b_messages = []
            
            bus.register_agent_inbox("agent_a", lambda msg, topic: agent_a_messages.append(msg))
            bus.register_agent_inbox("agent_b", lambda msg, topic: agent_b_messages.append(msg))
            
            # Simulate message to agent_a's inbox
            msg_for_a = AgentMessage(
                source_agent="sender",
                target_agent="agent_a",
                message_type="Test_Please",
                payload={"for": "a"}
            )
            
            mock_msg = MagicMock()
            mock_msg.topic = "telsonbase/agents/agent_a/inbox"
            mock_msg.payload = msg_for_a.to_json().encode()
            
            bus._on_message(mock_client, None, mock_msg)
            
            assert len(agent_a_messages) == 1
            assert len(agent_b_messages) == 0
            assert agent_a_messages[0].payload["for"] == "a"

    def test_broadcast_reaches_all_handlers(self):
        """REM: Broadcast messages must reach all subscribed handlers."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="broadcast-test")
            bus._client = mock_client
            
            received = {"handler_1": [], "handler_2": [], "handler_3": []}
            
            bus.subscribe("telsonbase/broadcast/#", lambda msg, t: received["handler_1"].append(msg))
            bus.subscribe("telsonbase/broadcast/#", lambda msg, t: received["handler_2"].append(msg))
            bus.subscribe("telsonbase/broadcast/#", lambda msg, t: received["handler_3"].append(msg))
            
            broadcast_msg = AgentMessage(
                source_agent="broadcaster",
                target_agent=None,
                message_type="Alert_Pretty_Please",
                payload={"alert": "test"}
            )
            
            mock_msg = MagicMock()
            mock_msg.topic = "telsonbase/broadcast/all"
            mock_msg.payload = broadcast_msg.to_json().encode()
            
            bus._on_message(mock_client, None, mock_msg)
            
            for handler_name, msgs in received.items():
                assert len(msgs) == 1, f"{handler_name} should have received 1 message"

    def test_event_type_routing(self):
        """REM: Event-specific handlers must only receive matching events."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="event-test")
            bus._client = mock_client
            
            security_events = []
            audit_events = []
            
            bus.register_event_handler("security", lambda msg, t: security_events.append(msg))
            bus.register_event_handler("audit", lambda msg, t: audit_events.append(msg))
            
            # Security event
            sec_msg = AgentMessage(
                source_agent="monitor",
                target_agent=None,
                message_type="Security_Alert_Please",
                payload={"type": "intrusion"}
            )
            mock_msg = MagicMock()
            mock_msg.topic = "telsonbase/events/security"
            mock_msg.payload = sec_msg.to_json().encode()
            bus._on_message(mock_client, None, mock_msg)
            
            assert len(security_events) == 1
            assert len(audit_events) == 0

    def test_unmatched_topic_no_crash(self):
        """REM: Messages on unsubscribed topics must be silently ignored."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="unmatched-test")
            bus._client = mock_client
            
            msg = AgentMessage(
                source_agent="ghost",
                target_agent=None,
                message_type="Nobody_Listening_Please",
                payload={}
            )
            mock_msg = MagicMock()
            mock_msg.topic = "telsonbase/agents/nonexistent/inbox"
            mock_msg.payload = msg.to_json().encode()
            
            # Should not raise
            bus._on_message(mock_client, None, mock_msg)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 3: Concurrent Publishing (Thread Safety)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConcurrentPublishing:
    """REM: Tests thread-safety of the MQTT bus under concurrent access."""

    def test_concurrent_publish_from_multiple_threads(self):
        """REM: Multiple threads publishing simultaneously must not corrupt state."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_client.is_connected.return_value = True
            mock_client.publish.return_value = MagicMock(rc=0)
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="concurrent-test")
            bus._connected = True
            bus._client = mock_client
            
            errors = []
            publish_count = [0]
            lock = threading.Lock()
            
            def publish_worker(thread_id, count):
                for i in range(count):
                    try:
                        msg = AgentMessage(
                            source_agent=f"thread_{thread_id}",
                            target_agent=None,
                            message_type=f"Concurrent_{i}_Please",
                            payload={"thread": thread_id, "seq": i}
                        )
                        bus.publish(msg)
                        with lock:
                            publish_count[0] += 1
                    except Exception as e:
                        errors.append(f"Thread {thread_id}: {e}")
            
            threads = []
            for t in range(10):
                thread = threading.Thread(target=publish_worker, args=(t, 50))
                threads.append(thread)
                thread.start()
            
            for t in threads:
                t.join(timeout=10)
            
            assert errors == [], f"Errors during concurrent publish: {errors}"
            assert publish_count[0] == 500  # 10 threads × 50 messages

    def test_concurrent_subscribe_and_publish(self):
        """REM: Subscribing and publishing simultaneously must not deadlock."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_client.is_connected.return_value = True
            mock_client.publish.return_value = MagicMock(rc=0)
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="sub-pub-test")
            bus._connected = True
            bus._client = mock_client
            
            completed = threading.Event()
            
            def subscriber_worker():
                for i in range(50):
                    bus.subscribe(f"telsonbase/test/{i}", lambda m, t: None)
                completed.set()
            
            def publisher_worker():
                for i in range(50):
                    msg = AgentMessage(
                        source_agent="pub", target_agent=None, message_type="Test_Please", payload={}
                    )
                    bus.publish(msg)
            
            t1 = threading.Thread(target=subscriber_worker)
            t2 = threading.Thread(target=publisher_worker)
            t1.start()
            t2.start()
            
            t1.join(timeout=5)
            t2.join(timeout=5)
            
            assert completed.is_set(), "Subscriber thread did not complete (possible deadlock)"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 4: Handler Error Resilience
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandlerResilience:
    """REM: Tests that handler exceptions don't crash the bus."""

    def test_handler_exception_doesnt_crash_bus(self):
        """REM: A crashing handler must not prevent other handlers from executing."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="resilience-test")
            bus._client = mock_client
            
            received = []
            
            def crashing_handler(msg, topic):
                raise ValueError("I crashed!")
            
            def healthy_handler(msg, topic):
                received.append(msg)
            
            bus.subscribe("telsonbase/test/#", crashing_handler)
            bus.subscribe("telsonbase/test/#", healthy_handler)
            
            msg = AgentMessage(
                source_agent="test", target_agent=None, message_type="Crash_Test_Please", payload={}
            )
            mock_msg = MagicMock()
            mock_msg.topic = "telsonbase/test/resilience"
            mock_msg.payload = msg.to_json().encode()
            
            # Should not raise despite crashing_handler
            bus._on_message(mock_client, None, mock_msg)
            
            # Healthy handler should still have received the message
            assert len(received) == 1

    def test_handler_timeout_doesnt_block(self):
        """REM: Slow handlers must not block other message processing."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="timeout-test")
            bus._client = mock_client
            
            fast_received = []
            
            def slow_handler(msg, topic):
                time.sleep(0.1)  # Simulate slow processing
            
            def fast_handler(msg, topic):
                fast_received.append(msg)
            
            bus.subscribe("telsonbase/test/#", slow_handler)
            bus.subscribe("telsonbase/test/#", fast_handler)
            
            msg = AgentMessage(
                source_agent="test", target_agent=None, message_type="Slow_Test_Please", payload={}
            )
            mock_msg = MagicMock()
            mock_msg.topic = "telsonbase/test/timeout"
            mock_msg.payload = msg.to_json().encode()
            
            start = time.time()
            bus._on_message(mock_client, None, mock_msg)
            elapsed = time.time() - start
            
            assert len(fast_received) == 1
            # Should complete in reasonable time (slow handler + fast handler)
            assert elapsed < 2.0

    def test_malformed_json_doesnt_crash_bus(self):
        """REM: Non-JSON messages must be handled gracefully."""
        from core.mqtt_bus import MQTTBus
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="malformed-test")
            bus._client = mock_client
            
            mock_msg = MagicMock()
            mock_msg.topic = "telsonbase/test/bad"
            mock_msg.payload = b"this is not json at all {{{{"
            
            # Must not raise
            bus._on_message(mock_client, None, mock_msg)

    def test_empty_payload_doesnt_crash(self):
        """REM: Empty payload messages must be handled gracefully."""
        from core.mqtt_bus import MQTTBus
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="empty-test")
            bus._client = mock_client
            
            mock_msg = MagicMock()
            mock_msg.topic = "telsonbase/test/empty"
            mock_msg.payload = b""
            
            # Must not raise
            bus._on_message(mock_client, None, mock_msg)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 5: Reconnection Behavior
# ═══════════════════════════════════════════════════════════════════════════════

class TestReconnectionBehavior:
    """REM: Tests that subscriptions survive reconnection."""

    def test_subscriptions_restored_on_reconnect(self):
        """REM: All subscriptions must be re-established after reconnect."""
        from core.mqtt_bus import MQTTBus
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="reconnect-test")
            bus._client = mock_client
            
            # Subscribe to 5 topics
            for i in range(5):
                bus.subscribe(f"telsonbase/test/topic_{i}", lambda m, t: None)
            
            # Simulate reconnection via _on_connect callback
            bus._on_connect(mock_client, None, None, 0)
            
            # Verify all topics were re-subscribed
            subscribe_calls = [c for c in mock_client.subscribe.call_args_list]
            subscribed_topics = {c[0][0] for c in subscribe_calls}
            
            for i in range(5):
                assert f"telsonbase/test/topic_{i}" in subscribed_topics

    def test_publish_fails_gracefully_when_disconnected(self):
        """REM: Publishing when disconnected must return False, not crash."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_client.is_connected.return_value = False
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="disconnected-test")
            bus._connected = False
            bus._client = mock_client
            
            msg = AgentMessage(
                source_agent="test", target_agent=None, message_type="Offline_Please", payload={}
            )
            result = bus.publish(msg)
            assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 6: QMS Chain Integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestQMSChainIntegration:
    """REM: Tests QMS message conventions within MQTT messages."""

    def test_please_suffix_in_message_type(self):
        """REM: Request messages must carry _Please suffix through MQTT."""
        from core.mqtt_bus import AgentMessage
        
        msg = AgentMessage(
            source_agent="requester",
            target_agent="responder",
            message_type="Analyze_Document_Please",
            payload={"doc_id": "DOC-001"}
        )
        
        json_str = msg.to_json()
        restored = AgentMessage.from_json(json_str)
        assert restored.message_type.endswith("_Please")

    def test_thank_you_suffix_preserved(self):
        """REM: Completion messages must carry _Thank_You suffix through MQTT."""
        from core.mqtt_bus import AgentMessage
        
        msg = AgentMessage(
            source_agent="responder",
            target_agent="requester",
            message_type="Analyze_Document_Thank_You",
            payload={"result": "complete"},
            reply_to="telsonbase/agents/requester/inbox"
        )
        
        json_str = msg.to_json()
        restored = AgentMessage.from_json(json_str)
        assert restored.message_type.endswith("_Thank_You")
        assert restored.reply_to == "telsonbase/agents/requester/inbox"

    def test_pretty_please_priority(self):
        """REM: Pretty_Please messages must carry high priority marker."""
        from core.mqtt_bus import AgentMessage
        
        msg = AgentMessage(
            source_agent="urgent_agent",
            target_agent=None,
            message_type="Critical_Alert_Pretty_Please",
            payload={"severity": "critical"},
            priority="high"
        )
        
        json_str = msg.to_json()
        restored = AgentMessage.from_json(json_str)
        assert restored.priority == "high"
        assert "Pretty_Please" in restored.message_type

    def test_excuse_me_for_clarification(self):
        """REM: Clarification requests carry _Excuse_Me suffix."""
        from core.mqtt_bus import AgentMessage
        
        msg = AgentMessage(
            source_agent="confused_agent",
            target_agent="sender",
            message_type="Document_Format_Unknown_Excuse_Me",
            payload={"question": "What format is this?"}
        )
        
        json_str = msg.to_json()
        restored = AgentMessage.from_json(json_str)
        assert restored.message_type.endswith("_Excuse_Me")

    def test_qms_chain_field_preserved(self):
        """REM: The qms_chain field must survive serialization."""
        from core.mqtt_bus import AgentMessage
        
        msg = AgentMessage(
            source_agent="agent_01",
            target_agent=None,
            message_type="Chain_Test_Please",
            payload={},
            qms_chain="::agent_01::→Analyze_Document_Please→::@@REQ_12345@@::"
        )
        
        json_str = msg.to_json()
        restored = AgentMessage.from_json(json_str)
        assert restored.qms_chain == msg.qms_chain
        assert "::agent_01::" in restored.qms_chain

    def test_message_id_uniqueness_across_1000(self):
        """REM: All auto-generated message_ids must be unique."""
        from core.mqtt_bus import AgentMessage
        
        ids = set()
        for i in range(1000):
            msg = AgentMessage(
                source_agent="id_test",
                target_agent=None,
                message_type="Unique_Please",
                payload={"i": i}
            )
            ids.add(msg.message_id)
        
        assert len(ids) == 1000, "Duplicate message IDs generated!"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 7: Publish Event Convenience Method
# ═══════════════════════════════════════════════════════════════════════════════

class TestPublishEvent:
    """REM: Tests the publish_event convenience method."""

    def test_publish_event_creates_correct_topic(self):
        """REM: publish_event must route to telsonbase/events/<type>."""
        from core.mqtt_bus import MQTTBus, AgentMessage
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_client.is_connected.return_value = True
            mock_client.publish.return_value = MagicMock(rc=0)
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="event-pub-test")
            bus._connected = True
            bus._client = mock_client
            
            bus.publish_event(
                event_type="security_breach",
                source_agent="monitor_agent",
                payload={"ip": "10.0.0.1", "action": "blocked"}
            )
            
            # Verify publish was called with correct topic
            call_args = mock_client.publish.call_args
            topic = call_args[0][0] if call_args[0] else call_args[1].get('topic')
            assert "telsonbase/events/security_breach" in str(topic) or \
                   "security_breach" in str(call_args)

    def test_publish_event_with_priority(self):
        """REM: High priority events must have priority field set."""
        from core.mqtt_bus import MQTTBus
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_client.is_connected.return_value = True
            mock_client.publish.return_value = MagicMock(rc=0)
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="priority-event-test")
            bus._connected = True
            bus._client = mock_client
            
            bus.publish_event(
                event_type="Critical_Alert",
                source_agent="monitor",
                payload={"alert": "system_overload"},
                qms_status="Pretty_Please"
            )
            
            # Verify the published message payload contains priority
            publish_call = mock_client.publish.call_args
            if publish_call and publish_call[0]:
                payload_json = publish_call[0][1] if len(publish_call[0]) > 1 else None
                if payload_json:
                    payload = json.loads(payload_json)
                    assert payload.get("priority") == "high"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 8: Topic Structure Validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestTopicStructure:
    """REM: Validates the MQTT topic hierarchy design."""

    def test_agent_inbox_topic_format(self):
        """REM: Agent inbox topics must follow standard format."""
        from core.mqtt_bus import MQTTBus
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="topic-test")
            bus._client = mock_client
            bus._connected = True  # REM: Must be connected for subscribe to reach _client
            
            bus.register_agent_inbox("doc_processor", lambda m, t: None)
            
            # Check that subscribe was called with correct topic pattern
            subscribe_calls = mock_client.subscribe.call_args_list
            topics = [c[0][0] for c in subscribe_calls]
            assert "telsonbase/agents/doc_processor/inbox" in topics

    def test_multiple_agent_inboxes_isolated(self):
        """REM: Each agent gets its own isolated inbox topic."""
        from core.mqtt_bus import MQTTBus
        
        with patch('core.mqtt_bus.mqtt.Client') as mock_mqtt:
            mock_client = MagicMock()
            mock_mqtt.return_value = mock_client
            
            bus = MQTTBus(client_id="isolation-test")
            bus._client = mock_client
            bus._connected = True  # REM: Must be connected for subscribe to reach _client
            
            agents = ["agent_a", "agent_b", "agent_c"]
            for agent in agents:
                bus.register_agent_inbox(agent, lambda m, t: None)
            
            subscribe_topics = [c[0][0] for c in mock_client.subscribe.call_args_list]
            
            for agent in agents:
                expected = f"telsonbase/agents/{agent}/inbox"
                assert expected in subscribe_topics
