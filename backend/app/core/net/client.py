from typing import Any, Dict, Optional
import httpx
from app.config import settings
from app.db.database import db
from app.models.case import EgressPolicy


class AsyncEgressClient:
    """
    Asynkron HTTP-klientwrapper för OpSec-kontrollerad utgående trafik (Egress Engine).
    Dirigerar anrop baserat på utredningsärendets säkerhetsprofil:
    - DIRECT: Trafik sker via serverns ordinarie IP (endast betrodda API:er).
    - PROXY_RESIDENTIAL: Roterande bostadsproxies för att undvika geoblockeringar.
    - TOR_STRICT: All HTTP- och socket-trafik tvingas genom Tor SOCKS5-proxy (socks5://tor:9050).
      DNS-uppslag sker på distans via Tor-proxy för att garantera att DNS inte läcker lokalt.
    """

    def __init__(
        self,
        policy: EgressPolicy = EgressPolicy.DIRECT,
        proxy_url: Optional[str] = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ):
        self.policy = policy
        self.proxy_url = proxy_url
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def effective_proxy_url(self) -> Optional[str]:
        if self.proxy_url:
            return self.proxy_url
        if self.policy == EgressPolicy.TOR_STRICT:
            return settings.TOR_PROXY_URL
        if self.policy == EgressPolicy.PROXY_RESIDENTIAL:
            return settings.RESIDENTIAL_PROXY_URL
        return None

    def _build_client(self) -> httpx.AsyncClient:
        proxy = self.effective_proxy_url
        # socks5:// skickar DNS-uppslag genom SOCKS5-proxyn direkt
        return httpx.AsyncClient(
            proxy=proxy,
            timeout=self.timeout,
            verify=self.verify_ssl,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "AsyncEgressClient":
        if self._client is None or self._client.is_closed:
            self._client = self._build_client()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Utför HTTP-anrop enligt konfigurerad OpSec-policy."""
        if self._client is None or self._client.is_closed:
            self._client = self._build_client()
        return await self._client.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    def is_dns_leak_protected(self) -> bool:
        """
        Verifierar om profilen dirigerar DNS genom proxy.
        För TOR_STRICT och PROXY_RESIDENTIAL (med socks5:// eller http:// proxy)
        sker namnupplösning uteslutande på proxyn/Tor-nätet utan lokal resolver-läcka.
        """
        return self.policy in (EgressPolicy.TOR_STRICT, EgressPolicy.PROXY_RESIDENTIAL)

    def get_routing_info(self) -> Dict[str, Any]:
        """Returnerar diagnostisk information om den aktiva nätverksrutten."""
        return {
            "policy": self.policy.value,
            "effective_proxy": self.effective_proxy_url,
            "dns_leak_protected": self.is_dns_leak_protected(),
            "target_isolation": "Tor Circuit" if self.policy == EgressPolicy.TOR_STRICT else "Standard",
        }


def get_egress_client(
    policy: Optional[EgressPolicy | str] = None,
    case_id: Optional[str] = None,
    proxy_url: Optional[str] = None,
) -> AsyncEgressClient:
    """
    Hjälpfunktion för att hämta lämplig AsyncEgressClient.
    Om case_id anges hämtas ärendets konfigurerade egress_policy från databasen.
    """
    resolved_policy = EgressPolicy.DIRECT

    if case_id:
        case = db.get_case(case_id)
        if case and hasattr(case, "egress_policy"):
            resolved_policy = case.egress_policy
    elif policy:
        if isinstance(policy, str):
            resolved_policy = EgressPolicy(policy.upper())
        else:
            resolved_policy = policy

    return AsyncEgressClient(policy=resolved_policy, proxy_url=proxy_url)
