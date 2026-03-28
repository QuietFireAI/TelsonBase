# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# ClawFilters/api/auth_routes.py
# REM: =======================================================================================
# REM: USER AUTHENTICATION API ENDPOINTS FOR TELSONBASE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v7.0.0CC: New feature — Per-user authentication REST API
#
# REM: Mission Statement: Expose user registration, login, MFA verification, password
# REM: management, and profile endpoints as REST API. These endpoints are for human
# REM: operators. The existing /v1/auth/token endpoint in main.py remains for
# REM: machine-to-machine API key exchange.
#
# REM: Endpoints:
# REM:   POST /v1/auth/register       — Register new user
# REM:   POST /v1/auth/login          — Login with username/password
# REM:   POST /v1/auth/login/mfa      — Complete MFA step after login
# REM:   POST /v1/auth/change-password — Change own password (authenticated)
# REM:   GET  /v1/auth/profile        — Get own profile (authenticated)
# REM:   POST /v1/auth/logout         — Logout (authenticated)
#
# REM: QMS Protocol:
# REM:   Success: "Thank_You"
# REM:   Failure: "Thank_You_But_No"
# REM: =======================================================================================

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from core.audit import AuditEventType, audit
from core.auth import (AuthResult, authenticate_request, create_access_token,
                       decode_token, require_permission, revoke_token)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["User Authentication"])


# REM: =======================================================================================
# REM: PYDANTIC MODELS
# REM: =======================================================================================

class RegisterRequest(BaseModel):
    """REM: Request body for user registration."""
    username: str = Field(..., min_length=3, max_length=64, description="Unique username")
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=12, description="Password (min 12 chars)")
    role: Optional[str] = Field(None, description="Initial role (viewer, operator, admin, security_officer, super_admin). First user always gets super_admin.")
    captcha_challenge_id: Optional[str] = Field(None, description="Solved CAPTCHA challenge ID — required for all registrations except the first user.")


class PublicCaptchaVerifyRequest(BaseModel):
    """REM: Request body for public CAPTCHA verification (no auth required)."""
    challenge_id: str = Field(..., description="Challenge ID from /captcha/generate")
    answer: str = Field(..., description="User's answer to the challenge")


class LoginRequest(BaseModel):
    """REM: Request body for user login."""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class MFALoginRequest(BaseModel):
    """REM: Request body for MFA completion after login."""
    pre_mfa_token: str = Field(..., description="Temporary pre-MFA token from login response")
    totp_code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code")


class ChangePasswordRequest(BaseModel):
    """REM: Request body for password change."""
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=12, description="New password (min 12 chars)")


# REM: =======================================================================================
# REM: REGISTRATION ENDPOINT
# REM: =======================================================================================

