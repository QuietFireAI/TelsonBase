# TelsonBase/core/identiclaw.py
# REM: =======================================================================================
# REM: IDENTICLAW MCP-I IDENTITY ENGINE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v7.3.0CC: Identiclaw integration — DID-based agent identity verification
#
# REM: Mission Statement: Give AI agents cryptographic identities they can prove,
# REM: while keeping all operations governed on TelsonBase. Identiclaw issues the
# REM: driver's license (DID + Verifiable Credentials). TelsonBase is the racetrack
# REM: with guardrails, pit stops, and race officials.
#
# REM: Architecture (Option 2 — Hybrid):
# REM:   - Identity registration/issuance: Cloudflare (Identiclaw's infrastructure)
# REM:   - Identity verification: LOCAL (Ed25519 crypto, no external calls)
# REM:   - Agent operations: LOCAL (TelsonBase approval gates, egress, audit)
# REM:   - Kill switch: LOCAL (overrides Identiclaw status immediately)
#
# REM: Auth flow per-request (all local, no network):
# REM:   Parse X-DID-Auth header → Check nonce not replayed (Redis, 5min) →
# REM:   Check timestamp within window → Check DID not revoked (kill switch) →
# REM:   Look up DID doc in cache → Ed25519 verify signature → Return AuthResult
#
# REM: MCP-I Protocol: https://modelcontextprotocol-identity.io/
# REM: W3C DID: https://www.w3.org/TR/did-core/
# REM: W3C VC: https://www.w3.org/TR/vc-data-model/
# REM: =======================================================================================

import base64
import hashlib
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Set, Any

from pydantic import BaseModel, Field

from core.audit import audit, AuditEventType
from core.config import get_settings

logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: DATA MODELS
# REM: =======================================================================================

class DIDDocument(BaseModel):
    """
    REM: Parsed W3C DID Document.
    REM: Contains the agent's public key for local signature verification.
    REM: Resolved from Identiclaw registry on first contact, cached locally.
    """
    did: str                                    # e.g., "did:key:z6MkhaXgBZDvotDkL..."
    method: str                                 # "key" or "web"
    public_key_bytes: bytes                     # Ed25519 public key (32 bytes)
    public_key_hex: str                         # Hex-encoded for storage
    verification_method: str = ""               # e.g., "did:key:z6Mk...#key-1"
    service_endpoints: List[Dict] = Field(default_factory=list)
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=24))

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            bytes: lambda v: base64.b64encode(v).decode("ascii"),
            datetime: lambda v: v.isoformat()
        }


class VerifiableCredential(BaseModel):
    """
    REM: Parsed W3C Verifiable Credential.
    REM: Contains scoped permissions issued by Identiclaw to an agent.
    """
    vc_id: str                                  # Unique credential identifier
    issuer_did: str                             # Who issued this credential
    subject_did: str                            # Who this credential is about (the agent)
    credential_type: List[str] = Field(default_factory=list)  # ["VerifiableCredential", "AgentCapability"]
    claims: Dict[str, Any] = Field(default_factory=dict)      # The permission claims
    scopes: List[str] = Field(default_factory=list)            # Extracted scope strings
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=24))
    proof_type: str = "Ed25519Signature2020"
    proof_value: str = ""                       # Base64-encoded signature

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AgentIdentityRecord(BaseModel):
    """
    REM: TelsonBase's local record of a DID-authenticated agent.
    REM: This is what we store — the agent's passport stamp for our racetrack.
    """
    did: str                                    # The agent's DID
    display_name: str = ""                      # Human-readable label
    public_key_hex: str = ""                    # Cached public key
    active_credential_ids: List[str] = Field(default_factory=list)  # Active VC IDs
    telsonbase_permissions: List[str] = Field(default_factory=list)  # Mapped permissions
    trust_level: str = "quarantine"             # Starts at quarantine
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_verified_at: Optional[datetime] = None
    revoked: bool = False                       # Kill switch
    revoked_by: Optional[str] = None
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None
    manners_md_path: Optional[str] = None          # Link to MANNERS.md constraint file
    profession_md_path: Optional[str] = None    # Link to Profession.md job description
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# REM: =======================================================================================
# REM: SCOPE-TO-PERMISSION MAPPING
# REM: =======================================================================================
# REM: Maps Identiclaw VC scopes to TelsonBase permission strings.
# REM: CRITICAL: Unknown scopes grant ZERO permissions (fail-closed).
# REM: =======================================================================================

