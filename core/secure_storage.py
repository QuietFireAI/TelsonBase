# TelsonBase/core/secure_storage.py
# REM: =======================================================================================
# REM: ENCRYPTION AT REST FOR SENSITIVE DATA
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.3.0CC: New feature - Encrypt sensitive data before Redis storage
#
# REM: Mission Statement: Protect secrets in Redis from exposure. Even if Redis is
# REM: compromised, encrypted data is useless without the encryption key.
#
# REM: Features:
# REM:   - AES-256-GCM encryption for all secrets
# REM:   - Key derivation from environment variable
# REM:   - Authenticated encryption prevents tampering
# REM:   - Automatic encryption/decryption in storage layer
# REM: =======================================================================================

import os
import base64
import logging
import secrets
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


# REM: Environment variable for encryption key (must be set in production)
ENCRYPTION_KEY_ENV = "TELSONBASE_ENCRYPTION_KEY"
ENCRYPTION_SALT_ENV = "TELSONBASE_ENCRYPTION_SALT"


@dataclass
class EncryptedValue:
    """REM: Container for encrypted data with metadata."""
    ciphertext: bytes
    nonce: bytes
    version: int = 1

    def to_bytes(self) -> bytes:
        """REM: Serialize for storage."""
        # Format: version (1 byte) + nonce (12 bytes) + ciphertext
        return bytes([self.version]) + self.nonce + self.ciphertext

    @classmethod
    def from_bytes(cls, data: bytes) -> 'EncryptedValue':
        """REM: Deserialize from storage."""
        version = data[0]
        nonce = data[1:13]
        ciphertext = data[13:]
        return cls(ciphertext=ciphertext, nonce=nonce, version=version)