@router.post("/register")
async def register_user(request: RegisterRequest):
    """
    REM: Register a new human operator account.
    REM: QMS: User_Register_Please with ::username:: ::email::
    REM:
    REM: The first user registered automatically receives the super_admin role.
    REM: Subsequent users receive the viewer role by default.
    """
    try:
        from core.captcha import captcha_manager
        from core.email_sender import send_verification_email
        from core.email_verification import email_verification as ev
        from core.user_management import user_manager

        # REM: Detect first-user before registration (count==0 means first user)
        is_first_user = user_manager.is_first_user()

        # REM: Require solved CAPTCHA for all non-first-user registrations
        if not is_first_user:
            if not request.captcha_challenge_id or \
               not captcha_manager.consume_challenge(request.captcha_challenge_id):
                raise HTTPException(status_code=400, detail={
                    "qms_status": "Thank_You_But_No",
                    "error": "CAPTCHA not solved or expired. Please complete the challenge.",
                    "captcha_required": True,
                })

        # REM: Use requested role if provided; first user always gets super_admin regardless
        roles = [request.role] if request.role else None
        user_profile = user_manager.register_user(
            username=request.username,
            email=request.email,
            password=request.password,
            roles=roles,
        )

        user_id = user_profile["user_id"]

        if is_first_user:
            # REM: Auto-verify first user so they can log in immediately and configure SMTP
            ev._verified_emails[user_id] = request.email
            ev._save_verified_email(user_id, request.email)
            logger.info(
                f"REM: First user ::{request.username}:: auto-verified — "
                f"SMTP setup not required for initial login_Thank_You"
            )
        else:
            # REM: Create verification token and send email (non-blocking)
            token_rec = ev.create_verification(user_id=user_id, email=request.email)
            asyncio.create_task(
                send_verification_email(
                    request.email, request.username, token_rec.token, user_id
                )
            )

        logger.info(f"REM: User registered via API ::{request.username}::_Thank_You")

        return {
            "qms_status": "Thank_You",
            "user": user_profile,
            "email_verification_required": not is_first_user,
            "message": (
                "Account created. You may log in immediately."
                if is_first_user else
                "Account created. Please verify your email before logging in."
            ),
        }

    except ValueError as e:
        logger.warning(f"REM: Registration failed for ::{request.username}::: {e}_Thank_You_But_No")
        raise HTTPException(status_code=400, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"REM: Registration error: {e}_Thank_You_But_No")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": "Registration failed due to internal error",
        })


# REM: =======================================================================================
# REM: LOGIN ENDPOINT
# REM: =======================================================================================

@router.post("/login")
async def login_user(request: LoginRequest, http_request: Request):
    """
    REM: Authenticate with username/password and receive a JWT access token.
    REM: QMS: User_Login_Please with ::username::
    REM:
    REM: If the user has MFA enabled, returns mfa_required=True with a temporary
    REM: pre-MFA token. The client must then call POST /v1/auth/login/mfa to
    REM: complete authentication and receive the full JWT.
    """
    try:
        from core.mfa import mfa_manager
        from core.rbac import rbac_manager
        from core.user_management import user_manager

        # REM: Authenticate username/password
        user_dict = user_manager.authenticate_user(
            username=request.username,
            password=request.password,
        )

        if not user_dict:
            raise HTTPException(status_code=401, detail={
                "qms_status": "Thank_You_But_No",
                "error": "Invalid username or password",
            })

        user_id = user_dict["user_id"]

        # REM: Gate on email verification — unverified users cannot receive a JWT
        from core.email_verification import email_verification as ev
        if not ev.is_verified(user_id):
            raise HTTPException(status_code=403, detail={
                "qms_status": "Thank_You_But_No",
                "error": "Email address not verified. Check your inbox for a verification link.",
                "email_not_verified": True,
                "user_id": user_id,
            })

        user = rbac_manager.get_user(user_id)

        # REM: Check if MFA is required or enrolled
        mfa_required = mfa_manager.is_mfa_required(user)
        mfa_enrolled = mfa_manager.is_enrolled(user_id)

        if mfa_enrolled:
            # REM: Issue a short-lived pre-MFA token (5 minutes)
            pre_mfa_token = create_access_token(
                subject=f"pre_mfa:{user_id}",
                permissions=[],
                expires_delta=timedelta(minutes=5),
            )

            logger.info(
                f"REM: User ::{request.username}:: authenticated — MFA step required_Thank_You"
            )

            return {
                "qms_status": "Thank_You",
                "mfa_required": True,
                "pre_mfa_token": pre_mfa_token,
                "user": user_dict,
                "message": "Password verified. Complete MFA to receive access token.",
            }

        # REM: No MFA — issue full JWT and create session
        permissions = [p.value for p in user.get_all_permissions()]
        access_token = create_access_token(
            subject=user_id,
            permissions=permissions,
        )

        # REM: Create session via session_manager
        ip_address = http_request.client.host if http_request.client else None
        user_agent = http_request.headers.get("user-agent")

        from core.session_management import session_manager
        session = session_manager.create_session(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            role=user_dict.get("roles", ["viewer"])[0],
        )

        logger.info(f"REM: User ::{request.username}:: logged in successfully_Thank_You")

        return {
            "qms_status": "Thank_You",
            "mfa_required": False,
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_dict,
            "session_id": session.session_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"REM: Login error: {e}_Thank_You_But_No")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": "Login failed due to internal error",
        })


