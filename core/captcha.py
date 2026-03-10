# TelsonBase/core/captcha.py
# REM: =======================================================================================
# REM: SERVER-SIDE CAPTCHA CHALLENGE MODULE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v6.3.0CC: Self-hosted CAPTCHA challenge system (no external service dependency)
#
# REM: Mission Statement: Defend against automated bot activity with server-generated
# REM: challenges. Math, text-reverse, and word-scramble challenges are generated locally
# REM: with no third-party CAPTCHA service required. Failed challenges are audit-logged
# REM: as potential bot activity.
#
# REM: Features:
# REM:   - Math-based challenges (addition, subtraction, multiplication)
# REM:   - Text-reverse challenges (type a word backwards)
# REM:   - Word-scramble challenges (unscramble a shuffled word)
# REM:   - Constant-time answer comparison (hmac.compare_digest)
# REM:   - 5-minute challenge expiry with max 3 attempts
# REM:   - Full audit trail for failed challenges (bot detection)
# REM: =======================================================================================

import hmac
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


# REM: Word list for text-based challenges
CHALLENGE_WORDS = [
    "security", "network", "firewall", "server", "database",
    "encrypt", "access", "system", "control", "monitor",
    "protect", "verify", "shield", "defend", "gateway",
    "digital", "platform", "cluster", "socket", "broker"
]


class ChallengeType(Enum):
    """REM: Types of CAPTCHA challenges available."""
    MATH = "math"
    TEXT_REVERSE = "text_reverse"
    WORD_SCRAMBLE = "word_scramble"


@dataclass
class CAPTCHAChallenge:
    """REM: Stores state for a single CAPTCHA challenge."""
    challenge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    challenge_type: ChallengeType = ChallengeType.MATH
    question: str = ""
    answer: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    attempts: int = 0
    solved: bool = False


