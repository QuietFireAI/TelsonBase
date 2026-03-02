# TelsonBase/federation/trust.py
# REM: =======================================================================================
# REM: FEDERATED TRUST PROTOCOL FOR CROSS-INSTANCE COMMUNICATION
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Enable secure agent collaboration between separate TelsonBase
# REM: instances operated by different organizations. Example: Law Firm A and Law Firm B
# REM: working on a shared case, each maintaining data sovereignty while their agents
# REM: can collaborate.
# REM:
# REM: Trust Model:
# REM:   - No shared cloud infrastructure
# REM:   - Each instance maintains its own data
# REM:   - Cross-instance messages are encrypted and signed
# REM:   - Trust is explicitly established and can be revoked instantly
# REM:   - All cross-instance communication is audited on both ends
# REM:
# REM: Protocol Flow:
# REM:   1. Instance A sends trust invitation to Instance B
# REM:   2. Instance B reviews and accepts (or rejects)
# REM:   3. Instances exchange public keys
# REM:   4. Agents can now send signed, encrypted messages across instances
# REM:   5. Either instance can revoke trust at any time
# REM:
# REM: v4.1.0CC: Fixed session key exchange using RSA encryption
# REM:           Added Redis persistence for trust relationships
# REM: =======================================================================================

import os
import json
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from cryptography import exceptions
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from pydantic import BaseModel, Field
import base64

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)

# REM: Import persistence store (lazy to avoid circular imports)
_federation_store = None

def _get_store():
    """REM: Lazy-load the federation store to avoid circular imports."""
    global _federation_store
    if _federation_store is None:
        try:
            from core.persistence import federation_store
            _federation_store = federation_store
        except Exception as e:
            logger.warning(f"REM: Redis persistence unavailable, using in-memory: {e}")
            _federation_store = False
    return _federation_store if _federation_store else None


class TrustStatus(str, Enum):
    """REM: Status of trust relationship between instances."""
    PENDING_OUTBOUND = "pending_outbound"  # We sent invitation, waiting for response
    PENDING_INBOUND = "pending_inbound"    # We received invitation, need to decide
    ESTABLISHED = "established"             # Mutual trust active
    REVOKED = "revoked"                     # Trust revoked (by either party)
    EXPIRED = "expired"                     # Trust expired
    REJECTED = "rejected"                   # Invitation was rejected


class TrustLevel(str, Enum):
    """REM: Levels of trust that can be granted."""
    MINIMAL = "minimal"        # Can only exchange basic status
    STANDARD = "standard"      # Can exchange agent messages
    ELEVATED = "elevated"      # Can request task execution
    FULL = "full"             # Full collaboration (rare, requires approval)


