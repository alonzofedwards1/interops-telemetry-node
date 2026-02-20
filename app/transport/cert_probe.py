import hashlib
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID


@dataclass
class CertInfo:
    subject_cn: Optional[str]
    subject_san: Optional[str]
    issuer_cn: Optional[str]
    not_before: Optional[datetime]
    not_after: Optional[datetime]
    serial: Optional[str]
    sha256: Optional[str]
    status: str  # e.g. VALID / EXPIRED / NOT_YET_VALID / UNREACHABLE / TLS_ERROR / NOT_PRESENT


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def probe_server_cert(host: str, port: int, timeout_sec: int = 5) -> CertInfo:
    """
    Fetch the peer TLS certificate from host:port WITHOUT requiring it to be trusted.
    This is important for dev/self-signed environments.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # we want the cert even if untrusted

    try:
        with socket.create_connection((host, port), timeout=timeout_sec) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                der = ssock.getpeercert(binary_form=True)

        if not der:
            return CertInfo(None, None, None, None, None, None, None, "NOT_PRESENT")

        cert = x509.load_der_x509_certificate(der, default_backend())

        # Subject CN
        subject_cn = None
        attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if attrs:
            subject_cn = attrs[0].value

        # Issuer CN
        issuer_cn = None
        iattrs = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        if iattrs:
            issuer_cn = iattrs[0].value

        # SANs
        san_text = None
        try:
            sans = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            values = []
            for name in sans:
                # DNSName / IPAddress / etc.
                values.append(str(name.value))
            san_text = ", ".join(values) if values else None
        except Exception:
            san_text = None

        not_before = _utc(cert.not_valid_before)
        not_after = _utc(cert.not_valid_after)

        sha256 = hashlib.sha256(der).hexdigest()
        serial = hex(cert.serial_number)

        now = datetime.now(timezone.utc)
        if now < not_before:
            status = "NOT_YET_VALID"
        elif now > not_after:
            status = "EXPIRED"
        else:
            status = "VALID"

        return CertInfo(
            subject_cn=subject_cn,
            subject_san=san_text,
            issuer_cn=issuer_cn,
            not_before=not_before,
            not_after=not_after,
            serial=serial,
            sha256=sha256,
            status=status,
        )

    except (socket.timeout, ConnectionRefusedError, OSError):
        return CertInfo(None, None, None, None, None, None, None, "UNREACHABLE")
    except ssl.SSLError:
        return CertInfo(None, None, None, None, None, None, None, "TLS_ERROR")
