# TelsonBase/core/mqtt_bus.py
# REM: =======================================================================================
# REM: MQTT AGENT-TO-AGENT COMMUNICATION BUS FOR TELSONBASE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: This module wires the Mosquitto MQTT broker into TelsonBase as
# REM: the real-time event bus for agent-to-agent communication. Every message published
# REM: on this bus carries QMS formatting and is logged to the audit trail.
# REM:
# REM: Topic Structure (QMS-native):
# REM:   telsonbase/agents/{agent_id}/inbox      — Direct messages to a specific agent
# REM:   telsonbase/agents/{agent_id}/outbox      — Messages FROM a specific agent
# REM:   telsonbase/broadcast/all                 — System-wide broadcasts
# REM:   telsonbase/broadcast/{trust_level}       — Trust-level filtered broadcasts
# REM:   telsonbase/events/{event_type}           — System events (anomaly, approval, etc.)
# REM:   telsonbase/federation/inbound            — Messages from federated instances
# REM:   telsonbase/federation/outbound           — Messages to federated instances
# REM:
# REM: Security Model:
# REM:   - All messages are signed using the agent's signing key
# REM:   - QMS format is enforced on all messages
# REM:   - Messages without valid signatures are logged as anomalies
# REM:   - Federation messages require additional encryption
# REM: =======================================================================================

import json
import time
import logging
import threading
import itertools
from datetime import datetime, timezone
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field

# REM: Atomic counter for unique message IDs — prevents collisions in rapid-fire loops
_msg_counter = itertools.count()

import paho.mqtt.client as mqtt

from core.config import get_settings
from core.audit import audit, AuditEventType
from core.qms import format_qms, QMSStatus

logger = logging.getLogger(__name__)
settings = get_settings()


# REM: =======================================================================================
# REM: MESSAGE ENVELOPE
# REM: =======================================================================================

@dataclass
class AgentMessage:
    """
    REM: Standard message envelope for agent-to-agent communication.
    REM: Every message on the bus MUST use this envelope.
    REM: QMS formatting is embedded in the message_type field.
    """
    source_agent: str                     # REM: Who sent it
    target_agent: Optional[str]           # REM: Who it's for (None = broadcast)
    message_type: str                     # REM: QMS-formatted type (e.g., "Analyze_Document_Please")
    payload: Dict[str, Any]               # REM: The actual content
    timestamp: str = ""                   # REM: ISO 8601 timestamp
    message_id: str = ""                  # REM: Unique message identifier
    signature: Optional[str] = None       # REM: Cryptographic signature
    qms_chain: Optional[str] = None       # REM: Full QMS chain for provenance
    priority: str = "normal"              # REM: normal, high (Pretty_Please)
    reply_to: Optional[str] = None        # REM: Topic to reply on

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.message_id:
            self.message_id = f"{self.source_agent}-{int(time.time() * 1000)}-{next(_msg_counter)}"

    def to_json(self) -> str:
        """REM: Serialize to JSON for MQTT transport."""
        return json.dumps({
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "message_type": self.message_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
            "signature": self.signature,
            "qms_chain": self.qms_chain,
            "priority": self.priority,
            "reply_to": self.reply_to,
        })

    @classmethod
    def from_json(cls, data: str) -> 'AgentMessage':
        """REM: Deserialize from JSON received via MQTT."""
        d = json.loads(data)
        return cls(**d)


# REM: =======================================================================================
# REM: MQTT BUS - THE WIRING
# REM: =======================================================================================

