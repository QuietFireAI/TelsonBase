# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_core_email_sender_depth.py
# REM: Depth coverage for core/email_sender.py
# REM: All SMTP calls are mocked. No mail server required.

import asyncio
import importlib
import sys
import smtplib
from unittest.mock import MagicMock, patch, call

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# _send_sync — SMTP logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestSendSync:
    @pytest.fixture(autouse=True)
    def fresh_module(self):
        """Force a clean import of core.email_sender for each test.
        Prevents MagicMock contamination from other test files that patch the module."""
        sys.modules.pop("core.email_sender", None)
        yield
        sys.modules.pop("core.email_sender", None)

    def test_returns_false_when_smtp_host_empty(self):
        from core.email_sender import _send_sync
        import core.email_sender as es
        original = es.SMTP_HOST
        es.SMTP_HOST = ""
        try:
            result = _send_sync("user@example.com", "Subject", "<p>body</p>")
            assert result is False
        finally:
            es.SMTP_HOST = original

    def test_plain_smtp_sends_on_success(self):
        from core.email_sender import _send_sync
        import core.email_sender as es

        original_host = es.SMTP_HOST
        original_port = es.SMTP_PORT
        original_user = es.SMTP_USER
        original_password = es.SMTP_PASSWORD

        es.SMTP_HOST = "mailhog"
        es.SMTP_PORT = 1025
        es.SMTP_USER = ""
        es.SMTP_PASSWORD = ""

        mock_server = MagicMock()
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)

        try:
            with patch("smtplib.SMTP", return_value=mock_server):
                result = _send_sync("test@example.com", "Test Subject", "<p>Hello</p>")
            assert result is True
        finally:
            es.SMTP_HOST = original_host
            es.SMTP_PORT = original_port
            es.SMTP_USER = original_user
            es.SMTP_PASSWORD = original_password

    def test_smtp_with_credentials_calls_login(self):
        from core.email_sender import _send_sync
        import core.email_sender as es

        original_host = es.SMTP_HOST
        original_port = es.SMTP_PORT
        original_user = es.SMTP_USER
        original_password = es.SMTP_PASSWORD

        es.SMTP_HOST = "smtp.gmail.com"
        es.SMTP_PORT = 587
        es.SMTP_USER = "user@gmail.com"
        es.SMTP_PASSWORD = "secret"

        mock_server = MagicMock()
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)

        try:
            with patch("smtplib.SMTP", return_value=mock_server):
                _send_sync("to@example.com", "Subject", "<p>body</p>")
            mock_server.login.assert_called_once_with("user@gmail.com", "secret")
        finally:
            es.SMTP_HOST = original_host
            es.SMTP_PORT = original_port
            es.SMTP_USER = original_user
            es.SMTP_PASSWORD = original_password

    def test_smtp_starttls_attempted(self):
        from core.email_sender import _send_sync
        import core.email_sender as es

        original_host = es.SMTP_HOST
        original_port = es.SMTP_PORT
        original_user = es.SMTP_USER
        original_password = es.SMTP_PASSWORD

        es.SMTP_HOST = "smtp.example.com"
        es.SMTP_PORT = 587
        es.SMTP_USER = ""
        es.SMTP_PASSWORD = ""

        mock_server = MagicMock()
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)

        try:
            with patch("smtplib.SMTP", return_value=mock_server):
                _send_sync("to@example.com", "Subject", "<p>body</p>")
            mock_server.starttls.assert_called_once()
        finally:
            es.SMTP_HOST = original_host
            es.SMTP_PORT = original_port
            es.SMTP_USER = original_user
            es.SMTP_PASSWORD = original_password

    def test_starttls_exception_continues(self):
        # REM: MailHog doesn't support STARTTLS — should continue with plain
        from core.email_sender import _send_sync
        import core.email_sender as es

        original_host = es.SMTP_HOST
        original_port = es.SMTP_PORT
        original_user = es.SMTP_USER
        original_password = es.SMTP_PASSWORD

        es.SMTP_HOST = "mailhog"
        es.SMTP_PORT = 1025
        es.SMTP_USER = ""
        es.SMTP_PASSWORD = ""

        mock_server = MagicMock()
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)
        mock_server.starttls.side_effect = smtplib.SMTPException("not supported")

        try:
            with patch("smtplib.SMTP", return_value=mock_server):
                result = _send_sync("to@example.com", "Subj", "<p>body</p>")
            # Still succeeds despite STARTTLS failure
            assert result is True
        finally:
            es.SMTP_HOST = original_host
            es.SMTP_PORT = original_port
            es.SMTP_USER = original_user
            es.SMTP_PASSWORD = original_password

    def test_ssl_port_465_uses_smtp_ssl(self):
        from core.email_sender import _send_sync
        import core.email_sender as es

        original_host = es.SMTP_HOST
        original_port = es.SMTP_PORT
        original_user = es.SMTP_USER
        original_password = es.SMTP_PASSWORD

        es.SMTP_HOST = "smtp.ssl.example.com"
        es.SMTP_PORT = 465
        es.SMTP_USER = ""
        es.SMTP_PASSWORD = ""

        mock_server = MagicMock()
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)

        try:
            with patch("smtplib.SMTP_SSL", return_value=mock_server) as mock_ssl, \
                 patch("ssl.create_default_context", return_value=MagicMock()):
                result = _send_sync("to@example.com", "Subject", "<p>ssl</p>")
            mock_ssl.assert_called_once()
            assert result is True
        finally:
            es.SMTP_HOST = original_host
            es.SMTP_PORT = original_port
            es.SMTP_USER = original_user
            es.SMTP_PASSWORD = original_password

    def test_ssl_with_credentials_calls_login(self):
        from core.email_sender import _send_sync
        import core.email_sender as es

        original_host = es.SMTP_HOST
        original_port = es.SMTP_PORT
        original_user = es.SMTP_USER
        original_password = es.SMTP_PASSWORD

        es.SMTP_HOST = "smtp.ssl.example.com"
        es.SMTP_PORT = 465
        es.SMTP_USER = "ssl_user"
        es.SMTP_PASSWORD = "ssl_pass"

        mock_server = MagicMock()
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)

        try:
            with patch("smtplib.SMTP_SSL", return_value=mock_server), \
                 patch("ssl.create_default_context", return_value=MagicMock()):
                _send_sync("to@example.com", "Subject", "<p>body</p>")
            mock_server.login.assert_called_once_with("ssl_user", "ssl_pass")
        finally:
            es.SMTP_HOST = original_host
            es.SMTP_PORT = original_port
            es.SMTP_USER = original_user
            es.SMTP_PASSWORD = original_password

    def test_exception_returns_false(self):
        from core.email_sender import _send_sync
        import core.email_sender as es

        original_host = es.SMTP_HOST
        original_port = es.SMTP_PORT
        original_user = es.SMTP_USER
        original_password = es.SMTP_PASSWORD

        es.SMTP_HOST = "bad-host"
        es.SMTP_PORT = 587
        es.SMTP_USER = ""
        es.SMTP_PASSWORD = ""

        try:
            with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("refused")):
                result = _send_sync("to@example.com", "Subject", "<p>body</p>")
            assert result is False
        finally:
            es.SMTP_HOST = original_host
            es.SMTP_PORT = original_port
            es.SMTP_USER = original_user
            es.SMTP_PASSWORD = original_password

    def test_sendmail_called_with_correct_recipient(self):
        from core.email_sender import _send_sync
        import core.email_sender as es

        original_host = es.SMTP_HOST
        original_port = es.SMTP_PORT
        original_user = es.SMTP_USER
        original_password = es.SMTP_PASSWORD

        es.SMTP_HOST = "mailhog"
        es.SMTP_PORT = 1025
        es.SMTP_USER = ""
        es.SMTP_PASSWORD = ""

        mock_server = MagicMock()
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)

        try:
            with patch("smtplib.SMTP", return_value=mock_server):
                _send_sync("recipient@example.com", "Sub", "<p>body</p>")
            sendmail_calls = mock_server.sendmail.call_args_list
            assert len(sendmail_calls) == 1
            args = sendmail_calls[0][0]
            assert args[1] == "recipient@example.com"
        finally:
            es.SMTP_HOST = original_host
            es.SMTP_PORT = original_port
            es.SMTP_USER = original_user
            es.SMTP_PASSWORD = original_password