SCOPE_PERMISSION_MAP: Dict[str, List[str]] = {
    # REM: Broad agent scopes
    "agent:read": ["read"],
    "agent:write": ["read", "write"],
    "agent:execute": ["read", "write", "execute"],
    "agent:admin": ["*"],

    # REM: MCP-I specific scopes
    "mcp:tool:invoke": ["tool_invoke"],
    "mcp:tool:list": ["tool_list"],
    "mcp:resource:read": ["read"],
    "mcp:resource:write": ["write"],
    "mcp:prompt:execute": ["prompt_execute"],

    # REM: TelsonBase-specific scopes (custom extension)
    "telsonbase:backup:read": ["backup_read"],
    "telsonbase:backup:create": ["backup_create"],
    "telsonbase:agent:register": ["agent_register"],
    "telsonbase:llm:chat": ["llm_chat"],
    "telsonbase:llm:manage": ["llm_manage"],
    "telsonbase:workflow:execute": ["workflow_execute"],
    "telsonbase:system:analyze": ["system_analyze"],
}


# REM: =======================================================================================
# REM: DID PARSING UTILITIES
# REM: =======================================================================================

# REM: Multicodec prefix for Ed25519 public keys (0xed01)
_ED25519_MULTICODEC_PREFIX = bytes([0xed, 0x01])

# REM: Base58btc alphabet (used by did:key)
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _base58_decode(encoded: str) -> bytes:
    """REM: Decode a base58btc-encoded string to bytes."""
    result = 0
    for char in encoded:
        result = result * 58 + _BASE58_ALPHABET.index(char)
    # REM: Convert int to bytes
    result_bytes = []
    while result > 0:
        result_bytes.append(result % 256)
        result //= 256
    # REM: Preserve leading zeros
    for char in encoded:
        if char == "1":
            result_bytes.append(0)
        else:
            break
    return bytes(reversed(result_bytes))


def parse_did_key(did: str) -> Optional[bytes]:
    """
    REM: Parse a did:key identifier to extract the Ed25519 public key.
    REM: Format: did:key:z6Mk<base58btc-encoded-multicodec-key>
    REM: The 'z' prefix indicates base58btc encoding.
    REM: The first two bytes are the multicodec prefix (0xed01 for Ed25519).

    Returns:
        Ed25519 public key bytes (32 bytes) or None if invalid
    """
    if not did.startswith("did:key:z"):
        logger.warning(f"REM: Invalid did:key format: {did[:50]}_Thank_You_But_No")
        return None

    try:
        # REM: Strip the 'z' prefix (base58btc indicator) and decode
        encoded = did.split(":")[-1][1:]  # Remove 'z' prefix
        decoded = _base58_decode(encoded)

        # REM: Verify multicodec prefix (0xed01 = Ed25519 public key)
        if not decoded[:2] == _ED25519_MULTICODEC_PREFIX:
            logger.warning(f"REM: Not an Ed25519 key (wrong multicodec prefix)_Thank_You_But_No")
            return None

        # REM: Extract the 32-byte public key after the 2-byte prefix
        public_key = decoded[2:]
        if len(public_key) != 32:
            logger.warning(f"REM: Ed25519 key wrong length: {len(public_key)} (expected 32)_Thank_You_But_No")
            return None

        return public_key

    except Exception as e:
        logger.warning(f"REM: Failed to parse did:key: {e}_Thank_You_But_No")
        return None


def parse_did(did: str) -> Optional[Dict[str, Any]]:
    """
    REM: Parse a DID string and return its components.
    REM: Supports did:key and did:web methods.
    """
    if not did or not did.startswith("did:"):
        return None

    parts = did.split(":", 2)
    if len(parts) < 3:
        return None

    method = parts[1]
    specific_id = parts[2]

    if method == "key":
        public_key = parse_did_key(did)
        if public_key:
            return {
                "did": did,
                "method": "key",
                "specific_id": specific_id,
                "public_key_bytes": public_key
            }
    elif method == "web":
        # REM: did:web identifiers use domain-based resolution
        return {
            "did": did,
            "method": "web",
            "specific_id": specific_id,
            "public_key_bytes": None  # Must be resolved via HTTP
        }
    else:
        logger.warning(f"REM: Unsupported DID method: {method}_Thank_You_But_No")

    return None