class CAPTCHAManager:
    """
    REM: Manages server-side CAPTCHA challenge generation and verification.
    REM: In-memory storage with expiry and attempt tracking.
    """

    # REM: Maximum attempts per challenge before invalidation
    MAX_ATTEMPTS = 3

    # REM: Challenge expiry lifetime
    CHALLENGE_LIFETIME = timedelta(minutes=5)

    def __init__(self):
        self._challenges: Dict[str, CAPTCHAChallenge] = {}
        self._load_from_redis()

    def _load_from_redis(self) -> None:
        """REM: Load CAPTCHA challenges from Redis on startup. TTL-based, so most will have expired."""
        try:
            from core.persistence import security_store
            from core.secure_storage import secure_storage

            # REM: CAPTCHA uses TTL keys — cannot enumerate via hgetall.
            # REM: Challenges are short-lived (5 min), so we skip loading on init.
            # REM: This is intentionally a no-op; challenges are transient by design.
            pass
        except Exception as e:
            logger.warning(f"REM: Redis unavailable for CAPTCHA load: {e}_Thank_You_But_No")

    def _save_record(self, challenge_id: str) -> None:
        """REM: Write-through save of a single CAPTCHA challenge to Redis with TTL."""
        try:
            from core.persistence import security_store
            from core.secure_storage import secure_storage
            challenge = self._challenges.get(challenge_id)
            if not challenge:
                return
            data = {
                "challenge_id": challenge.challenge_id,
                "challenge_type": challenge.challenge_type.value,
                "question": challenge.question,
                "answer": challenge.answer,
                "created_at": challenge.created_at.isoformat(),
                "expires_at": challenge.expires_at.isoformat(),
                "attempts": challenge.attempts,
                "solved": challenge.solved,
            }
            # REM: Encrypt the answer field before storing
            try:
                data["answer"] = secure_storage.encrypt_string(data["answer"])
                data["_answer_encrypted"] = True
            except Exception:
                pass  # Store unencrypted if encryption unavailable
            security_store.store_record("captcha", challenge_id, data, ttl=300)
        except Exception as e:
            logger.warning(f"REM: Failed to save CAPTCHA to Redis for ::{challenge_id}::: {e}_Thank_You_But_No")

    def generate_challenge(self, challenge_type: Optional[ChallengeType] = None) -> CAPTCHAChallenge:
        """
        REM: Generate a new CAPTCHA challenge.
        REM: If no type is specified, one is selected at random.

        Args:
            challenge_type: The type of challenge to generate, or None for random

        Returns:
            CAPTCHAChallenge with the generated question and stored answer
        """
        if challenge_type is None:
            challenge_type = ChallengeType.MATH

        # REM: Dispatch to the appropriate generator
        if challenge_type == ChallengeType.MATH:
            question, answer = self._generate_math()
        elif challenge_type == ChallengeType.TEXT_REVERSE:
            question, answer = self._generate_text_reverse()
        elif challenge_type == ChallengeType.WORD_SCRAMBLE:
            question, answer = self._generate_word_scramble()
        else:
            question, answer = self._generate_math()

        now = datetime.now(timezone.utc)

        challenge = CAPTCHAChallenge(
            challenge_type=challenge_type,
            question=question,
            answer=answer,
            created_at=now,
            expires_at=now + self.CHALLENGE_LIFETIME,
            attempts=0,
            solved=False
        )

        self._challenges[challenge.challenge_id] = challenge
        self._save_record(challenge.challenge_id)

        logger.info(
            f"REM: CAPTCHA challenge generated ::{challenge.challenge_id}:: "
            f"type ::{challenge_type.value}::_Thank_You"
        )

        return challenge

    def verify_challenge(self, challenge_id: str, user_answer: str) -> bool:
        """
        REM: Verify a user's answer to a CAPTCHA challenge.
        REM: Uses constant-time comparison. Checks expiry and max attempts.

        Args:
            challenge_id: The challenge's unique identifier
            user_answer: The user's answer to verify

        Returns:
            True if the answer is correct
        """
        challenge = self._challenges.get(challenge_id)
        if not challenge:
            logger.warning(
                f"REM: Verification attempt for unknown challenge "
                f"::{challenge_id}::_Thank_You_But_No"
            )
            return False

        # REM: Check if already solved
        if challenge.solved:
            logger.info(
                f"REM: Challenge already solved ::{challenge_id}::_Thank_You"
            )
            return True

        # REM: Check expiry
        now = datetime.now(timezone.utc)
        if now > challenge.expires_at:
            logger.warning(
                f"REM: Challenge expired ::{challenge_id}::_Thank_You_But_No"
            )
            return False

        # REM: Check max attempts
        if challenge.attempts >= self.MAX_ATTEMPTS:
            logger.warning(
                f"REM: Max attempts exceeded for challenge "
                f"::{challenge_id}::_Thank_You_But_No"
            )
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"CAPTCHA max attempts exceeded: {challenge_id}",
                actor="unknown",
                resource=challenge_id,
                details={
                    "action": "captcha_max_attempts",
                    "challenge_type": challenge.challenge_type.value,
                    "attempts": challenge.attempts
                },
                qms_status="Thank_You_But_No"
            )
            return False

        # REM: Increment attempt counter
        challenge.attempts += 1

        # REM: Constant-time, case-insensitive comparison
        is_correct = hmac.compare_digest(
            user_answer.strip().lower(),
            challenge.answer.lower()
        )

        if is_correct:
            challenge.solved = True
            self._save_record(challenge_id)

            logger.info(
                f"REM: CAPTCHA solved successfully ::{challenge_id}::_Thank_You"
            )
        else:
            self._save_record(challenge_id)
            logger.warning(
                f"REM: CAPTCHA answer incorrect for ::{challenge_id}:: "
                f"(attempt {challenge.attempts}/{self.MAX_ATTEMPTS})_Thank_You_But_No"
            )

            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"CAPTCHA challenge failed (possible bot): {challenge_id}",
                actor="unknown",
                resource=challenge_id,
                details={
                    "action": "captcha_failed",
                    "challenge_type": challenge.challenge_type.value,
                    "attempt": challenge.attempts,
                    "max_attempts": self.MAX_ATTEMPTS
                },
                qms_status="Thank_You_But_No"
            )

        return is_correct

    def is_challenge_valid(self, challenge_id: str) -> bool:
        """
        REM: Check if a challenge is still valid (not expired, not solved, attempts remain).

        Args:
            challenge_id: The challenge's unique identifier

        Returns:
            True if the challenge can still accept answers
        """
        challenge = self._challenges.get(challenge_id)
        if not challenge:
            return False

        now = datetime.now(timezone.utc)
        if now > challenge.expires_at:
            return False

        if challenge.solved:
            return False

        if challenge.attempts >= self.MAX_ATTEMPTS:
            return False

        return True

    def is_solved(self, challenge_id: str) -> bool:
        """
        REM: Check if a challenge was successfully solved.

        Args:
            challenge_id: The challenge's unique identifier

        Returns:
            True if the challenge exists and was correctly answered
        """
        ch = self._challenges.get(challenge_id)
        return ch is not None and ch.solved

    def consume_challenge(self, challenge_id: str) -> bool:
        """
        REM: Check if a challenge was solved AND remove it from storage.
        REM: This is the single-use gate — once consumed, the challenge_id is
        REM: invalid and cannot be replayed for a second registration.
        REM: Must be called instead of is_solved() wherever a challenge is
        REM: redeemed (registration endpoint) to prevent replay attacks.

        Args:
            challenge_id: The challenge's unique identifier

        Returns:
            True if the challenge existed, was correctly answered, and has now
            been consumed (deleted). False if not solved or already consumed.
        """
        ch = self._challenges.get(challenge_id)
        if ch is None or not ch.solved:
            return False
        # REM: Remove from in-memory store — challenge_id is now permanently invalid.
        del self._challenges[challenge_id]
        # REM: Also remove from Redis so the challenge can't be replayed across
        # REM: workers or after a restart.
        try:
            from core.persistence import security_store
            security_store.delete_record("captcha", challenge_id)
        except Exception:
            pass  # Redis unavailable — in-memory deletion is sufficient
        logger.info(
            f"REM: CAPTCHA challenge consumed (single-use) ::{challenge_id}::_Thank_You"
        )
        return True

    def cleanup_expired(self) -> int:
        """
        REM: Remove all expired challenges from storage.

        Returns:
            Number of expired challenges removed
        """
        now = datetime.now(timezone.utc)
        expired_ids = [
            cid for cid, ch in self._challenges.items()
            if now > ch.expires_at
        ]

        for cid in expired_ids:
            del self._challenges[cid]

        if expired_ids:
            logger.info(
                f"REM: Cleaned up {len(expired_ids)} expired CAPTCHA challenges_Thank_You"
            )

            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Expired CAPTCHA challenges cleaned up: {len(expired_ids)}",
                actor="system",
                details={"action": "captcha_cleanup", "removed": len(expired_ids)},
                qms_status="Thank_You"
            )

        return len(expired_ids)

    def _generate_math(self) -> tuple:
        """
        REM: Generate a math-based CAPTCHA challenge.
        REM: Uses random 2-digit numbers with addition, subtraction, or multiplication.

        Returns:
            Tuple of (question_string, answer_string)
        """
        op = random.choice(["+", "-", "*"])

        if op == "+":
            a = random.randint(2, 20)
            b = random.randint(2, 20)
            result = a + b
            question = f"What is {a} + {b}?"
        elif op == "-":
            # REM: Ensure non-negative result for clarity
            a = random.randint(10, 25)
            b = random.randint(1, a)
            result = a - b
            question = f"What is {a} - {b}?"
        else:
            # REM: Single-digit multiplication — fast for humans, still requires computation
            a = random.randint(2, 9)
            b = random.randint(2, 9)
            result = a * b
            question = f"What is {a} x {b}?"

        return question, str(result)

    def _generate_text_reverse(self) -> tuple:
        """
        REM: Generate a text-reverse CAPTCHA challenge.
        REM: Selects a random word (5-7 letters) and asks the user to type it backwards.

        Returns:
            Tuple of (question_string, answer_string)
        """
        # REM: Filter words to 5-7 letter range for appropriate difficulty
        eligible = [w for w in CHALLENGE_WORDS if 5 <= len(w) <= 7]
        word = random.choice(eligible)
        answer = word[::-1]
        question = f"Type '{word}' backwards"

        return question, answer

    def _generate_word_scramble(self) -> tuple:
        """
        REM: Generate a word-scramble CAPTCHA challenge.
        REM: Scrambles the letters of a common word and asks the user to unscramble it.

        Returns:
            Tuple of (question_string, answer_string)
        """
        word = random.choice(CHALLENGE_WORDS)

        # REM: Shuffle letters until the scramble differs from the original
        letters = list(word)
        scrambled = list(word)
        max_shuffles = 10
        for _ in range(max_shuffles):
            random.shuffle(scrambled)
            if scrambled != letters:
                break

        scrambled_str = "".join(scrambled).upper()
        question = f"Unscramble: {scrambled_str}"

        return question, word


# REM: Global CAPTCHA manager instance
captcha_manager = CAPTCHAManager()