# ═══════════════════════════════════════════════════════════════════════════════
# send_verification_email — async wrapper
# ═══════════════════════════════════════════════════════════════════════════════

class TestSendVerificationEmail:
    @pytest.fixture(autouse=True)
    def fresh_module(self):
        sys.modules.pop("core.email_sender", None)
        yield
        sys.modules.pop("core.email_sender", None)

    def test_returns_true_on_success(self):
        from core.email_sender import send_verification_email

        with patch("core.email_sender._send_sync", return_value=True):
            result = asyncio.run(
                send_verification_email(
                    to_email="user@example.com",
                    username="Alice",
                    token="tok123",
                    user_id="usr-abc",
                )
            )
        assert result is True

    def test_returns_false_on_smtp_failure(self):
        from core.email_sender import send_verification_email

        with patch("core.email_sender._send_sync", return_value=False):
            result = asyncio.run(
                send_verification_email(
                    to_email="user@example.com",
                    username="Bob",
                    token="tok456",
                    user_id="usr-def",
                )
            )
        assert result is False

    def test_calls_send_sync_with_subject(self):
        from core.email_sender import send_verification_email

        captured = {}

        def capture_sync(to, subject, body):
            captured["to"] = to
            captured["subject"] = subject
            captured["body"] = body
            return True

        with patch("core.email_sender._send_sync", side_effect=capture_sync):
            asyncio.run(
                send_verification_email(
                    to_email="test@example.com",
                    username="Carol",
                    token="tok789",
                    user_id="usr-ghi",
                )
            )

        assert captured["to"] == "test@example.com"
        assert "verify" in captured["subject"].lower()

    def test_verification_url_contains_token(self):
        from core.email_sender import send_verification_email

        captured = {}

        def capture_sync(to, subject, body):
            captured["body"] = body
            return True

        with patch("core.email_sender._send_sync", side_effect=capture_sync):
            asyncio.run(
                send_verification_email(
                    to_email="test@example.com",
                    username="Dave",
                    token="my-secret-token",
                    user_id="usr-xyz",
                )
            )

        assert "my-secret-token" in captured["body"]

    def test_verification_url_contains_user_id(self):
        from core.email_sender import send_verification_email

        captured = {}

        def capture_sync(to, subject, body):
            captured["body"] = body
            return True

        with patch("core.email_sender._send_sync", side_effect=capture_sync):
            asyncio.run(
                send_verification_email(
                    to_email="test@example.com",
                    username="Eve",
                    token="tok",
                    user_id="usr-special-id-42",
                )
            )

        assert "usr-special-id-42" in captured["body"]

    def test_html_body_contains_username(self):
        from core.email_sender import send_verification_email

        captured = {}

        def capture_sync(to, subject, body):
            captured["body"] = body
            return True

        with patch("core.email_sender._send_sync", side_effect=capture_sync):
            asyncio.run(
                send_verification_email(
                    to_email="test@example.com",
                    username="SpecialUser99",
                    token="tok",
                    user_id="uid",
                )
            )

        assert "SpecialUser99" in captured["body"]

    def test_html_body_is_html(self):
        from core.email_sender import send_verification_email

        captured = {}

        def capture_sync(to, subject, body):
            captured["body"] = body
            return True

        with patch("core.email_sender._send_sync", side_effect=capture_sync):
            asyncio.run(
                send_verification_email(
                    to_email="test@example.com",
                    username="HTML Test",
                    token="tok",
                    user_id="uid",
                )
            )

        assert "<!DOCTYPE html>" in captured["body"] or "<html" in captured["body"]