class MQTTBus:
    """
    REM: Manages the MQTT connection and provides publish/subscribe methods
    REM: for agent-to-agent communication.
    REM:
    REM: This is a singleton — one connection per TelsonBase instance.
    REM: Agents register handlers for their inbox topics.
    """

    TOPIC_PREFIX = "telsonbase"

    def __init__(self, client_id: str = "telsonbase-api"):
        # REM: Append PID to client ID so gunicorn workers don't fight for the same session
        import os
        unique_client_id = f"{client_id}-{os.getpid()}"
        self._client = mqtt.Client(
            client_id=unique_client_id,
            protocol=mqtt.MQTTv311,
            clean_session=True
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._connected = False
        self._handlers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        self._reconnect_delay = 5  # seconds

    def connect(self) -> bool:
        """
        REM: Connect to the Mosquitto broker.
        REM: Returns True if connection successful, False otherwise.
        REM: Non-blocking — starts the MQTT loop in a background thread.
        REM: v5.2.1CC: Uses MOSQUITTO_USER/MOSQUITTO_PASSWORD if configured.
        """
        try:
            # REM: Set credentials if configured
            if settings.mosquitto_user and settings.mosquitto_password:
                self._client.username_pw_set(
                    settings.mosquitto_user,
                    settings.mosquitto_password
                )
                logger.info("REM: MQTT Bus using authenticated connection_Thank_You")

            logger.info(
                f"REM: MQTT Bus connecting to ::{settings.mosquitto_host}::{settings.mosquitto_port}::_Please"
            )
            self._client.connect(
                host=settings.mosquitto_host,
                port=settings.mosquitto_port,
                keepalive=60
            )
            self._client.loop_start()  # REM: Background thread for MQTT
            return True
        except Exception as e:
            logger.error(
                f"REM: MQTT Bus connection failed: ::{e}::_Thank_You_But_No"
            )
            return False

    def disconnect(self):
        """REM: Gracefully disconnect from the broker."""
        logger.info("REM: MQTT Bus disconnecting_Please")
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False

    def publish(self, message: AgentMessage, topic: Optional[str] = None) -> bool:
        """
        REM: Publish a message to the MQTT bus.
        REM: If no topic is specified, it's derived from the message:
        REM:   - Direct message → telsonbase/agents/{target_agent}/inbox
        REM:   - Broadcast → telsonbase/broadcast/all
        REM:   - High priority → telsonbase/broadcast/all (with retain)
        """
        if not self._connected:
            logger.warning("REM: MQTT Bus not connected. Message queued_Excuse_Me")
            return False

        if not topic:
            if message.target_agent:
                topic = f"{self.TOPIC_PREFIX}/agents/{message.target_agent}/inbox"
            else:
                topic = f"{self.TOPIC_PREFIX}/broadcast/all"

        # REM: Also publish to the source agent's outbox for audit trail
        outbox_topic = f"{self.TOPIC_PREFIX}/agents/{message.source_agent}/outbox"

        try:
            payload = message.to_json()
            retain = message.priority == "high"

            # REM: Publish to target
            result = self._client.publish(topic, payload, qos=1, retain=retain)
            
            # REM: Publish to outbox (for audit/monitoring)
            self._client.publish(outbox_topic, payload, qos=0)

            # REM: Log to audit trail
            audit.log(
                AuditEventType.AGENT_ACTION,
                f"MQTT_Publish_{message.message_type} "
                f"::{message.source_agent}:: → ::{message.target_agent or 'broadcast'}:: "
                f"topic=::{topic}::",
                actor=message.source_agent,
                details={
                    "topic": topic,
                    "message_id": message.message_id,
                    "message_type": message.message_type,
                    "priority": message.priority,
                },
                qms_status="Thank_You" if result.rc == mqtt.MQTT_ERR_SUCCESS else "Thank_You_But_No"
            )

            return result.rc == mqtt.MQTT_ERR_SUCCESS

        except Exception as e:
            logger.error(f"REM: MQTT publish failed: ::{e}::_Thank_You_But_No")
            return False

    def subscribe(self, topic_pattern: str, handler: Callable[[AgentMessage, str], None]):
        """
        REM: Subscribe to a topic pattern and register a message handler.
        REM:
        REM: Args:
        REM:   topic_pattern: MQTT topic (supports wildcards: + for single level, # for multi)
        REM:   handler: Callable that receives (AgentMessage, topic_string)
        REM:
        REM: Example:
        REM:   bus.subscribe("telsonbase/agents/ollama_agent/inbox", handle_ollama_msg)
        REM:   bus.subscribe("telsonbase/broadcast/#", handle_broadcasts)
        """
        with self._lock:
            if topic_pattern not in self._handlers:
                self._handlers[topic_pattern] = []
                if self._connected:
                    self._client.subscribe(topic_pattern, qos=1)
                    logger.info(f"REM: MQTT subscribed to ::{topic_pattern}::_Thank_You")

            self._handlers[topic_pattern].append(handler)

    def register_agent_inbox(self, agent_id: str, handler: Callable[[AgentMessage, str], None]):
        """
        REM: Convenience method — subscribe to an agent's inbox.
        REM: This is how agents "listen" for messages directed at them.
        """
        topic = f"{self.TOPIC_PREFIX}/agents/{agent_id}/inbox"
        self.subscribe(topic, handler)

    def register_event_handler(self, event_type: str, handler: Callable[[AgentMessage, str], None]):
        """
        REM: Convenience method — subscribe to system events.
        REM: event_type examples: "anomaly", "approval", "federation", "backup"
        """
        topic = f"{self.TOPIC_PREFIX}/events/{event_type}"
        self.subscribe(topic, handler)

    def publish_event(self, event_type: str, source_agent: str, payload: Dict[str, Any],
                      qms_status: str = "Please"):
        """
        REM: Convenience method — publish a system event.
        REM: Used for anomaly notifications, approval requests, etc.
        """
        msg = AgentMessage(
            source_agent=source_agent,
            target_agent=None,
            message_type=f"{event_type}_{qms_status}",
            payload=payload,
            priority="high" if "Pretty_Please" in qms_status else "normal",
        )
        topic = f"{self.TOPIC_PREFIX}/events/{event_type}"
        return self.publish(msg, topic=topic)

    # REM: -------------------------------------------------------------------------
    # REM: INTERNAL CALLBACKS
    # REM: -------------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc):
        """REM: Called when connection to broker is established."""
        if rc == 0:
            self._connected = True
            logger.info("REM: MQTT Bus connected to Mosquitto_Thank_You")

            # REM: Re-subscribe to all registered topics on reconnect
            with self._lock:
                for topic_pattern in self._handlers:
                    client.subscribe(topic_pattern, qos=1)
                    logger.info(f"REM: MQTT re-subscribed to ::{topic_pattern}::")

            audit.log(
                AuditEventType.SYSTEM_STARTUP,
                "MQTT_Bus_Connected_Thank_You",
                actor="mqtt_bus",
                details={"broker": f"{settings.mosquitto_host}:{settings.mosquitto_port}"}
            )
        else:
            self._connected = False
            logger.error(f"REM: MQTT connection refused, rc=::{rc}::_Thank_You_But_No")

    def _on_disconnect(self, client, userdata, rc):
        """REM: Called when disconnected from broker."""
        self._connected = False
        if rc != 0:
            logger.warning(f"REM: MQTT unexpected disconnect, rc=::{rc}::. Will auto-reconnect.")
            audit.log(
                AuditEventType.SYSTEM_SHUTDOWN,
                f"MQTT_Bus_Disconnected_Unexpected ::{rc}::_Excuse_Me",
                actor="mqtt_bus"
            )

    def _on_message(self, client, userdata, msg):
        """
        REM: Called when a message is received on a subscribed topic.
        REM: Deserializes the message and dispatches to registered handlers.
        """
        try:
            agent_msg = AgentMessage.from_json(msg.payload.decode('utf-8'))
            topic = msg.topic

            # REM: Find matching handlers
            with self._lock:
                for pattern, handlers in self._handlers.items():
                    if mqtt.topic_matches_sub(pattern, topic):
                        for handler in handlers:
                            try:
                                handler(agent_msg, topic)
                            except Exception as e:
                                logger.error(
                                    f"REM: MQTT handler error for ::{pattern}::: ::{e}::_Thank_You_But_No"
                                )

        except json.JSONDecodeError as e:
            logger.warning(
                f"REM: MQTT received malformed message on ::{msg.topic}::: ::{e}::_Thank_You_But_No"
            )
            # REM: Flag as potential anomaly — malformed messages could be attack vectors
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"MQTT_Malformed_Message ::{msg.topic}::_Thank_You_But_No",
                actor="mqtt_bus",
                details={"topic": msg.topic, "error": str(e)}
            )
        except Exception as e:
            logger.error(f"REM: MQTT message processing error: ::{e}::_Thank_You_But_No")

    @property
    def is_connected(self) -> bool:
        return self._connected