class SecureStorageManager:
    """
    REM: Manages encryption/decryption of sensitive data for Redis storage.
    """

    NONCE_SIZE = 12  # 96 bits for AES-GCM
    KEY_SIZE = 32    # 256 bits

    def __init__(self, encryption_key: Optional[str] = None, salt: Optional[str] = None):
        """
        REM: Initialize with encryption key.

        Args:
            encryption_key: Base encryption key (from env if not provided)
            salt: Salt for key derivation (from env if not provided)
        """
        self._initialized = False

        # REM: Get key from environment or parameter
        key_material = encryption_key or os.environ.get(ENCRYPTION_KEY_ENV)
        salt_material = salt or os.environ.get(ENCRYPTION_SALT_ENV)

        if not key_material:
            logger.warning(
                f"REM: {ENCRYPTION_KEY_ENV} not set - generating ephemeral key. "
                f"DATA WILL NOT PERSIST ACROSS RESTARTS!_Thank_You_But_No"
            )
            key_material = secrets.token_hex(32)
            salt_material = secrets.token_hex(16)

        if not salt_material:
            salt_material = "telsonbase_default_salt_CHANGE_ME"
            logger.warning(
                f"REM: {ENCRYPTION_SALT_ENV} not set - using default. "
                f"Set for production!_Thank_You_But_No"
            )

        # REM: Derive key using PBKDF2
        self._encryption_key = self._derive_key(key_material, salt_material)
        self._aesgcm = AESGCM(self._encryption_key)
        self._initialized = True

        logger.info("REM: Secure storage initialized_Thank_You")

    def _derive_key(self, key_material: str, salt: str) -> bytes:
        """REM: Derive encryption key using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt.encode('utf-8'),
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(key_material.encode('utf-8'))

    def encrypt(self, plaintext: Union[str, bytes]) -> bytes:
        """
        REM: Encrypt data for storage.

        Args:
            plaintext: Data to encrypt (string or bytes)

        Returns:
            Encrypted data as bytes (ready for Redis storage)
        """
        if not self._initialized:
            raise RuntimeError("Secure storage not initialized")

        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')

        # REM: Generate random nonce
        nonce = secrets.token_bytes(self.NONCE_SIZE)

        # REM: Encrypt with AES-GCM (includes authentication)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)

        encrypted = EncryptedValue(ciphertext=ciphertext, nonce=nonce)
        return encrypted.to_bytes()

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """
        REM: Decrypt data from storage.

        Args:
            encrypted_data: Encrypted data bytes from Redis

        Returns:
            Decrypted plaintext as bytes
        """
        if not self._initialized:
            raise RuntimeError("Secure storage not initialized")

        encrypted = EncryptedValue.from_bytes(encrypted_data)

        # REM: Decrypt and verify authentication tag
        plaintext = self._aesgcm.decrypt(
            encrypted.nonce,
            encrypted.ciphertext,
            None
        )

        return plaintext

    def encrypt_string(self, plaintext: str) -> str:
        """REM: Encrypt a string and return base64-encoded result."""
        encrypted = self.encrypt(plaintext)
        return base64.b64encode(encrypted).decode('utf-8')

    def decrypt_string(self, encrypted_b64: str) -> str:
        """REM: Decrypt a base64-encoded encrypted string."""
        encrypted = base64.b64decode(encrypted_b64)
        decrypted = self.decrypt(encrypted)
        return decrypted.decode('utf-8')

    def encrypt_dict(self, data: Dict[str, Any], sensitive_keys: list) -> Dict[str, Any]:
        """
        REM: Encrypt specific keys in a dictionary.

        Args:
            data: Dictionary to process
            sensitive_keys: Keys whose values should be encrypted

        Returns:
            Dictionary with sensitive values encrypted
        """
        result = data.copy()
        for key in sensitive_keys:
            if key in result and result[key] is not None:
                value = result[key]
                if isinstance(value, bytes):
                    value = base64.b64encode(value).decode('utf-8')
                elif not isinstance(value, str):
                    value = str(value)
                result[key] = self.encrypt_string(value)
                result[f"_{key}_encrypted"] = True
        return result

    def decrypt_dict(self, data: Dict[str, Any], sensitive_keys: list) -> Dict[str, Any]:
        """
        REM: Decrypt specific keys in a dictionary.

        Args:
            data: Dictionary to process
            sensitive_keys: Keys whose values should be decrypted

        Returns:
            Dictionary with sensitive values decrypted
        """
        result = data.copy()
        for key in sensitive_keys:
            if data.get(f"_{key}_encrypted") and key in result:
                try:
                    result[key] = self.decrypt_string(result[key])
                    del result[f"_{key}_encrypted"]
                except Exception as e:
                    logger.error(f"REM: Failed to decrypt {key}: {e}_Thank_You_But_No")
        return result


    # REM: v6.3.0CC Enhancement — HIPAA 45 CFR 164.312(c)(1) PHI Integrity Controls

    def compute_integrity_hash(self, data: bytes, context: str = "") -> str:
        """REM: Compute HMAC-SHA256 for data integrity verification."""
        import hmac as hmac_mod
        import hashlib
        key_material = self._encryption_key if self._initialized else b"integrity-check"
        h = hmac_mod.new(key_material, data + context.encode(), hashlib.sha256)
        return h.hexdigest()

    def verify_integrity(self, data: bytes, expected_hash: str, context: str = "") -> bool:
        """REM: Verify HMAC integrity of data."""
        import hmac as hmac_mod
        computed = self.compute_integrity_hash(data, context)
        return hmac_mod.compare_digest(computed, expected_hash)


class SecureRedisStore:
    """
    REM: Redis store wrapper with automatic encryption for sensitive fields.
    """

    # REM: Keys that should always be encrypted
    DEFAULT_SENSITIVE_KEYS = [
        'signing_key',
        'secret_key',
        'api_key',
        'token',
        'password',
        'private_key',
        'session_key',
        'encryption_key'
    ]

    def __init__(self, redis_client, secure_storage: SecureStorageManager):
        self._redis = redis_client
        self._secure = secure_storage
        self._sensitive_keys = set(self.DEFAULT_SENSITIVE_KEYS)

    def add_sensitive_key(self, key: str):
        """REM: Add a key to the list of fields to encrypt."""
        self._sensitive_keys.add(key)

    def store_secret(self, redis_key: str, value: Union[str, bytes], ttl: Optional[int] = None):
        """
        REM: Store an encrypted secret in Redis.

        Args:
            redis_key: Redis key to store under
            value: Secret value to encrypt and store
            ttl: Optional TTL in seconds
        """
        encrypted = self._secure.encrypt(value if isinstance(value, bytes) else value.encode())
        encrypted_b64 = base64.b64encode(encrypted).decode('utf-8')

        if ttl:
            self._redis.setex(redis_key, ttl, encrypted_b64)
        else:
            self._redis.set(redis_key, encrypted_b64)

        logger.debug(f"REM: Stored encrypted secret at ::{redis_key}::_Thank_You")

    def retrieve_secret(self, redis_key: str) -> Optional[bytes]:
        """
        REM: Retrieve and decrypt a secret from Redis.

        Args:
            redis_key: Redis key to retrieve

        Returns:
            Decrypted secret as bytes, or None if not found
        """
        encrypted_b64 = self._redis.get(redis_key)
        if not encrypted_b64:
            return None

        try:
            encrypted = base64.b64decode(encrypted_b64)
            return self._secure.decrypt(encrypted)
        except Exception as e:
            logger.error(f"REM: Failed to decrypt secret at ::{redis_key}:: - {e}_Thank_You_But_No")
            return None

    def store_json(self, redis_key: str, data: Dict[str, Any], ttl: Optional[int] = None):
        """
        REM: Store JSON data with sensitive fields encrypted.

        Args:
            redis_key: Redis key to store under
            data: Dictionary to store
            ttl: Optional TTL in seconds
        """
        import json

        encrypted_data = self._secure.encrypt_dict(data, list(self._sensitive_keys))
        json_str = json.dumps(encrypted_data)

        if ttl:
            self._redis.setex(redis_key, ttl, json_str)
        else:
            self._redis.set(redis_key, json_str)

    def retrieve_json(self, redis_key: str) -> Optional[Dict[str, Any]]:
        """
        REM: Retrieve JSON data with sensitive fields decrypted.

        Args:
            redis_key: Redis key to retrieve

        Returns:
            Decrypted dictionary, or None if not found
        """
        import json

        json_str = self._redis.get(redis_key)
        if not json_str:
            return None

        try:
            data = json.loads(json_str)
            return self._secure.decrypt_dict(data, list(self._sensitive_keys))
        except Exception as e:
            logger.error(f"REM: Failed to retrieve JSON at ::{redis_key}:: - {e}_Thank_You_But_No")
            return None

    def delete_secret(self, redis_key: str):
        """REM: Securely delete a secret from Redis."""
        self._redis.delete(redis_key)
        logger.debug(f"REM: Deleted secret at ::{redis_key}::_Thank_You")


# REM: Global secure storage instance
secure_storage = SecureStorageManager()


def get_secure_redis_store(redis_client) -> SecureRedisStore:
    """REM: Factory function to create a secure Redis store."""
    return SecureRedisStore(redis_client, secure_storage)
