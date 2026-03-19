# TB-PROOF-067 -- MQTT Bus Load and Stress Test Suite

**Sheet ID:** TB-PROOF-067
**Claim Source:** tests/test_mqtt_stress.py
**Status:** VERIFIED
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "MQTT agent communication bus handles throughput, concurrency, routing accuracy, handler errors, and QMS chain integration under load."

This sheet proves the **MQTT Bus Load and Stress Test Suite**: 26 tests across 8 classes exercising the MQTT bus under volume and concurrency: message throughput, topic routing accuracy, concurrent publishing from multiple threads, handler error isolation, reconnection subscription restoration, and QMS chain integration.

*Note: This suite is excluded from the main 720-test count and run separately. It requires no live broker - all tests use mocked paho-mqtt.*

## Verdict

VERIFIED -- All 26 stress tests pass. The MQTT bus correctly handles 1,000-message serialize/deserialize cycles without exception. Topic routing delivers messages to the correct handlers and ignores unmatched topics without crashing. Concurrent publishing from multiple threads produces no race conditions. Handler exceptions and timeouts are isolated - they do not crash the bus. Subscriptions are restored after reconnection. QMS command suffixes (::_Please::, ::_Thank_You::, ::_Pretty_Please::, ::_Excuse_Me::) are preserved through publish/receive cycles. Agent inbox topics are isolated per agent.

## Test Classes

| Class | Tests | Proves |
|---|---|---|
| `TestMessageThroughput` | 4 | 1,000-message serialize/deserialize, rapid publish no exceptions, large payload, nested payload depth |
| `TestTopicRouting` | 4 | Agent inbox routing, broadcast reaches all handlers, event-type routing, unmatched topic no crash |
| `TestConcurrentPublishing` | 2 | Concurrent publish from multiple threads, concurrent subscribe and publish |
| `TestHandlerResilience` | 4 | Handler exception isolation, handler timeout isolation, malformed JSON no crash, empty payload no crash |
| `TestReconnectionBehavior` | 2 | Subscriptions restored on reconnect, graceful publish failure when disconnected |
| `TestQMSChainIntegration` | 6 | QMS command suffixes preserved: _Please, _Thank_You, _Pretty_Please, _Excuse_Me; QMS chain field preserved; message ID uniqueness across 1,000 |
| `TestPublishEvent` | 2 | publish_event creates correct topic, publish_event with priority |
| `TestTopicStructure` | 2 | Agent inbox topic format, multiple agent inboxes isolated |

## Source Files Tested

- `tests/test_mqtt_stress.py`
- `core/mqtt_bus.py` -- MQTTBus, publish_event, topic structure
- `core/qms.py` -- QMS chain field preservation through publish/receive

## Verification Command

```bash
docker compose exec mcp_server python -m pytest tests/test_mqtt_stress.py -v --tb=short
```

## Expected Result

```
26 passed
```

---

*Sheet TB-PROOF-067 | ClawCoat v11.0.2 | March 19, 2026*
