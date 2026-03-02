# TelsonBase/federation/mtls.py
# REM: =======================================================================================
# REM: MUTUAL TLS FOR FEDERATION TRANSPORT SECURITY
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.2.0CC: New feature - Mutual TLS for federation
#
# REM: Mission Statement: Defense in depth for federation communication. Even if an
# REM: attacker obtains a session key, they cannot impersonate an instance without
# REM: the corresponding X.509 certificate.
#
# REM: Features:
# REM:   - Self-signed CA per instance
# REM:   - Instance certificates for mTLS
# REM:   - Certificate pinning for known peers
# REM:   - Certificate revocation list (CRL)
# REM: =======================================================================================

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import base64

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


@dataclass
class CertificateInfo:
    """REM: Information about a certificate."""
    subject: str
    issuer: str
    serial_number: int
    not_valid_before: datetime
    not_valid_after: datetime
    fingerprint_sha256: str
    is_ca: bool = False
    is_revoked: bool = False


@dataclass
class PinnedCertificate:
    """REM: A pinned certificate for a known peer."""
    instance_id: str
    fingerprint_sha256: str
    pinned_at: datetime
    pinned_by: str
    certificate_pem: bytes


class FederationTLSManager:
    """
    REM: Manages TLS certificates for federation mTLS.
    """

    def __init__(self, instance_id: str, organization_name: str):
        self.instance_id = instance_id
        self.organization_name = organization_name

        # REM: CA certificate and key
        self._ca_key: Optional[rsa.RSAPrivateKey] = None
        self._ca_cert: Optional[x509.Certificate] = None

        # REM: Instance certificate and key
        self._instance_key: Optional[rsa.RSAPrivateKey] = None
        self._instance_cert: Optional[x509.Certificate] = None

        # REM: Pinned peer certificates
        self._pinned_certs: Dict[str, PinnedCertificate] = {}

        # REM: Revoked certificates (by fingerprint)
        self._revoked_certs: set = set()

        # REM: Initialize CA and instance cert
        self._initialize_ca()
        self._initialize_instance_cert()

    def _initialize_ca(self):
        """REM: Generate a self-signed CA certificate for this instance."""
        # REM: Generate CA private key
        self._ca_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )

        # REM: Build CA certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.organization_name),
            x509.NameAttribute(NameOID.COMMON_NAME, f"{self.instance_id}-CA"),
        ])

        self._ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(self._ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))  # 10 years
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=0),
                critical=True
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    key_encipherment=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False
                ),
                critical=True
            )
            .sign(self._ca_key, hashes.SHA256(), default_backend())
        )

        logger.info(
            f"REM: CA certificate generated for ::{self.instance_id}::_Thank_You"
        )

    def _initialize_instance_cert(self):
        """REM: Generate instance certificate signed by our CA."""
        # REM: Generate instance private key
        self._instance_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # REM: Build instance certificate
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.organization_name),
            x509.NameAttribute(NameOID.COMMON_NAME, self.instance_id),
        ])

        self._instance_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self._ca_cert.subject)
            .public_key(self._instance_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))  # 1 year
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False
                ),
                critical=True
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    ExtendedKeyUsageOID.CLIENT_AUTH,
                    ExtendedKeyUsageOID.SERVER_AUTH,
                ]),
                critical=False
            )
            .sign(self._ca_key, hashes.SHA256(), default_backend())
        )

        logger.info(
            f"REM: Instance certificate generated for ::{self.instance_id}::_Thank_You"
        )

    def get_ca_certificate_pem(self) -> bytes:
        """REM: Get CA certificate in PEM format."""
        return self._ca_cert.public_bytes(serialization.Encoding.PEM)

    def get_instance_certificate_pem(self) -> bytes:
        """REM: Get instance certificate in PEM format."""
        return self._instance_cert.public_bytes(serialization.Encoding.PEM)

    def get_instance_key_pem(self, password: Optional[bytes] = None) -> bytes:
        """REM: Get instance private key in PEM format."""
        encryption = (
            serialization.BestAvailableEncryption(password)
            if password else serialization.NoEncryption()
        )
        return self._instance_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption
        )

    def get_certificate_fingerprint(self, cert_pem: bytes) -> str:
        """REM: Get SHA256 fingerprint of a certificate."""
        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        fingerprint = cert.fingerprint(hashes.SHA256())
        return fingerprint.hex().upper()

    def get_certificate_info(self, cert_pem: bytes) -> CertificateInfo:
        """REM: Parse certificate and extract information."""
        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())

        # REM: Check if CA
        try:
            bc = cert.extensions.get_extension_for_class(x509.BasicConstraints)
            is_ca = bc.value.ca
        except x509.ExtensionNotFound:
            is_ca = False

        fingerprint = self.get_certificate_fingerprint(cert_pem)

        return CertificateInfo(
            subject=cert.subject.rfc4514_string(),
            issuer=cert.issuer.rfc4514_string(),
            serial_number=cert.serial_number,
            not_valid_before=cert.not_valid_before_utc,
            not_valid_after=cert.not_valid_after_utc,
            fingerprint_sha256=fingerprint,
            is_ca=is_ca,
            is_revoked=fingerprint in self._revoked_certs
        )

    def verify_peer_certificate(
        self,
        cert_pem: bytes,
        expected_instance_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        REM: Verify a peer's certificate.

        Checks:
        1. Certificate is not expired
        2. Certificate is not revoked
        3. Certificate matches pinned fingerprint (if pinned)
        4. Certificate CN matches expected instance ID (if provided)

        Returns:
            Tuple of (valid, reason)
        """
        try:
            cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
            now = datetime.now(timezone.utc)

            # REM: Check expiration
            if now < cert.not_valid_before_utc:
                return False, "Certificate not yet valid"
            if now > cert.not_valid_after_utc:
                return False, "Certificate has expired"

            # REM: Check revocation
            fingerprint = self.get_certificate_fingerprint(cert_pem)
            if fingerprint in self._revoked_certs:
                return False, "Certificate has been revoked"

            # REM: Extract CN for instance ID
            cn = None
            for attr in cert.subject:
                if attr.oid == NameOID.COMMON_NAME:
                    cn = attr.value
                    break

            # REM: Check against expected instance ID
            if expected_instance_id and cn != expected_instance_id:
                return False, f"CN mismatch: expected {expected_instance_id}, got {cn}"

            # REM: Check against pinned certificate
            if cn and cn in self._pinned_certs:
                pinned = self._pinned_certs[cn]
                if pinned.fingerprint_sha256 != fingerprint:
                    logger.warning(
                        f"REM: Certificate fingerprint mismatch for ::{cn}:: - "
                        f"Possible MITM attack!_Thank_You_But_No"
                    )
                    return False, "Certificate fingerprint does not match pinned certificate"

            return True, "Certificate verified"

        except Exception as e:
            logger.error(f"REM: Certificate verification failed: {e}_Thank_You_But_No")
            return False, f"Verification error: {str(e)}"

    def pin_peer_certificate(
        self,
        instance_id: str,
        cert_pem: bytes,
        pinned_by: str = "system"
    ) -> bool:
        """
        REM: Pin a peer's certificate for future verification.

        Once pinned, only this exact certificate will be accepted
        for this instance ID (prevents certificate substitution attacks).
        """
        fingerprint = self.get_certificate_fingerprint(cert_pem)

        self._pinned_certs[instance_id] = PinnedCertificate(
            instance_id=instance_id,
            fingerprint_sha256=fingerprint,
            pinned_at=datetime.now(timezone.utc),
            pinned_by=pinned_by,
            certificate_pem=cert_pem
        )

        logger.info(
            f"REM: Certificate pinned for ::{instance_id}:: "
            f"Fingerprint: ::{fingerprint[:16]}...::_Thank_You"
        )

        audit.log(
            AuditEventType.EXTERNAL_RESPONSE,
            f"Certificate pinned for federation peer: {instance_id}",
            actor=pinned_by,
            resource=instance_id,
            details={"fingerprint": fingerprint},
            qms_status="Thank_You"
        )

        return True

    def unpin_peer_certificate(
        self,
        instance_id: str,
        unpinned_by: str = "system"
    ) -> bool:
        """REM: Remove a pinned certificate."""
        if instance_id in self._pinned_certs:
            del self._pinned_certs[instance_id]

            logger.warning(
                f"REM: Certificate unpinned for ::{instance_id}::_Thank_You"
            )

            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Certificate unpinned for federation peer: {instance_id}",
                actor=unpinned_by,
                resource=instance_id,
                qms_status="Thank_You"
            )

            return True
        return False

    def revoke_certificate(
        self,
        fingerprint: str,
        revoked_by: str,
        reason: str
    ) -> bool:
        """REM: Add a certificate to the revocation list."""
        self._revoked_certs.add(fingerprint.upper())

        logger.warning(
            f"REM: Certificate revoked - Fingerprint: ::{fingerprint[:16]}...:: "
            f"Reason: ::{reason}::_Thank_You_But_No"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Certificate revoked: {fingerprint[:16]}...",
            actor=revoked_by,
            details={
                "fingerprint": fingerprint,
                "reason": reason
            },
            qms_status="Thank_You_But_No"
        )

        return True

    def get_pinned_peers(self) -> List[Dict[str, Any]]:
        """REM: Get list of all pinned peer certificates."""
        return [
            {
                "instance_id": p.instance_id,
                "fingerprint": p.fingerprint_sha256,
                "pinned_at": p.pinned_at.isoformat(),
                "pinned_by": p.pinned_by
            }
            for p in self._pinned_certs.values()
        ]

    def get_revoked_certificates(self) -> List[str]:
        """REM: Get list of revoked certificate fingerprints."""
        return list(self._revoked_certs)

    def export_trust_bundle(self) -> Dict[str, Any]:
        """
        REM: Export trust bundle for sharing with federation peers.

        Contains:
        - Our CA certificate (for verifying our instance cert)
        - Our instance certificate
        - Instance ID and organization info
        """
        return {
            "instance_id": self.instance_id,
            "organization_name": self.organization_name,
            "ca_certificate_pem": base64.b64encode(self.get_ca_certificate_pem()).decode(),
            "instance_certificate_pem": base64.b64encode(self.get_instance_certificate_pem()).decode(),
            "ca_fingerprint": self.get_certificate_fingerprint(self.get_ca_certificate_pem()),
            "instance_fingerprint": self.get_certificate_fingerprint(self.get_instance_certificate_pem()),
            "exported_at": datetime.now(timezone.utc).isoformat()
        }

    def import_peer_trust_bundle(
        self,
        bundle: Dict[str, Any],
        imported_by: str = "system",
        auto_pin: bool = True
    ) -> Tuple[bool, str]:
        """
        REM: Import a trust bundle from a federation peer.

        Optionally pins the certificate for future verification.
        """
        try:
            instance_id = bundle.get("instance_id")
            if not instance_id:
                return False, "Missing instance_id in bundle"

            cert_pem = base64.b64decode(bundle.get("instance_certificate_pem", ""))
            if not cert_pem:
                return False, "Missing instance_certificate_pem in bundle"

            # REM: Verify the certificate
            valid, reason = self.verify_peer_certificate(cert_pem, instance_id)
            if not valid:
                return False, f"Certificate verification failed: {reason}"

            # REM: Pin if requested
            if auto_pin:
                self.pin_peer_certificate(instance_id, cert_pem, imported_by)

            logger.info(
                f"REM: Trust bundle imported for ::{instance_id}::_Thank_You"
            )

            return True, f"Trust bundle imported for {instance_id}"

        except Exception as e:
            logger.error(f"REM: Failed to import trust bundle: {e}_Thank_You_But_No")
            return False, f"Import failed: {str(e)}"