# REM: =======================================================================================
# REM: MFA LOGIN COMPLETION ENDPOINT
# REM: =======================================================================================

@router.post("/login/mfa")
async def login_mfa(request: MFALoginRequest, http_request: Request):
    """
    REM: Complete the MFA step after a successful password login.
    REM: QMS: User_MFA_Login_Please
    REM:
    REM: Validates the pre-MFA token issued by /login, then verifies the TOTP code.
    REM: On success, returns a full JWT access token with user permissions.
    """
    try:
        from core.mfa import mfa_manager
        from core.rbac import rbac_manager
        from core.session_management import session_manager

        # REM: Decode and validate the pre-MFA token
        token_data = decode_token(request.pre_mfa_token)
        if not token_data:
            raise HTTPException(status_code=401, detail={
                "qms_status": "Thank_You_But_No",
                "error": "Invalid or expired pre-MFA token",
            })

        # REM: Extract user_id from pre-MFA subject
        subject = token_data.sub
        if not subject.startswith("pre_mfa:"):
            raise HTTPException(status_code=401, detail={
                "qms_status": "Thank_You_But_No",
                "error": "Invalid pre-MFA token format",
            })

        user_id = subject[len("pre_mfa:"):]
        user = rbac_manager.get_user(user_id)
        if not user:
            raise HTTPException(status_code=401, detail={
                "qms_status": "Thank_You_But_No",
                "error": "User not found",
            })

        # REM: Verify TOTP code
        verified = mfa_manager.verify_mfa(user_id, request.totp_code)
        if not verified:
            logger.warning(
                f"REM: MFA verification failed for user ::{user.username}::_Thank_You_But_No"
            )
            raise HTTPException(status_code=401, detail={
                "qms_status": "Thank_You_But_No",
                "error": "Invalid TOTP code",
            })

        # REM: Revoke the pre-MFA token (one-time use)
        if token_data.jti:
            revoke_token(token_data.jti, token_data.exp, revoked_by="mfa_completion")

        # REM: Issue full JWT with permissions
        permissions = [p.value for p in user.get_all_permissions()]
        access_token = create_access_token(
            subject=user_id,
            permissions=permissions,
        )

        # REM: Create session with mfa_verified flag
        ip_address = http_request.client.host if http_request.client else None
        user_agent = http_request.headers.get("user-agent")

        session = session_manager.create_session(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            role=list(user.roles)[0].value if user.roles else "viewer",
        )
        # REM: L11 fix: use set_mfa_verified() which persists the flag to Redis
        session_manager.set_mfa_verified(session.session_id)

        logger.info(
            f"REM: User ::{user.username}:: completed MFA login successfully_Thank_You"
        )

        audit.log(
            AuditEventType.AUTH_SUCCESS,
            f"MFA login completed for user: {user.username}",
            actor=user.username,
            resource=user_id,
            details={"method": "password+mfa", "session_id": session.session_id},
            qms_status="Thank_You"
        )

        return {
            "qms_status": "Thank_You",
            "access_token": access_token,
            "token_type": "bearer",
            "user": user.to_dict(),
            "session_id": session.session_id,
            "mfa_verified": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"REM: MFA login error: {e}_Thank_You_But_No")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": "MFA login failed due to internal error",
        })


# REM: =======================================================================================
# REM: CHANGE PASSWORD ENDPOINT (AUTHENTICATED)
# REM: =======================================================================================