@dataclass
class InstanceIdentity:
    """
    REM: Cryptographic identity of an TelsonBase instance.
    """
    instance_id: str
    organization_name: str
    
    # REM: Cryptographic keys
    public_key_pem: bytes
    
    # REM: Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "2.0.0"
    
    def fingerprint(self) -> str:
        """REM: Generate short fingerprint of public key for verification."""
        return hashlib.sha256(self.public_key_pem).hexdigest()[:16].upper()
    
    def to_dict(self) -> Dict:
        return {
            "instance_id": self.instance_id,
            "organization_name": self.organization_name,
            "public_key_pem": base64.b64encode(self.public_key_pem).decode(),
            "created_at": self.created_at.isoformat(),
            "version": self.version,
            "fingerprint": self.fingerprint()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "InstanceIdentity":
        return cls(
            instance_id=data["instance_id"],
            organization_name=data["organization_name"],
            public_key_pem=base64.b64decode(data["public_key_pem"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            version=data.get("version", "unknown")
        )


@dataclass
class TrustRelationship:
    """
    REM: A trust relationship between this instance and another.
    """
    relationship_id: str
    
    # REM: The remote instance
    remote_identity: InstanceIdentity
    
    # REM: Trust configuration
    trust_level: TrustLevel
    status: TrustStatus
    
    # REM: Allowed agent communications (glob patterns)
    allowed_agents: List[str] = field(default_factory=lambda: ["*"])
    allowed_actions: List[str] = field(default_factory=lambda: ["message", "query"])
    
    # REM: Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    established_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    
    # REM: Session key for encrypted communication (established during handshake)
    session_key: Optional[bytes] = field(default=None, repr=False)
    
    # REM: Statistics
    messages_sent: int = 0
    messages_received: int = 0
    last_activity: Optional[datetime] = None


@dataclass
class FederatedMessage:
    """
    REM: A message sent between federated instances.
    REM: FIXED v3.0.1: Reordered fields - non-defaults must precede defaults in dataclasses.
    """
    # REM: Required fields (no defaults) - MUST come first per Python dataclass rules
    message_id: str
    source_instance_id: str
    target_instance_id: str
    source_agent_id: str
    action: str
    encrypted_payload: bytes = field(repr=False)
    signature: bytes = field(repr=False)
    nonce: bytes = field(repr=False)
    
    # REM: Optional fields (have defaults) - MUST come last
    target_agent_id: Optional[str] = None  # None = broadcast to instance
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reply_to: Optional[str] = None
    
    def to_wire_format(self) -> bytes:
        """REM: Serialize for transmission."""
        data = {
            "message_id": self.message_id,
            "source_instance_id": self.source_instance_id,
            "target_instance_id": self.target_instance_id,
            "source_agent_id": self.source_agent_id,
            "target_agent_id": self.target_agent_id,
            "action": self.action,
            "encrypted_payload": base64.b64encode(self.encrypted_payload).decode(),
            "signature": base64.b64encode(self.signature).decode(),
            "nonce": base64.b64encode(self.nonce).decode(),
            "timestamp": self.timestamp.isoformat(),
            "reply_to": self.reply_to
        }
        return json.dumps(data).encode()
    
    @classmethod
    def from_wire_format(cls, data: bytes) -> "FederatedMessage":
        """REM: Deserialize from transmission."""
        parsed = json.loads(data)
        return cls(
            message_id=parsed["message_id"],
            source_instance_id=parsed["source_instance_id"],
            target_instance_id=parsed["target_instance_id"],
            source_agent_id=parsed["source_agent_id"],
            target_agent_id=parsed.get("target_agent_id"),
            action=parsed["action"],
            encrypted_payload=base64.b64decode(parsed["encrypted_payload"]),
            signature=base64.b64decode(parsed["signature"]),
            nonce=base64.b64decode(parsed["nonce"]),
            timestamp=datetime.fromisoformat(parsed["timestamp"]),
            reply_to=parsed.get("reply_to")
        )


class FederationManager:
    """
    REM: Manages trust relationships and federated communication.
    REM: v4.1.0CC: Now persists relationships to Redis (excluding session keys).
    """

    def __init__(self, instance_id: str, organization_name: str):
        self.instance_id = instance_id
        self.organization_name = organization_name

        # REM: Generate instance key pair
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )
        self._public_key = self._private_key.public_key()

        # REM: Create our identity
        public_key_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        self.identity = InstanceIdentity(
            instance_id=instance_id,
            organization_name=organization_name,
            public_key_pem=public_key_pem
        )

        # REM: Trust relationships
        self._relationships: Dict[str, TrustRelationship] = {}

        # REM: Message handlers
        self._message_handlers: Dict[str, callable] = {}

        # REM: Load relationships from persistence (without session keys)
        self._load_from_persistence()

        logger.info(
            f"REM: Federation Manager initialized for ::{instance_id}:: "
            f"({organization_name}) - Fingerprint: ::{self.identity.fingerprint()}::_Thank_You"
        )

    def _load_from_persistence(self):
        """REM: Load relationships from Redis on startup (session keys excluded)."""
        store = _get_store()
        if store:
            try:
                stored_rels = store.list_relationships()
                for rel_data in stored_rels:
                    # REM: Reconstruct relationship (without session key)
                    remote_identity = InstanceIdentity.from_dict(rel_data["remote_identity"])
                    relationship = TrustRelationship(
                        relationship_id=rel_data["relationship_id"],
                        remote_identity=remote_identity,
                        trust_level=TrustLevel(rel_data["trust_level"]),
                        status=TrustStatus(rel_data["status"]),
                        allowed_agents=rel_data.get("allowed_agents", ["*"]),
                        allowed_actions=rel_data.get("allowed_actions", ["message", "query"]),
                        created_at=datetime.fromisoformat(rel_data["created_at"]) if rel_data.get("created_at") else None,
                        established_at=datetime.fromisoformat(rel_data["established_at"]) if rel_data.get("established_at") else None,
                        messages_sent=rel_data.get("messages_sent", 0),
                        messages_received=rel_data.get("messages_received", 0)
                        # NOTE: session_key is NOT loaded - must be re-exchanged after restart
                    )
                    self._relationships[relationship.relationship_id] = relationship
                logger.info(f"REM: Loaded {len(self._relationships)} federation relationships from persistence_Thank_You")
                logger.warning(f"REM: Session keys must be re-exchanged after restart for established relationships")
            except Exception as e:
                logger.warning(f"REM: Failed to load relationships from persistence: {e}")
    
    def create_trust_invitation(
        self,
        trust_level: TrustLevel = TrustLevel.STANDARD,
        allowed_agents: List[str] = None,
        allowed_actions: List[str] = None,
        expires_in_hours: int = 72
    ) -> Dict:
        """
        REM: Create a trust invitation to send to another instance.
        REM: The invitation contains our identity and proposed trust terms.
        """
        invitation_id = f"INV-{secrets.token_hex(8).upper()}"
        
        invitation = {
            "invitation_id": invitation_id,
            "type": "trust_invitation",
            "version": "1.0",
            "from_identity": self.identity.to_dict(),
            "proposed_trust_level": trust_level.value,
            "proposed_allowed_agents": allowed_agents or ["*"],
            "proposed_allowed_actions": allowed_actions or ["message", "query"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)).isoformat()
        }
        
        # REM: Sign the invitation
        invitation_bytes = json.dumps(invitation, sort_keys=True).encode()
        signature = self._private_key.sign(
            invitation_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        invitation["signature"] = base64.b64encode(signature).decode()
        
        logger.info(
            f"REM: Trust invitation created ::{invitation_id}:: "
            f"Trust level ::{trust_level.value}::_Please"
        )
        
        audit.log(
            AuditEventType.EXTERNAL_REQUEST,
            f"Trust invitation created ::{invitation_id}::",
            actor=self.instance_id,
            details=invitation,
            qms_status="Please"
        )
        
        return invitation
    
    def process_trust_invitation(
        self,
        invitation: Dict,
        auto_accept: bool = False
    ) -> Tuple[bool, str, Optional[TrustRelationship]]:
        """
        REM: Process an incoming trust invitation.
        
        Returns:
            Tuple of (success, message, relationship if accepted)
        """
        try:
            # REM: Verify invitation structure
            required_fields = [
                "invitation_id", "from_identity", "proposed_trust_level",
                "signature", "expires_at"
            ]
            for field in required_fields:
                if field not in invitation:
                    return False, f"Missing required field: {field}", None
            
            # REM: Check expiration
            expires_at = datetime.fromisoformat(invitation["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                return False, "Invitation has expired", None
            
            # REM: Parse remote identity
            remote_identity = InstanceIdentity.from_dict(invitation["from_identity"])
            
            # REM: Verify signature
            signature = base64.b64decode(invitation["signature"])
            invitation_copy = {k: v for k, v in invitation.items() if k != "signature"}
            invitation_bytes = json.dumps(invitation_copy, sort_keys=True).encode()
            
            remote_public_key = serialization.load_pem_public_key(
                remote_identity.public_key_pem,
                backend=default_backend()
            )
            
            try:
                remote_public_key.verify(
                    signature,
                    invitation_bytes,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
            except (ValueError, TypeError, exceptions.InvalidSignature):
                logger.warning(
                    f"REM: Invalid signature on trust invitation from "
                    f"::{remote_identity.instance_id}::_Thank_You_But_No"
                )
                return False, "Invalid invitation signature", None
            
            # REM: Create pending relationship
            relationship_id = f"REL-{secrets.token_hex(8).upper()}"
            relationship = TrustRelationship(
                relationship_id=relationship_id,
                remote_identity=remote_identity,
                trust_level=TrustLevel(invitation["proposed_trust_level"]),
                status=TrustStatus.PENDING_INBOUND,
                allowed_agents=invitation.get("proposed_allowed_agents", ["*"]),
                allowed_actions=invitation.get("proposed_allowed_actions", ["message", "query"])
            )
            
            self._relationships[relationship_id] = relationship
            
            logger.info(
                f"REM: Trust invitation received from ::{remote_identity.organization_name}:: "
                f"({remote_identity.instance_id}) - Relationship ::{relationship_id}::_Please"
            )
            
            audit.log(
                AuditEventType.EXTERNAL_REQUEST,
                f"Trust invitation received from ::{remote_identity.organization_name}::",
                actor=remote_identity.instance_id,
                resource=relationship_id,
                details={
                    "remote_fingerprint": remote_identity.fingerprint(),
                    "proposed_trust_level": invitation["proposed_trust_level"]
                },
                qms_status="Please"
            )
            
            if auto_accept:
                success, message, rel, _session_key = self.accept_trust(relationship_id)
                return success, message, rel
            
            return True, f"Invitation pending review. Relationship ID: {relationship_id}", relationship
            
        except Exception as e:
            logger.error(f"REM: Failed to process trust invitation: {e}_Thank_You_But_No")
            return False, f"Failed to process invitation: {str(e)}", None
    
    def accept_trust(
        self,
        relationship_id: str,
        decided_by: str = "system"
    ) -> Tuple[bool, str, Optional[TrustRelationship], Optional[Dict]]:
        """
        REM: Accept a pending trust invitation.
        REM: v4.1.0CC: Returns encrypted session key for secure transmission.

        Returns:
            Tuple of (success, message, relationship, acceptance_response)
            The acceptance_response contains the encrypted session key to send back.
        """
        relationship = self._relationships.get(relationship_id)
        if not relationship:
            return False, "Relationship not found", None, None

        if relationship.status != TrustStatus.PENDING_INBOUND:
            return False, f"Relationship not in pending state: {relationship.status.value}", None, None

        # REM: Generate session key for encrypted communication
        session_key = AESGCM.generate_key(bit_length=256)
        relationship.session_key = session_key
        relationship.status = TrustStatus.ESTABLISHED
        relationship.established_at = datetime.now(timezone.utc)

        # REM: Encrypt session key with remote instance's public key (RSA-OAEP)
        remote_public_key = serialization.load_pem_public_key(
            relationship.remote_identity.public_key_pem,
            backend=default_backend()
        )

        encrypted_session_key = remote_public_key.encrypt(
            session_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        # REM: Create acceptance response to send back to the inviting instance
        acceptance_response = {
            "type": "trust_acceptance",
            "relationship_id": relationship_id,
            "from_identity": self.identity.to_dict(),
            "encrypted_session_key": base64.b64encode(encrypted_session_key).decode(),
            "accepted_at": relationship.established_at.isoformat(),
            "accepted_by": decided_by
        }

        # REM: Sign the acceptance response
        response_bytes = json.dumps(acceptance_response, sort_keys=True).encode()
        signature = self._private_key.sign(
            response_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        acceptance_response["signature"] = base64.b64encode(signature).decode()

        # REM: Persist the relationship to Redis
        self._persist_relationship(relationship)

        logger.info(
            f"REM: Trust relationship ::{relationship_id}:: ESTABLISHED with "
            f"::{relationship.remote_identity.organization_name}::_Thank_You"
        )

        audit.log(
            AuditEventType.EXTERNAL_RESPONSE,
            f"Trust established with ::{relationship.remote_identity.organization_name}::",
            actor=decided_by,
            resource=relationship_id,
            details={
                "remote_instance_id": relationship.remote_identity.instance_id,
                "trust_level": relationship.trust_level.value
            },
            qms_status="Thank_You"
        )

        return True, "Trust established", relationship, acceptance_response

    def process_trust_acceptance(self, acceptance: Dict) -> Tuple[bool, str]:
        """
        REM: Process a trust acceptance response from a remote instance.
        REM: v4.1.0CC: Extracts and stores the decrypted session key.
        """
        try:
            # REM: Verify required fields
            required = ["relationship_id", "from_identity", "encrypted_session_key", "signature"]
            for field in required:
                if field not in acceptance:
                    return False, f"Missing required field: {field}"

            # REM: Find the relationship
            relationship_id = acceptance["relationship_id"]
            relationship = self._relationships.get(relationship_id)
            if not relationship:
                return False, f"Unknown relationship: {relationship_id}"

            # REM: Verify signature
            signature = base64.b64decode(acceptance["signature"])
            acceptance_copy = {k: v for k, v in acceptance.items() if k != "signature"}
            acceptance_bytes = json.dumps(acceptance_copy, sort_keys=True).encode()

            remote_public_key = serialization.load_pem_public_key(
                relationship.remote_identity.public_key_pem,
                backend=default_backend()
            )

            try:
                remote_public_key.verify(
                    signature,
                    acceptance_bytes,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
            except Exception:
                return False, "Invalid acceptance signature"

            # REM: Decrypt the session key using our private key
            encrypted_session_key = base64.b64decode(acceptance["encrypted_session_key"])
            session_key = self._private_key.decrypt(
                encrypted_session_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            # REM: Update relationship with session key
            relationship.session_key = session_key
            relationship.status = TrustStatus.ESTABLISHED
            relationship.established_at = datetime.now(timezone.utc)

            # REM: Persist the relationship
            self._persist_relationship(relationship)

            logger.info(
                f"REM: Trust acceptance processed for ::{relationship_id}:: - "
                f"Session key established_Thank_You"
            )

            return True, "Trust acceptance processed successfully"

        except Exception as e:
            logger.error(f"REM: Failed to process trust acceptance: {e}_Thank_You_But_No")
            return False, f"Failed to process acceptance: {str(e)}"

    def _persist_relationship(self, relationship: TrustRelationship):
        """REM: Persist a relationship to Redis."""
        store = _get_store()
        if store:
            try:
                rel_dict = {
                    "relationship_id": relationship.relationship_id,
                    "remote_identity": relationship.remote_identity.to_dict(),
                    "trust_level": relationship.trust_level.value,
                    "status": relationship.status.value,
                    "allowed_agents": relationship.allowed_agents,
                    "allowed_actions": relationship.allowed_actions,
                    "created_at": relationship.created_at.isoformat(),
                    "established_at": relationship.established_at.isoformat() if relationship.established_at else None,
                    "expires_at": relationship.expires_at.isoformat() if relationship.expires_at else None,
                    "messages_sent": relationship.messages_sent,
                    "messages_received": relationship.messages_received
                    # NOTE: session_key is NOT persisted for security reasons
                }
                store.store_relationship(rel_dict)
            except Exception as e:
                logger.warning(f"REM: Failed to persist relationship: {e}")
    
    def revoke_trust(
        self,
        relationship_id: str,
        reason: str,
        revoked_by: str = "system"
    ) -> bool:
        """
        REM: Immediately revoke a trust relationship.
        REM: No further messages will be accepted from the remote instance.
        """
        relationship = self._relationships.get(relationship_id)
        if not relationship:
            return False

        relationship.status = TrustStatus.REVOKED
        relationship.revoked_at = datetime.now(timezone.utc)
        relationship.session_key = None  # Destroy session key

        # REM: Persist the revocation
        self._persist_relationship(relationship)

        logger.warning(
            f"REM: Trust relationship ::{relationship_id}:: REVOKED - "
            f"Remote: ::{relationship.remote_identity.organization_name}:: - "
            f"Reason: ::{reason}::_Thank_You_But_No"
        )

        audit.log(
            AuditEventType.EXTERNAL_BLOCKED,
            f"Trust revoked for ::{relationship.remote_identity.organization_name}::",
            actor=revoked_by,
            resource=relationship_id,
            details={"reason": reason},
            qms_status="Thank_You_But_No"
        )

        return True
    
    def send_message(
        self,
        relationship_id: str,
        source_agent_id: str,
        action: str,
        payload: Dict[str, Any],
        target_agent_id: Optional[str] = None
    ) -> Optional[FederatedMessage]:
        """
        REM: Send an encrypted, signed message to a federated instance.
        """
        relationship = self._relationships.get(relationship_id)
        if not relationship or relationship.status != TrustStatus.ESTABLISHED:
            logger.error(f"REM: Cannot send - no active trust relationship ::{relationship_id}::")
            return None
        
        if not relationship.session_key:
            logger.error(f"REM: Cannot send - no session key for ::{relationship_id}::")
            return None
        
        # REM: Encrypt payload
        aesgcm = AESGCM(relationship.session_key)
        nonce = os.urandom(12)
        payload_bytes = json.dumps(payload).encode()
        encrypted_payload = aesgcm.encrypt(nonce, payload_bytes, None)
        
        # REM: Create message
        message_id = f"MSG-{secrets.token_hex(8).upper()}"
        
        message = FederatedMessage(
            message_id=message_id,
            source_instance_id=self.instance_id,
            target_instance_id=relationship.remote_identity.instance_id,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            action=action,
            encrypted_payload=encrypted_payload,
            nonce=nonce,
            signature=b""  # Will be set below
        )
        
        # REM: Sign the message
        message_to_sign = f"{message_id}:{self.instance_id}:{action}:{message.timestamp.isoformat()}"
        signature = self._private_key.sign(
            message_to_sign.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        message.signature = signature
        
        # REM: Update statistics
        relationship.messages_sent += 1
        relationship.last_activity = datetime.now(timezone.utc)
        
        logger.info(
            f"REM: Federated message ::{message_id}:: sent to "
            f"::{relationship.remote_identity.organization_name}:: "
            f"Action ::{action}::_Please"
        )
        
        audit.log(
            AuditEventType.EXTERNAL_REQUEST,
            f"Federated message sent to ::{relationship.remote_identity.organization_name}::",
            actor=source_agent_id,
            resource=message_id,
            details={
                "action": action,
                "target_agent": target_agent_id,
                "relationship_id": relationship_id
            },
            qms_status="Please"
        )
        
        return message
    
    def receive_message(
        self,
        wire_data: bytes
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        REM: Process an incoming federated message.
        REM: Verifies signature, decrypts payload, and validates trust.
        
        Returns:
            Tuple of (success, message/error, decrypted payload if successful)
        """
        try:
            message = FederatedMessage.from_wire_format(wire_data)
        except Exception as e:
            return False, f"Failed to parse message: {e}", None
        
        # REM: Find the trust relationship
        relationship = None
        for rel in self._relationships.values():
            if rel.remote_identity.instance_id == message.source_instance_id:
                relationship = rel
                break
        
        if not relationship:
            logger.warning(
                f"REM: Message from unknown instance ::{message.source_instance_id}::_Thank_You_But_No"
            )
            return False, "No trust relationship with source instance", None
        
        if relationship.status != TrustStatus.ESTABLISHED:
            logger.warning(
                f"REM: Message from non-trusted instance ::{message.source_instance_id}:: "
                f"Status ::{relationship.status.value}::_Thank_You_But_No"
            )
            return False, f"Trust relationship not active: {relationship.status.value}", None
        
        # REM: Verify signature
        remote_public_key = serialization.load_pem_public_key(
            relationship.remote_identity.public_key_pem,
            backend=default_backend()
        )
        
        message_to_verify = f"{message.message_id}:{message.source_instance_id}:{message.action}:{message.timestamp.isoformat()}"
        
        try:
            remote_public_key.verify(
                message.signature,
                message_to_verify.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        except Exception:
            logger.warning(
                f"REM: Invalid signature on federated message ::{message.message_id}::_Thank_You_But_No"
            )
            return False, "Invalid message signature", None
        
        # REM: Decrypt payload
        if not relationship.session_key:
            return False, "No session key available", None
        
        try:
            aesgcm = AESGCM(relationship.session_key)
            decrypted_bytes = aesgcm.decrypt(message.nonce, message.encrypted_payload, None)
            payload = json.loads(decrypted_bytes)
        except Exception as e:
            logger.error(f"REM: Failed to decrypt message: {e}_Thank_You_But_No")
            return False, "Failed to decrypt message", None
        
        # REM: Update statistics
        relationship.messages_received += 1
        relationship.last_activity = datetime.now(timezone.utc)
        
        logger.info(
            f"REM: Federated message ::{message.message_id}:: received from "
            f"::{relationship.remote_identity.organization_name}:: "
            f"Action ::{message.action}::_Thank_You"
        )
        
        audit.log(
            AuditEventType.EXTERNAL_RESPONSE,
            f"Federated message received from ::{relationship.remote_identity.organization_name}::",
            actor=message.source_agent_id,
            resource=message.message_id,
            details={
                "action": message.action,
                "source_agent": message.source_agent_id,
                "target_agent": message.target_agent_id
            },
            qms_status="Thank_You"
        )
        
        return True, "Message received and verified", {
            "message_id": message.message_id,
            "source_instance": message.source_instance_id,
            "source_agent": message.source_agent_id,
            "action": message.action,
            "payload": payload,
            "timestamp": message.timestamp.isoformat()
        }
    
    def get_relationship_status(self, relationship_id: str) -> Optional[Dict]:
        """REM: Get status of a trust relationship."""
        relationship = self._relationships.get(relationship_id)
        if not relationship:
            return None
        
        return {
            "relationship_id": relationship_id,
            "remote_instance": relationship.remote_identity.instance_id,
            "remote_organization": relationship.remote_identity.organization_name,
            "remote_fingerprint": relationship.remote_identity.fingerprint(),
            "trust_level": relationship.trust_level.value,
            "status": relationship.status.value,
            "established_at": relationship.established_at.isoformat() if relationship.established_at else None,
            "messages_sent": relationship.messages_sent,
            "messages_received": relationship.messages_received,
            "last_activity": relationship.last_activity.isoformat() if relationship.last_activity else None
        }
    
    def list_relationships(self, status: Optional[TrustStatus] = None) -> List[Dict]:
        """REM: List all trust relationships."""
        results = []
        for rel_id, rel in self._relationships.items():
            if status and rel.status != status:
                continue
            results.append(self.get_relationship_status(rel_id))
        return results


# REM: =======================================================================================
# REM: SINGLETON FACTORY — Ensures consistent identity across API calls
# REM: =======================================================================================
# REM: v5.1.0CC fix: FederationManager MUST be a singleton so RSA keys persist
# REM: across requests. Without this, every API call generates a new identity.

_federation_manager_instance: Optional[FederationManager] = None


def get_federation_manager() -> FederationManager:
    """
    REM: Get or create the singleton FederationManager.
    REM: Ensures the same RSA key pair is used for all federation operations.
    """
    global _federation_manager_instance
    if _federation_manager_instance is None:
        instance_id = os.environ.get("INSTANCE_ID", f"instance-{os.urandom(4).hex()}")
        org_name = os.environ.get("ORGANIZATION_NAME", "Quietfire AI TelsonBase")
        _federation_manager_instance = FederationManager(instance_id, org_name)
    return _federation_manager_instance
