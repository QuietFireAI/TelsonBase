# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: MIT
# TelsonBase/core/telegram_gateway.py
# REM: =======================================================================================
# REM: TELEGRAM GATEWAY — REMOTE OPERATOR COMMUNICATION
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: March 21, 2026
# REM:
# REM: Mission Statement: Bring governance decisions to the operator wherever they are.
# REM: HITL approval requests fire to a Telegram chat with inline Approve/Reject buttons.
# REM: The operator taps. The gate resolves. No web UI required.
# REM:
# REM: Features:
# REM:   - HITL approval requests → Telegram message with inline Approve/Reject buttons
# REM:   - Governance alerts (blocked calls, kill-switch events) → notification messages
# REM:   - /kill <agent_id> — suspend an agent from Telegram
# REM:   - /pending — list pending approval requests
# REM:   - /status — live system summary
# REM:   - Polling mode (default) or webhook mode (TELEGRAM_WEBHOOK_URL set)
# REM:
# REM: v11.1.0CC: Initial implementation
# REM: =======================================================================================

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# REM: Telegram Bot API base
_TG_API = "https://api.telegram.org/bot{token}/{method}"

# REM: Priority icons for HITL messages
_PRIORITY_ICON = {
    "urgent": "🚨",
    "high": "⚠️",
    "normal": "📋",
    "low": "📌",
}

# REM: Standardized tool grant durations (item 2 on sprint list)
GRANT_DURATIONS_HOURS = {
    "24h": 24,
    "72h": 72,
    "7d": 168,
}