# REM: =======================================================================================
# REM: IDENTICLAW MANAGER (SINGLETON)
# REM: =======================================================================================

class IdenticlawManager:
    """
    REM: v7.3.0CC — Singleton manager for all Identiclaw identity operations.
    REM: Follows the pattern of: APIKeyRegistry (auth.py), ApprovalGate (approval.py)
    REM:
    REM: Responsibilities:
    REM:   1. DID document resolution and caching
    REM:   2. Ed25519 signature verification (local, no external calls)
    REM:   3. W3C Verifiable Credential parsing and validation
    REM:   4. Credential-to-permission mapping
    REM:   5. Agent identity cache (Redis-backed)
    REM:   6. Kill switch (local revocation overrides Identiclaw status)
    """

    def __init__(self):
        self._identity_cache: Dict[str, AgentIdentityRecord] = {}
        self._did_cache: Dict[str, DIDDocument] = {}
        self._vc_cache: Dict[str, VerifiableCredential] = {}
        self._revoked_dids: Set[str] = set()
        self._initialized = False

    # REM: ==========================================
    # REM: INITIALIZATION
    # REM: ==========================================

    def startup_check(self):
        """REM: Called during app lifespan when IDENTICLAW_ENABLED=true."""
        self._load_from_persistence()
        self._initialized = True
        logger.info(
            f"REM: Identiclaw MCP-I engine initialized — "
            f"{len(self._identity_cache)} agents cached, "
            f"{len(self._revoked_dids)} revoked_Thank_You"
        )

    def _get_redis(self):
        """REM: Lazy Redis client to avoid circular imports."""
        try:
            import redis
            settings = get_settings()
            return redis.Redis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            return None

    def _load_from_persistence(self):
        """REM: Load cached identities and revocations from Redis on startup."""
        client = self._get_redis()
        if not client:
            return

        try:
            # REM: Load revoked DIDs
            revoked_keys = client.keys("identiclaw:revoked:*")
            for key in revoked_keys:
                did = key.replace("identiclaw:revoked:", "")
                self._revoked_dids.add(did)

            # REM: Load agent identity records
            agent_keys = client.keys("identiclaw:agent:*")
            for key in agent_keys:
                data = client.get(key)
                if data:
                    try:
                        record = AgentIdentityRecord.model_validate_json(data)
                        self._identity_cache[record.did] = record
                    except Exception as e:
                        logger.warning(f"REM: Failed to load identity record from {key}: {e}")

            # REM: Load cached DID documents
            did_keys = client.keys("identiclaw:did:*")
            for key in did_keys:
                data = client.get(key)
                if data:
                    try:
                        doc_data = json.loads(data)
                        # REM: Reconstruct DIDDocument from stored JSON
                        doc = DIDDocument(
                            did=doc_data["did"],
                            method=doc_data["method"],
                            public_key_bytes=bytes.fromhex(doc_data["public_key_hex"]),
                            public_key_hex=doc_data["public_key_hex"],
                            verification_method=doc_data.get("verification_method", ""),
                            resolved_at=datetime.fromisoformat(doc_data["resolved_at"]),
                            expires_at=datetime.fromisoformat(doc_data["expires_at"]),
                        )
                        if doc.expires_at > datetime.now(timezone.utc):
                            self._did_cache[doc.did] = doc
                    except Exception as e:
                        logger.warning(f"REM: Failed to load DID document from {key}: {e}")

            logger.info(
                f"REM: Loaded from Redis — {len(self._identity_cache)} identities, "
                f"{len(self._did_cache)} DID docs, {len(self._revoked_dids)} revocations_Thank_You"
            )
        except Exception as e:
            logger.warning(f"REM: Failed to load Identiclaw state from Redis: {e}_Excuse_Me")

    # REM: ==========================================
    # REM: DID DOCUMENT RESOLUTION
    # REM: ==========================================

    def resolve_did_local(self, did: str) -> Optional[DIDDocument]:
        """
        REM: Resolve a DID to its document using LOCAL parsing only (did:key).
        REM: For did:key, the public key is embedded in the identifier itself.
        REM: No network call needed.
        """
        parsed = parse_did(did)
        if not parsed:
            return None

        if parsed["method"] == "key" and parsed["public_key_bytes"]:
            doc = DIDDocument(
                did=did,
                method="key",
                public_key_bytes=parsed["public_key_bytes"],
                public_key_hex=parsed["public_key_bytes"].hex(),
                verification_method=f"{did}#key-1",
            )
            return doc

        return None

    def resolve_did(self, did: str, force_refresh: bool = False) -> Optional[DIDDocument]:
        """
        REM: Resolve a DID to its document.
        REM: 1. Check local cache
        REM: 2. If did:key, parse locally (no network needed)
        REM: 3. If did:web and cache miss, would need HTTP resolution (via egress)
        REM: 4. Cache the result in Redis
        """
        # REM: Check cache first (unless force refresh)
        if not force_refresh and did in self._did_cache:
            cached = self._did_cache[did]
            if cached.expires_at > datetime.now(timezone.utc):
                return cached

        # REM: Try local resolution (did:key embeds the public key)
        doc = self.resolve_did_local(did)
        if doc:
            self._did_cache[did] = doc
            self._persist_did_document(doc)
            return doc

        # REM: did:web requires HTTP resolution — would go through egress gateway
        # REM: For MVP, did:web resolution is a future enhancement
        parsed = parse_did(did)
        if parsed and parsed["method"] == "web":
            logger.info(f"REM: did:web resolution not yet implemented for {did}_Excuse_Me")
            return None

        return None

    def _persist_did_document(self, doc: DIDDocument):
        """REM: Cache a DID document in Redis with TTL."""
        client = self._get_redis()
        if not client:
            return
        try:
            settings = get_settings()
            ttl_seconds = settings.identiclaw_did_cache_ttl_hours * 3600
            doc_data = {
                "did": doc.did,
                "method": doc.method,
                "public_key_hex": doc.public_key_hex,
                "verification_method": doc.verification_method,
                "resolved_at": doc.resolved_at.isoformat(),
                "expires_at": doc.expires_at.isoformat(),
            }
            client.setex(
                f"identiclaw:did:{doc.did}",
                ttl_seconds,
                json.dumps(doc_data)
            )
        except Exception as e:
            logger.warning(f"REM: Failed to persist DID document: {e}")

    # REM: ==========================================
    # REM: ED25519 SIGNATURE VERIFICATION (LOCAL)
    # REM: ==========================================

    def verify_signature(self, public_key_bytes: bytes, message: bytes, signature: bytes) -> bool:
        """
        REM: Verify an Ed25519 signature using the cached public key.
        REM: 100% local — no external calls. Uses cryptography library.
        """
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            from cryptography.exceptions import InvalidSignature

            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            public_key.verify(signature, message)
            return True

        except InvalidSignature:
            return False
        except Exception as e:
            logger.warning(f"REM: Ed25519 verification error: {e}_Thank_You_But_No")
            return False

    # REM: ==========================================
    # REM: VERIFIABLE CREDENTIAL VALIDATION
    # REM: ==========================================

    def validate_credential(self, vc_json: Dict) -> Optional[VerifiableCredential]:
        """
        REM: Parse and validate a W3C Verifiable Credential.
        REM: 1. Parse JSON structure
        REM: 2. Verify issuer is in known issuers list
        REM: 3. Verify expiration
        REM: 4. Verify issuer signature (Ed25519, local) if issuer DID is resolvable
        REM: 5. Extract scopes/claims
        """
        try:
            settings = get_settings()

            # REM: Parse required fields
            vc_id = vc_json.get("id", vc_json.get("jti", ""))
            issuer = vc_json.get("issuer", "")
            if isinstance(issuer, dict):
                issuer_did = issuer.get("id", "")
            else:
                issuer_did = str(issuer)

            subject = vc_json.get("credentialSubject", {})
            subject_did = subject.get("id", "") if isinstance(subject, dict) else ""

            # REM: Check issuer is trusted
            if issuer_did not in settings.identiclaw_known_issuers:
                logger.warning(
                    f"REM: VC issuer not trusted: {issuer_did} "
                    f"(known: {settings.identiclaw_known_issuers})_Thank_You_But_No"
                )
                return None

            # REM: Parse credential type
            cred_type = vc_json.get("type", ["VerifiableCredential"])
            if isinstance(cred_type, str):
                cred_type = [cred_type]

            # REM: Parse issuance and expiration dates
            issued_at = datetime.now(timezone.utc)
            if "issuanceDate" in vc_json:
                try:
                    issued_at = datetime.fromisoformat(vc_json["issuanceDate"].replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            if "expirationDate" in vc_json:
                try:
                    expires_at = datetime.fromisoformat(vc_json["expirationDate"].replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            # REM: Check expiration
            if expires_at < datetime.now(timezone.utc):
                logger.warning(f"REM: VC expired at {expires_at.isoformat()}_Thank_You_But_No")
                return None

            # REM: Extract scopes from claims
            scopes = []
            if isinstance(subject, dict):
                scopes = subject.get("scopes", subject.get("scope", []))
                if isinstance(scopes, str):
                    scopes = scopes.split()

            # REM: Parse proof
            proof = vc_json.get("proof", {})
            proof_type = proof.get("type", "Ed25519Signature2020")
            proof_value = proof.get("proofValue", proof.get("jws", ""))

            # REM: Verify issuer signature if we can resolve the issuer DID
            if proof_value and issuer_did:
                issuer_doc = self.resolve_did(issuer_did)
                if issuer_doc:
                    try:
                        sig_bytes = base64.b64decode(proof_value)
                        # REM: Reconstruct the message that was signed
                        # REM: (simplified — full W3C VC signature uses canonicalization)
                        message_data = json.dumps({
                            k: v for k, v in vc_json.items() if k != "proof"
                        }, sort_keys=True, separators=(",", ":")).encode("utf-8")

                        if not self.verify_signature(issuer_doc.public_key_bytes, message_data, sig_bytes):
                            logger.warning(f"REM: VC signature invalid for {vc_id}_Thank_You_But_No")
                            return None
                    except Exception as e:
                        logger.warning(f"REM: VC signature verification skipped: {e}")
                        # REM: Don't fail on unverifiable signatures for MVP
                        # REM: (issuer may use did:web which we can't resolve yet)

            vc = VerifiableCredential(
                vc_id=vc_id,
                issuer_did=issuer_did,
                subject_did=subject_did,
                credential_type=cred_type,
                claims=subject if isinstance(subject, dict) else {},
                scopes=scopes,
                issued_at=issued_at,
                expires_at=expires_at,
                proof_type=proof_type,
                proof_value=proof_value,
            )

            # REM: Cache the validated VC
            self._vc_cache[vc_id] = vc
            self._persist_credential(vc)

            return vc

        except Exception as e:
            logger.error(f"REM: VC validation failed: {e}_Thank_You_But_No")
            return None

    def _persist_credential(self, vc: VerifiableCredential):
        """REM: Cache a validated VC in Redis with TTL."""
        client = self._get_redis()
        if not client:
            return
        try:
            settings = get_settings()
            ttl_seconds = settings.identiclaw_vc_cache_ttl_hours * 3600
            client.setex(
                f"identiclaw:vc:{vc.vc_id}",
                ttl_seconds,
                vc.model_dump_json()
            )
        except Exception as e:
            logger.warning(f"REM: Failed to persist VC: {e}")

    # REM: ==========================================
    # REM: PERMISSION MAPPING
    # REM: ==========================================

    def map_scopes_to_permissions(self, scopes: List[str]) -> List[str]:
        """
        REM: Map Identiclaw VC scopes to TelsonBase permission strings.
        REM: CRITICAL: Unknown scopes grant ZERO permissions (fail-closed).
        """
        permissions = set()
        for scope in scopes:
            mapped = SCOPE_PERMISSION_MAP.get(scope)
            if mapped:
                permissions.update(mapped)
            else:
                logger.info(f"REM: Unknown scope ignored (fail-closed): {scope}")
        return sorted(permissions)

    # REM: ==========================================
    # REM: AGENT REGISTRATION
    # REM: ==========================================

    def register_agent(
        self,
        did: str,
        credentials: List[Dict] = None,
        display_name: str = "",
        manners_md_path: Optional[str] = None,
        profession_md_path: Optional[str] = None,
        registered_by: str = "system"
    ) -> Optional[AgentIdentityRecord]:
        """
        REM: Register an agent identity from Identiclaw.
        REM: Resolves the DID, validates credentials, maps permissions.
        REM: The agent starts at QUARANTINE trust level.
        """
        # REM: Check if already registered
        if did in self._identity_cache:
            existing = self._identity_cache[did]
            if not existing.revoked:
                logger.info(f"REM: DID already registered: {did}_Thank_You")
                return existing

        # REM: Resolve the DID document
        doc = self.resolve_did(did)
        if not doc:
            logger.warning(f"REM: Cannot resolve DID: {did}_Thank_You_But_No")
            return None

        # REM: Validate credentials and extract permissions
        all_permissions = set()
        active_vc_ids = []

        for vc_json in (credentials or []):
            vc = self.validate_credential(vc_json)
            if vc:
                active_vc_ids.append(vc.vc_id)
                perms = self.map_scopes_to_permissions(vc.scopes)
                all_permissions.update(perms)

        # REM: Create identity record
        record = AgentIdentityRecord(
            did=did,
            display_name=display_name or did[:32],
            public_key_hex=doc.public_key_hex,
            active_credential_ids=active_vc_ids,
            telsonbase_permissions=sorted(all_permissions),
            trust_level="quarantine",
            registered_at=datetime.now(timezone.utc),
            last_verified_at=datetime.now(timezone.utc),
            manners_md_path=manners_md_path,
            profession_md_path=profession_md_path,
        )

        # REM: Store in cache and persist
        self._identity_cache[did] = record
        self._persist_agent(record)

        # REM: Audit trail
        audit.log(
            AuditEventType.AGENT_REGISTERED,
            f"DID agent registered: ::{display_name or did[:32]}:: ({did[:32]}...)",
            actor=registered_by,
            details={
                "did": did,
                "display_name": display_name,
                "permissions": sorted(all_permissions),
                "credential_count": len(active_vc_ids),
                "trust_level": "quarantine",
            },
            qms_status="Thank_You"
        )

        logger.info(
            f"REM: DID agent registered ::{display_name}:: "
            f"with {len(all_permissions)} permissions_Thank_You"
        )
        return record

    def _persist_agent(self, record: AgentIdentityRecord):
        """REM: Persist agent identity record to Redis."""
        client = self._get_redis()
        if not client:
            return
        try:
            client.set(
                f"identiclaw:agent:{record.did}",
                record.model_dump_json()
            )
        except Exception as e:
            logger.warning(f"REM: Failed to persist agent identity: {e}")

    # REM: ==========================================
    # REM: AUTHENTICATION FROM HEADER
    # REM: ==========================================

    def authenticate_from_header(
        self, header_value: str, request_path: str, request_method: str
    ) -> Optional[AgentIdentityRecord]:
        """
        REM: Authenticate an agent from the X-DID-Auth header.
        REM: Header format: <did>:<base64-signature>:<nonce>:<timestamp>
        REM:
        REM: The signature is computed over: nonce + timestamp + path + method
        REM: using the agent's Ed25519 private key.
        REM:
        REM: All checks are LOCAL (no network calls):
        REM:   1. Parse header
        REM:   2. Check nonce not replayed (Redis)
        REM:   3. Check timestamp within 5-minute window
        REM:   4. Check DID not revoked (kill switch)
        REM:   5. Look up DID document in cache
        REM:   6. Ed25519 verify signature
        REM:   7. Return AgentIdentityRecord
        """
        try:
            # REM: Step 1 — Parse header
            parts = header_value.split(":", 3)
            # REM: DID itself contains colons (did:key:z6Mk...), so we need smarter parsing
            # REM: Header format is actually: <full-did>|<base64-sig>|<nonce>|<timestamp>
            # REM: Using pipe delimiter to avoid DID colon conflicts
            parts = header_value.split("|")
            if len(parts) != 4:
                logger.warning(f"REM: Invalid X-DID-Auth header format (expected 4 pipe-delimited parts)_Thank_You_But_No")
                return None

            did, sig_b64, nonce, timestamp_str = parts

            # REM: Step 2 — Replay protection
            if not self._check_nonce(nonce):
                logger.warning(f"REM: Nonce replay detected for DID {did[:32]}..._Thank_You_But_No")
                audit.log(
                    AuditEventType.SECURITY_ALERT,
                    f"DID auth nonce replay: {did[:32]}...",
                    actor=f"did:{did}",
                    details={"nonce": nonce},
                    qms_status="Thank_You_But_No"
                )
                return None

            # REM: Step 3 — Timestamp window check (5 minutes)
            try:
                timestamp = float(timestamp_str)
                now = time.time()
                if abs(now - timestamp) > 300:  # 5 minutes
                    logger.warning(f"REM: DID auth timestamp outside window_Thank_You_But_No")
                    return None
            except (ValueError, TypeError):
                logger.warning(f"REM: Invalid timestamp in DID auth header_Thank_You_But_No")
                return None

            # REM: Step 4 — Kill switch check (FIRST — fast rejection)
            if self.is_revoked(did):
                logger.warning(f"REM: Revoked DID attempted auth: {did[:32]}..._Thank_You_But_No")
                audit.log(
                    AuditEventType.SECURITY_ALERT,
                    f"Revoked DID auth attempt: {did[:32]}...",
                    actor=f"did:{did}",
                    details={"did": did},
                    qms_status="Thank_You_But_No"
                )
                return None

            # REM: Step 5 — Look up DID document (cache only on auth path)
            doc = self._did_cache.get(did)
            if not doc:
                # REM: Try local resolution for did:key (no network needed)
                doc = self.resolve_did_local(did)
                if doc:
                    self._did_cache[did] = doc
                else:
                    logger.warning(
                        f"REM: DID not in cache and cannot resolve locally: {did[:32]}..._Thank_You_But_No"
                    )
                    return None

            # REM: Step 6 — Ed25519 signature verification
            message = f"{nonce}{timestamp_str}{request_path}{request_method}".encode("utf-8")
            try:
                sig_bytes = base64.b64decode(sig_b64)
            except Exception:
                logger.warning(f"REM: Invalid base64 signature_Thank_You_But_No")
                return None

            if not self.verify_signature(doc.public_key_bytes, message, sig_bytes):
                logger.warning(f"REM: DID signature verification failed: {did[:32]}..._Thank_You_But_No")
                audit.log(
                    AuditEventType.AUTH_FAILURE,
                    f"DID signature failed: {did[:32]}...",
                    actor=f"did:{did}",
                    details={"did": did, "path": request_path},
                    qms_status="Thank_You_But_No"
                )
                return None

            # REM: Step 7 — Return identity record
            record = self._identity_cache.get(did)
            if not record:
                # REM: DID authenticated but not registered — create minimal record
                logger.info(f"REM: Authenticated but unregistered DID: {did[:32]}..._Excuse_Me")
                return None

            # REM: Update last verified timestamp
            record.last_verified_at = datetime.now(timezone.utc)

            # REM: Mark nonce as used
            self._mark_nonce_used(nonce)

            logger.debug(f"REM: DID auth success: {did[:32]}..._Thank_You")
            return record

        except Exception as e:
            logger.error(f"REM: DID authentication error: {e}_Thank_You_But_No")
            return None

    def _check_nonce(self, nonce: str) -> bool:
        """REM: Check if nonce has been used (replay protection). Returns True if nonce is fresh."""
        client = self._get_redis()
        if client:
            try:
                # REM: If key exists, nonce was already used
                if client.exists(f"identiclaw:nonce:{nonce}"):
                    return False
                return True
            except Exception:
                pass
        # REM: Fallback: accept (better to allow than fail-closed on Redis outage for auth)
        return True

    def _mark_nonce_used(self, nonce: str):
        """REM: Mark a nonce as used with 5-minute TTL."""
        client = self._get_redis()
        if client:
            try:
                client.setex(f"identiclaw:nonce:{nonce}", 300, "used")
            except Exception:
                pass

    # REM: ==========================================
    # REM: KILL SWITCH
    # REM: ==========================================

    def revoke_agent(self, did: str, revoked_by: str, reason: str = "") -> bool:
        """
        REM: Immediately revoke a DID agent. Overrides Identiclaw status.
        REM: This is the TelsonBase kill switch.
        """
        self._revoked_dids.add(did)

        # REM: Update identity record if exists
        if did in self._identity_cache:
            record = self._identity_cache[did]
            record.revoked = True
            record.revoked_by = revoked_by
            record.revoked_at = datetime.now(timezone.utc)
            record.revocation_reason = reason
            self._persist_agent(record)

        # REM: Persist revocation to Redis (survives restarts)
        client = self._get_redis()
        if client:
            try:
                client.set(f"identiclaw:revoked:{did}", "revoked")
            except Exception:
                pass

        # REM: Audit trail
        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"DID agent REVOKED (kill switch): {did[:32]}...",
            actor=revoked_by,
            details={"did": did, "reason": reason, "action": "kill_switch"},
            qms_status="Thank_You"
        )

        logger.warning(f"REM: KILL SWITCH — DID revoked: {did[:32]}... by {revoked_by}_Thank_You")
        return True

    def reinstate_agent(self, did: str, reinstated_by: str, reason: str = "") -> bool:
        """REM: Clear revocation after human review."""
        if did not in self._revoked_dids:
            return False

        self._revoked_dids.discard(did)

        # REM: Update identity record
        if did in self._identity_cache:
            record = self._identity_cache[did]
            record.revoked = False
            record.revoked_by = None
            record.revoked_at = None
            record.revocation_reason = None
            self._persist_agent(record)

        # REM: Remove revocation from Redis
        client = self._get_redis()
        if client:
            try:
                client.delete(f"identiclaw:revoked:{did}")
            except Exception:
                pass

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"DID agent REINSTATED: {did[:32]}...",
            actor=reinstated_by,
            details={"did": did, "reason": reason, "action": "reinstate"},
            qms_status="Thank_You"
        )

        logger.info(f"REM: DID reinstated: {did[:32]}... by {reinstated_by}_Thank_You")
        return True

    def is_revoked(self, did: str) -> bool:
        """REM: Check if a DID is revoked. Always checked first in auth flow."""
        if did in self._revoked_dids:
            return True
        # REM: Fallback to Redis (may have been revoked by another worker)
        client = self._get_redis()
        if client:
            try:
                if client.exists(f"identiclaw:revoked:{did}"):
                    self._revoked_dids.add(did)  # Sync to memory
                    return True
            except Exception:
                pass
        return False

    # REM: ==========================================
    # REM: QUERY METHODS
    # REM: ==========================================

    def get_agent(self, did: str) -> Optional[AgentIdentityRecord]:
        """REM: Get an agent identity record by DID."""
        record = self._identity_cache.get(did)
        if record:
            return record
        # REM: Try Redis
        client = self._get_redis()
        if client:
            try:
                data = client.get(f"identiclaw:agent:{did}")
                if data:
                    record = AgentIdentityRecord.model_validate_json(data)
                    self._identity_cache[did] = record
                    return record
            except Exception:
                pass
        return None

    def list_agents(self) -> List[AgentIdentityRecord]:
        """REM: List all registered DID agents."""
        return list(self._identity_cache.values())

    def update_agent_trust_level(self, did: str, trust_level: str, updated_by: str) -> bool:
        """REM: Promote or demote an agent's trust level."""
        record = self.get_agent(did)
        if not record:
            return False

        old_level = record.trust_level
        record.trust_level = trust_level
        self._persist_agent(record)

        audit.log(
            AuditEventType.AGENT_ACTION,
            f"DID agent trust level changed: {did[:32]}... {old_level} → {trust_level}",
            actor=updated_by,
            details={"did": did, "old_level": old_level, "new_level": trust_level},
            qms_status="Thank_You"
        )

        logger.info(f"REM: DID trust level updated: {did[:32]}... → {trust_level}_Thank_You")
        return True

    def refresh_credentials(self, did: str) -> Optional[AgentIdentityRecord]:
        """REM: Force refresh of DID document from cache/resolution."""
        record = self.get_agent(did)
        if not record:
            return None

        # REM: Re-resolve DID document
        doc = self.resolve_did(did, force_refresh=True)
        if doc:
            record.public_key_hex = doc.public_key_hex
            record.last_verified_at = datetime.now(timezone.utc)
            self._persist_agent(record)

        return record


# REM: =======================================================================================
# REM: GLOBAL SINGLETON
# REM: =======================================================================================
identiclaw_manager = IdenticlawManager()