@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    auth: AuthResult = Depends(authenticate_request),
):
    """
    REM: Change the authenticated user's password.
    REM: QMS: User_ChangePassword_Please
    REM: Requires valid JWT auth and correct old password.
    """
    try:
        from core.user_management import user_manager

        # REM: The auth.actor is the user_id from JWT sub claim
        user_id = auth.actor

        success = user_manager.change_password(
            user_id=user_id,
            old_password=request.old_password,
            new_password=request.new_password,
        )

        if not success:
            raise HTTPException(status_code=400, detail={
                "qms_status": "Thank_You_But_No",
                "error": "Invalid current password",
            })

        logger.info(f"REM: Password changed for user ::{user_id}:: via API_Thank_You")

        return {
            "qms_status": "Thank_You",
            "message": "Password changed successfully",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"REM: Password change error: {e}_Thank_You_But_No")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": "Password change failed due to internal error",
        })


# REM: =======================================================================================
# REM: PROFILE ENDPOINT (AUTHENTICATED)
# REM: =======================================================================================

@router.get("/profile")
async def get_profile(auth: AuthResult = Depends(authenticate_request)):
    """
    REM: Get the authenticated user's profile.
    REM: QMS: User_Profile_Please
    REM: Returns user info, roles, permissions, MFA status, and session info.
    """
    try:
        from core.session_management import session_manager
        from core.user_management import user_manager

        user_id = auth.actor
        profile = user_manager.get_user_profile(user_id)

        if not profile:
            raise HTTPException(status_code=404, detail={
                "qms_status": "Thank_You_But_No",
                "error": "User profile not found",
            })

        # REM: Add active session info
        active_sessions = session_manager.get_active_sessions(user_id)
        profile["active_sessions"] = len(active_sessions)

        return {
            "qms_status": "Thank_You",
            "profile": profile,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"REM: Profile fetch error: {e}_Thank_You_But_No")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": "Failed to fetch profile",
        })


# REM: =======================================================================================
# REM: USER LIST ENDPOINT (ADMIN)
# REM: =======================================================================================

@router.get("/users")
async def list_users(auth: AuthResult = Depends(require_permission("admin:config"))):
    """
    REM: List all registered users with their roles and status.
    REM: QMS: User_List_Please
    """
    try:
        from core.email_verification import email_verification as ev
        from core.mfa import mfa_manager
        from core.rbac import rbac_manager

        users = rbac_manager.list_users()
        result = []
        for u in users:
            uid = u.get("user_id", "")
            try:
                mfa_status = mfa_manager.get_mfa_status(user_id=uid)
                u["mfa_enabled"] = mfa_status.get("enrolled", False)
            except Exception:
                u["mfa_enabled"] = False
            try:
                u["email_verified"] = ev.is_verified(uid)
            except Exception:
                u["email_verified"] = False
            result.append(u)

        return {
            "qms_status": "Thank_You",
            "users": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e),
        })


# REM: =======================================================================================
# REM: LOGOUT ENDPOINT (AUTHENTICATED)
# REM: =======================================================================================

@router.post("/logout")
async def logout(
    auth: AuthResult = Depends(authenticate_request),
    http_request: Request = None,
):
    """
    REM: Logout the authenticated user.
    REM: QMS: User_Logout_Please
    REM: Revokes the JWT token and terminates all active sessions for the user.
    """
    try:
        from fastapi.security import HTTPAuthorizationCredentials

        from core.session_management import session_manager

        user_id = auth.actor

        # REM: Revoke the JWT token if we can extract it
        auth_header = http_request.headers.get("authorization", "") if http_request else ""
        if auth_header.startswith("Bearer "):
            token_str = auth_header[7:]
            token_data = decode_token(token_str)
            if token_data and token_data.jti:
                revoke_token(token_data.jti, token_data.exp, revoked_by=user_id)

        # REM: Terminate all sessions for this user
        terminated = session_manager.terminate_all_user_sessions(
            user_id=user_id,
            reason="user_logout",
        )

        logger.info(
            f"REM: User ::{user_id}:: logged out — "
            f"{terminated} session(s) terminated_Thank_You"
        )

        audit.log(
            AuditEventType.AUTH_SUCCESS,
            f"User logout: {user_id}",
            actor=user_id,
            details={"sessions_terminated": terminated},
            qms_status="Thank_You"
        )

        return {
            "qms_status": "Thank_You",
            "message": "Logged out successfully",
            "sessions_terminated": terminated,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"REM: Logout error: {e}_Thank_You_But_No")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": "Logout failed due to internal error",
        })