class TelegramGateway:
    """
    REM: Operator communication gateway via Telegram Bot API.
    REM: Registers as a notification callback on the ApprovalGate.
    REM: Runs a polling loop in a daemon thread when webhook mode is not configured.
    """

    def __init__(self):
        self._token: str = ""
        self._chat_id: str = ""
        self._webhook_url: str = ""
        self._enabled: bool = False
        self._poll_thread: Optional[threading.Thread] = None
        self._polling: bool = False
        self._last_update_id: int = 0
        self._webhook_secret: str = ""

    # ------------------------------------------------------------------
    # REM: Configuration
    # ------------------------------------------------------------------

    def configure(self, token: str, chat_id: str, webhook_url: str = "", webhook_secret: str = "") -> bool:
        """REM: Configure and validate the gateway. Returns True if ready."""
        if not token or not chat_id:
            logger.warning("REM: Telegram gateway not configured — TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required")
            return False
        self._token = token
        self._chat_id = str(chat_id)
        self._webhook_url = webhook_url
        self._webhook_secret = str(webhook_secret or "")
        self._enabled = True
        logger.info(f"REM: Telegram gateway configured — chat_id ::{self._chat_id}::_Thank_You")
        return True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def verify_webhook_secret(self, header_value: str) -> bool:
        """REM: Constant-time check of Telegram's X-Telegram-Bot-Api-Secret-Token header.
        REM: If a secret is configured, inbound webhooks MUST present it. Fails closed."""
        import hmac
        if not self._webhook_secret:
            # REM: No secret configured — fail CLOSED unless explicitly dev/test.
            from core.config import is_strict_env
            if is_strict_env():
                logger.error("REM: Telegram webhook secret not set in production — rejecting inbound update")
                return False
            return True
        return hmac.compare_digest(str(header_value or ""), self._webhook_secret)

    def _is_authorized_sender(self, chat_id) -> bool:
        """REM: Inbound updates are only honored from the configured admin chat.
        REM: A forged callback_query from any other chat is rejected before it can
        REM: approve/reject a HITL gate."""
        return self._chat_id != "" and str(chat_id) == str(self._chat_id)

    def _api_url(self, method: str) -> str:
        return _TG_API.format(token=self._token, method=method)

    # ------------------------------------------------------------------
    # REM: Sending messages
    # ------------------------------------------------------------------

    def send_notification(self, text: str) -> bool:
        """REM: Send a plain text notification to the configured chat."""
        if not self._enabled:
            return False
        try:
            resp = httpx.post(
                self._api_url("sendMessage"),
                json={"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"REM: Telegram sendMessage failed: {e}")
            return False

    def send_hitl_request(self, request: Any) -> Optional[int]:
        """
        REM: Send a HITL approval request with Approve/Reject inline buttons.
        REM: Returns the Telegram message_id so we can edit it after decision.
        """
        if not self._enabled:
            return None

        priority = getattr(request.priority, "value", str(request.priority))
        icon = _PRIORITY_ICON.get(priority, "📋")
        expires_str = ""
        if request.expires_at:
            expires_str = f"\n⏱ Expires: {request.expires_at.strftime('%H:%M UTC %d %b')}"

        risk_str = ""
        if request.risk_factors:
            risk_str = f"\n⚠️ Risk: {', '.join(request.risk_factors)}"

        text = (
            f"{icon} <b>HITL Gate — {priority.upper()}</b>\n"
            f"ID: <code>{request.request_id}</code>\n"
            f"Agent: <code>{request.agent_id}</code>\n"
            f"Action: <code>{request.action}</code>\n"
            f"{request.description}"
            f"{risk_str}"
            f"{expires_str}"
        )

        keyboard = {
            "inline_keyboard": [[
                {"text": "✅ Approve", "callback_data": f"approve:{request.request_id}"},
                {"text": "❌ Reject",  "callback_data": f"reject:{request.request_id}"},
            ]]
        }

        try:
            resp = httpx.post(
                self._api_url("sendMessage"),
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "reply_markup": keyboard,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                msg_id = resp.json().get("result", {}).get("message_id")
                logger.info(f"REM: Telegram HITL request sent for ::{request.request_id}:: msg_id={msg_id}_Thank_You")
                return msg_id
        except Exception as e:
            logger.error(f"REM: Telegram HITL send failed for ::{request.request_id}::: {e}")
        return None

    def edit_hitl_resolved(self, message_id: int, request_id: str, decision: str, decided_by: str):
        """REM: Edit the original HITL message to show it was resolved."""
        if not self._enabled or not message_id:
            return
        icon = "✅" if decision == "approved" else "❌"
        text = (
            f"{icon} <b>{decision.upper()}</b>\n"
            f"Request: <code>{request_id}</code>\n"
            f"Decided by: {decided_by}"
        )
        try:
            httpx.post(
                self._api_url("editMessageText"),
                json={
                    "chat_id": self._chat_id,
                    "message_id": message_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"REM: Telegram editMessage failed: {e}")

    # ------------------------------------------------------------------
    # REM: Approval gate callback (registered via register_notification_callback)
    # ------------------------------------------------------------------

    def as_approval_callback(self, event: str, request: Any):
        """
        REM: Called by ApprovalGate on new_request events.
        REM: Register with: approval_gate.register_notification_callback(telegram.as_approval_callback)
        """
        if event == "new_request":
            msg_id = self.send_hitl_request(request)
            # REM: Store message_id on the request object so we can edit it later
            if msg_id:
                request._telegram_message_id = msg_id

    # ------------------------------------------------------------------
    # REM: Incoming update handling
    # ------------------------------------------------------------------

    def handle_update(self, update: Dict) -> None:
        """REM: Process a single Telegram update (from webhook or polling)."""
        # REM: SECURITY — only honor updates from the configured admin chat.
        # REM: Approve/reject taps drive the HITL gate; an unauthenticated sender
        # REM: must never reach approval_gate. Fails closed.
        cb = update.get("callback_query", {})
        msg = update.get("message", {})
        origin_chat = (
            cb.get("message", {}).get("chat", {}).get("id")
            if cb else msg.get("chat", {}).get("id")
        )
        if not self._is_authorized_sender(origin_chat):
            logger.warning(f"REM: Telegram update from unauthorized chat ::{origin_chat}:: rejected")
            return

        # REM: Button tap (callback_query)
        if "callback_query" in update:
            self._handle_callback_query(update["callback_query"])
            return

        # REM: Text command
        text = msg.get("text", "").strip()
        if text.startswith("/"):
            self._handle_command(text, msg)

    def _handle_callback_query(self, cq: Dict) -> None:
        """REM: Handle Approve/Reject button taps."""
        from core.approval import approval_gate

        cq_id = cq.get("id")
        data = cq.get("data", "")
        from_user = cq.get("from", {})
        username = from_user.get("username") or str(from_user.get("id", "unknown"))
        message = cq.get("message", {})
        message_id = message.get("message_id")

        # REM: Acknowledge the tap immediately (removes Telegram spinner)
        self._answer_callback_query(cq_id)

        if ":" not in data:
            return

        action, request_id = data.split(":", 1)

        if action == "approve":
            success = approval_gate.approve(request_id, decided_by=f"telegram:{username}")
            decision = "approved" if success else "already_resolved"
        elif action == "reject":
            success = approval_gate.reject(request_id, decided_by=f"telegram:{username}")
            decision = "rejected" if success else "already_resolved"
        else:
            return

        logger.info(f"REM: Telegram {action} for ::{request_id}:: by ::{username}::_Thank_You")
        self.edit_hitl_resolved(message_id, request_id, decision, f"telegram:{username}")

    def _handle_command(self, text: str, message: Dict) -> None:
        """REM: Handle operator slash commands from Telegram."""
        parts = text.split()
        cmd = parts[0].lower().split("@")[0]  # strip @botname suffix

        if cmd == "/kill":
            if len(parts) < 2:
                self.send_notification("Usage: /kill &lt;agent_id&gt;")
                return
            agent_id = parts[1]
            try:
                from core.openclaw import openclaw_manager
                from_user = message.get("from", {})
                operator = message.get("from", {}).get("username") or str(from_user.get("id", "telegram"))
                success = openclaw_manager.suspend_instance(
                    agent_id,
                    suspended_by=f"telegram:{operator}",
                    reason="Kill switch via Telegram",
                )
                if success:
                    self.send_notification(f"🛑 Kill switch activated — agent <code>{agent_id}</code> suspended.")
                    logger.info(f"REM: Kill switch via Telegram — agent ::{agent_id}::_Thank_You")
                else:
                    self.send_notification(f"❌ Agent <code>{agent_id}</code> not found.")
            except Exception as e:
                self.send_notification(f"❌ Kill switch failed: {e}")

        elif cmd == "/pending":
            try:
                from core.approval import approval_gate
                pending = approval_gate.get_pending_requests()
                if not pending:
                    self.send_notification("No pending approvals.")
                else:
                    lines = [f"📋 <b>{len(pending)} pending approval(s):</b>"]
                    for req in pending[:10]:
                        priority = getattr(req.priority, "value", str(req.priority))
                        lines.append(f"  • <code>{req.request_id}</code> — {req.agent_id} → {req.action} [{priority}]")
                    self.send_notification("\n".join(lines))
            except Exception as e:
                self.send_notification(f"❌ Error: {e}")

        elif cmd == "/status":
            try:
                from core.approval import approval_gate
                from core.openclaw import openclaw_manager
                pending_count = len(approval_gate.get_pending_requests())
                instances = openclaw_manager.list_instances()
                active_count = len(instances)
                lines = [
                    "📊 <b>TelsonBase Status</b>",
                    f"  Pending HITL gates: {pending_count}",
                    f"  Active OpenClaw instances: {active_count}",
                ]
                if instances:
                    for inst in instances[:5]:
                        tier = getattr(inst, "trust_level", "?")
                        aid = getattr(inst, "instance_id", "?")[:16]
                        score = getattr(inst, "manners_score", 0.0)
                        name = getattr(inst, "name", aid)
                        lines.append(f"  • <code>{name}</code> [{tier}] score={score:.2f}")
                self.send_notification("\n".join(lines))
            except Exception as e:
                self.send_notification(f"❌ Error: {e}")

        elif cmd == "/help":
            self.send_notification(
                "🦞 <b>TelsonBase Telegram Commands</b>\n"
                "/pending — list pending approval requests\n"
                "/status — system summary\n"
                "/kill &lt;agent_id&gt; — suspend an agent immediately\n"
                "/help — this message"
            )

    def _answer_callback_query(self, cq_id: str) -> None:
        """REM: Acknowledge a Telegram callback query to clear the spinner."""
        try:
            httpx.post(
                self._api_url("answerCallbackQuery"),
                json={"callback_query_id": cq_id},
                timeout=5,
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # REM: Webhook registration
    # ------------------------------------------------------------------

    def register_webhook(self) -> bool:
        """REM: Register the webhook URL with Telegram."""
        if not self._enabled or not self._webhook_url:
            return False
        webhook_endpoint = f"{self._webhook_url.rstrip('/')}/v1/telegram/webhook"
        try:
            resp = httpx.post(
                self._api_url("setWebhook"),
                json={"url": webhook_endpoint},
                timeout=10,
            )
            ok = resp.status_code == 200 and resp.json().get("ok")
            if ok:
                logger.info(f"REM: Telegram webhook registered at ::{webhook_endpoint}::_Thank_You")
            else:
                logger.warning(f"REM: Telegram webhook registration failed: {resp.text}")
            return ok
        except Exception as e:
            logger.error(f"REM: Telegram webhook registration error: {e}")
            return False

    def delete_webhook(self) -> None:
        """REM: Remove webhook (used when switching to polling mode)."""
        if not self._enabled:
            return
        try:
            httpx.post(self._api_url("deleteWebhook"), timeout=5)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # REM: Long polling (runs in daemon thread when webhook not configured)
    # ------------------------------------------------------------------

    def start_polling(self) -> None:
        """REM: Start long-polling in a background daemon thread."""
        if not self._enabled or self._webhook_url:
            return  # webhook mode — polling not needed
        if self._polling:
            return
        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True, name="telegram-poll")
        self._poll_thread.start()
        logger.info("REM: Telegram long-polling started_Thank_You")

    def stop_polling(self) -> None:
        """REM: Signal the polling loop to stop."""
        self._polling = False
        logger.info("REM: Telegram polling stopped_Thank_You")

    def _poll_loop(self) -> None:
        """REM: Background polling loop — fetches updates from Telegram."""
        while self._polling:
            try:
                resp = httpx.post(
                    self._api_url("getUpdates"),
                    json={
                        "offset": self._last_update_id + 1,
                        "timeout": 20,
                        "allowed_updates": ["message", "callback_query"],
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for update in data.get("result", []):
                        uid = update.get("update_id", 0)
                        if uid > self._last_update_id:
                            self._last_update_id = uid
                        try:
                            self.handle_update(update)
                        except Exception as e:
                            logger.error(f"REM: Telegram update handler error: {e}")
            except httpx.TimeoutException:
                pass  # Normal — long poll returned empty
            except Exception as e:
                logger.warning(f"REM: Telegram polling error: {e}")
                time.sleep(5)  # Back off on unexpected errors

    # ------------------------------------------------------------------
    # REM: Startup
    # ------------------------------------------------------------------

    def startup(self) -> None:
        """REM: Called from lifespan on startup."""
        if not self._enabled:
            return
        if self._webhook_url:
            self.register_webhook()
        else:
            self.delete_webhook()  # clear any stale webhook
            self.start_polling()
        self.send_notification("🦞 <b>TelsonBase online</b> — governance gateway active.")
        logger.info("REM: Telegram gateway started_Thank_You")

    def shutdown(self) -> None:
        """REM: Called from lifespan on shutdown."""
        if not self._enabled:
            return
        self.stop_polling()
        self.send_notification("🔴 <b>TelsonBase offline</b> — gateway shutting down.")


# REM: Global singleton
telegram_gateway = TelegramGateway()