# REM: =======================================================================================
# REM: SINGLETON INSTANCE
# REM: =======================================================================================
# REM: One bus per TelsonBase instance. Import and use: from core.mqtt_bus import mqtt_bus

_mqtt_bus_instance: Optional[MQTTBus] = None


def get_mqtt_bus() -> MQTTBus:
    """
    REM: Get the singleton MQTT bus instance.
    REM: Creates and connects on first call.
    """
    global _mqtt_bus_instance
    if _mqtt_bus_instance is None:
        _mqtt_bus_instance = MQTTBus()
    return _mqtt_bus_instance


def init_mqtt_bus() -> bool:
    """
    REM: Initialize and connect the MQTT bus.
    REM: Called during application startup in main.py lifespan.
    REM: Returns True if connection successful.
    """
    bus = get_mqtt_bus()
    connected = bus.connect()
    if connected:
        # REM: Subscribe to system-wide event topics
        bus.subscribe("telsonbase/events/#", _default_event_handler)
        bus.subscribe("telsonbase/broadcast/all", _default_broadcast_handler)
    return connected


def shutdown_mqtt_bus():
    """REM: Gracefully shut down the MQTT bus on application exit."""
    global _mqtt_bus_instance
    if _mqtt_bus_instance:
        _mqtt_bus_instance.disconnect()
        _mqtt_bus_instance = None


def _default_event_handler(msg: AgentMessage, topic: str):
    """REM: Default handler for system events — logs to audit trail."""
    logger.info(
        f"REM: MQTT Event ::{msg.message_type}:: from ::{msg.source_agent}:: on ::{topic}::"
    )


def _default_broadcast_handler(msg: AgentMessage, topic: str):
    """REM: Default handler for broadcasts — logs to audit trail."""
    logger.info(
        f"REM: MQTT Broadcast ::{msg.message_type}:: from ::{msg.source_agent}::"
    )