# REM: =======================================================================================
# REM: PUBLIC CAPTCHA ENDPOINTS — No authentication required (used before login/registration)
# REM: =======================================================================================

@router.post("/captcha/generate", tags=["User Authentication"])
async def public_captcha_generate():
    """
    REM: Generate a self-hosted CAPTCHA challenge for registration forms.
    REM: No authentication required — this endpoint is intentionally public.
    REM: Returns challenge_id and question only; the answer is never exposed.
    """
    try:
        from core.captcha import captcha_manager
        ch = captcha_manager.generate_challenge()
        return {
            "qms_status": "Thank_You",
            "challenge_id": ch.challenge_id,
            "question": ch.question,
        }
    except Exception as e:
        logger.error(f"REM: CAPTCHA generate error: {e}_Thank_You_But_No")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": "Failed to generate CAPTCHA challenge",
        })


@router.post("/captcha/verify", tags=["User Authentication"])
async def public_captcha_verify(request: PublicCaptchaVerifyRequest):
    """
    REM: Verify a CAPTCHA challenge answer.
    REM: No authentication required — call this before submitting registration.
    REM: On success the challenge is marked solved; pass challenge_id in the register body.
    """
    try:
        from core.captcha import captcha_manager
        solved = captcha_manager.verify_challenge(
            challenge_id=request.challenge_id,
            user_answer=request.answer,
        )
        return {
            "qms_status": "Thank_You" if solved else "Thank_You_But_No",
            "solved": solved,
        }
    except Exception as e:
        logger.error(f"REM: CAPTCHA verify error: {e}_Thank_You_But_No")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": "Failed to verify CAPTCHA",
        })


# REM: =======================================================================================
# REM: EMAIL VERIFICATION LINK ENDPOINT
# REM: =======================================================================================

@router.get("/verify-email", response_class=HTMLResponse, tags=["User Authentication"])
async def verify_email_link(user_id: str, token: str):
    """
    REM: Handle email verification link clicks.
    REM: GET /v1/auth/verify-email?user_id=...&token=...
    REM: This URL is embedded in the verification email sent to new users.
    """
    try:
        from core.email_verification import email_verification as ev
        ok = ev.verify_email(user_id=user_id, token=token)
        if ok:
            return HTMLResponse(content="""
<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Email Verified</title>
<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0;}
.box{background:#1e293b;border:1px solid #22d3ee44;border-radius:12px;padding:40px 48px;text-align:center;max-width:400px;}
h2{color:#22d3ee;margin-top:0;}a{color:#22d3ee;}</style></head>
<body><div class="box">
<h2>&#10003; Email Verified</h2>
<p>Your TelsonBase account is now active.</p>
<p><a href="/dashboard">Go to Dashboard</a></p>
</div></body></html>
""", status_code=200)
        else:
            return HTMLResponse(content="""
<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Verification Failed</title>
<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0;}
.box{background:#1e293b;border:1px solid #f8717144;border-radius:12px;padding:40px 48px;text-align:center;max-width:400px;}
h2{color:#f87171;margin-top:0;}</style></head>
<body><div class="box">
<h2>&#10007; Link Invalid or Expired</h2>
<p>This verification link has expired or already been used.</p>
<p>Ask an administrator to resend a verification link from the Users tab.</p>
</div></body></html>
""", status_code=400)
    except Exception as e:
        logger.error(f"REM: Email verify link error: {e}_Thank_You_But_No")
        return HTMLResponse(content="<h2>Verification error. Please contact your administrator.</h2>",
                            status_code=500)
