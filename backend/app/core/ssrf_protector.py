import ipaddress
import socket
from urllib.parse import urlparse
from fastapi import HTTPException

# Förbjudna nätverksintervall enligt säkerhetsmanual Sektion 7.3
BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("10.0.0.0/8"),  # RFC 1918 Privat
    ipaddress.ip_network("172.16.0.0/12"),  # RFC 1918 Privat
    ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918 Privat
    ipaddress.ip_network("169.254.0.0/16"),  # Link-Local / Molnmetadata (AWS/GCP/Azure)
    ipaddress.ip_network("::1/128"),  # IPv6 Loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 Unique Local
    ipaddress.ip_network("fe80::/10"),  # IPv6 Link-Local
]


class SSRFProtectionError(HTTPException):
    def __init__(self, detail: str = "BLOCKED_DESTINATION"):
        super().__init__(status_code=400, detail=detail)


def is_ip_blocked(ip_str: str) -> bool:
    """Kontrollerar om en specifik IP-adress tillhör ett förbjudet/internt intervall."""
    try:
        ip = ipaddress.ip_address(ip_str)
        for net in BLOCKED_NETWORKS:
            if ip in net:
                return True
        return False
    except ValueError:
        return True


def validate_target_url(url: str) -> str:
    """
    Validerar måladressen och dess upplösta IP-adresser mot SSRF-blocklistan.
    Avvisar anslutningar till lokala nätverk, molnmetadata (169.254.169.254) och loopback.
    Kastar HTTP 400 BLOCKED_DESTINATION om adressen är blockerad.
    """
    if not url or not url.strip():
        raise SSRFProtectionError("BLOCKED_DESTINATION")

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise SSRFProtectionError("BLOCKED_DESTINATION")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFProtectionError("BLOCKED_DESTINATION")

    # Kontrollera om hostname är en direkt IP
    try:
        if is_ip_blocked(hostname):
            raise SSRFProtectionError("BLOCKED_DESTINATION")
    except Exception:
        pass

    # Lös upp värdnamnet mot DNS för att förhindra DNS rebinding / alternativa representationer
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for item in addr_info:
            ip_str = str(item[4][0])
            if is_ip_blocked(ip_str):
                raise SSRFProtectionError("BLOCKED_DESTINATION")
    except socket.gaierror:
        # Om värdnamnet inte kan slås upp godkänns det inte
        raise SSRFProtectionError("BLOCKED_DESTINATION")

    return url
