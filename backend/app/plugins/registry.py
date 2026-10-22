import importlib
import inspect
from pathlib import Path
import pkgutil
from typing import Any, Dict, List, Optional
from .base import BaseOSINTPlugin, EntityInput, PluginResult


class PluginManager:
    """
    Dynamisk plugin-laddare och hanterare (Plugin Registry).
    Söker igenom plugin-kataloger, instansierar tillgängliga plugins och
    tillhandahåller gränssnitt för att lista och köra transforms.
    """

    def __init__(self):
        self._plugins: Dict[str, BaseOSINTPlugin] = {}
        self.discover_plugins()

    def register(self, plugin: BaseOSINTPlugin):
        """Registrerar en plugin-instans i katalogen under dess plugin_id och slug."""
        if getattr(plugin, "plugin_id", None):
            self._plugins[plugin.plugin_id] = plugin
        if getattr(plugin, "slug", None):
            self._plugins[plugin.slug] = plugin

    def get_plugin(self, slug_or_id: str) -> Optional[BaseOSINTPlugin]:
        """Hämtar ett plugin via dess unika slug eller plugin_id."""
        return self._plugins.get(slug_or_id)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Listar metadata för samtliga registrerade plugins utan dubbletter."""
        seen = set()
        result = []
        for p in self._plugins.values():
            key = getattr(p, "plugin_id", "") or getattr(p, "slug", "")
            if key in seen:
                continue
            seen.add(key)
            result.append(
                {
                    "plugin_id": getattr(p, "plugin_id", p.slug),
                    "name": p.name,
                    "category": p.category.value if hasattr(p.category, "value") else str(p.category),
                    "nato_admiralty": getattr(p, "nato_admiralty", "A1"),
                    "requires_api_key": getattr(p, "requires_api_key", False),
                    "cost_per_query_usd": getattr(p, "cost_per_query_usd", 0.0),
                    "supported_entity_types": getattr(p, "supported_entity_types", p.supported_inputs),
                    "slug": p.slug,
                    "description": p.description,
                    "version": p.version,
                    "required_vault_key": p.required_vault_key,
                    "is_commercial": p.is_commercial,
                    "cost_per_query_estimate": p.cost_per_query_estimate,
                    "supported_inputs": p.supported_inputs,
                    "output_entities": p.output_entities,
                    "rate_limit_per_minute": p.rate_limit_per_minute,
                    "supports_proxy": p.supports_proxy,
                }
            )
        return result

    def get_plugins_for_input(self, entity_type: str) -> List[BaseOSINTPlugin]:
        """Filtrerar ut unika plugins som stödjer en given entitetstyp."""
        cleaned = entity_type.strip().lower()
        seen = set()
        matched = []
        for p in self._plugins.values():
            key = getattr(p, "plugin_id", "") or getattr(p, "slug", "")
            if key in seen:
                continue
            types_lower = [t.lower() for t in (getattr(p, "supported_entity_types", None) or p.supported_inputs)]
            if cleaned in types_lower or "*" in types_lower:
                seen.add(key)
                matched.append(p)
        return matched

    get_plugins_for_type = get_plugins_for_input

    async def execute_plugin(
        self,
        slug_or_id: str,
        target: EntityInput,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> PluginResult:
        """Kör ett namngivet plugin mot målet."""
        plugin = self.get_plugin(slug_or_id)
        if not plugin:
            raise ValueError(f"Plugin med identifierare '{slug_or_id}' hittades inte.")
        return await plugin.execute(target, api_key=api_key, proxy_url=proxy_url)

    def discover_plugins(self, package_path: Optional[str] = None):
        """
        Söker och registrerar inbyggda plugins samt skannar kataloger.
        """
        # 1. Rot-plugins
        from .shodan_plugin import ShodanPlugin
        from .virustotal_plugin import VirusTotalPlugin
        from .whois_plugin import WhoisPlugin

        # 2. SOCMINT
        from .socmint.gravatar_probe import GravatarProbe
        from .socmint.pgp_keyserver_probe import PGPKeyserverProbe
        from .socmint.whatsmyname_probe import WhatsMyNameProbe

        # 3. FINMINT
        from .finmint.bolagsverket_plugin import BolagsverketPlugin
        from .finmint.crypto_mempool_plugin import CryptoMempoolPlugin
        from .finmint.opencorporates_plugin import OpenCorporatesPlugin
        from .finmint.opensanctions_plugin import OpenSanctionsPlugin

        # 4. CTI
        from .cti.crtsh_subdomains import CrtshSubdomainsPlugin
        from .cti.doh_dns_probe import DoHDNSProbePlugin
        from .cti.ripestat_asn_probe import RIPEstatASNProbePlugin
        from .cti.shodan_cti_plugin import ShodanCTIPlugin

        # 5. GEOINT
        from .geoint.nasa_firms_plugin import NASAFIRMSPlugin
        from .geoint.opensky_adsb_plugin import OpenSkyADSBPlugin

        builtins: list[Any] = [
            ShodanPlugin,
            VirusTotalPlugin,
            WhoisPlugin,
            WhatsMyNameProbe,
            GravatarProbe,
            PGPKeyserverProbe,
            BolagsverketPlugin,
            OpenCorporatesPlugin,
            OpenSanctionsPlugin,
            CryptoMempoolPlugin,
            CrtshSubdomainsPlugin,
            DoHDNSProbePlugin,
            RIPEstatASNProbePlugin,
            ShodanCTIPlugin,
            OpenSkyADSBPlugin,
            NASAFIRMSPlugin,
        ]

        for cls in builtins:
            inst = cls()
            self.register(inst)

        # Skanna katalogen efter eventuella dynamiska tredjepartsplugins
        plugins_dir = Path(__file__).parent
        package_name = "app.plugins"
        try:
            for _, module_name, is_pkg in pkgutil.walk_packages([str(plugins_dir)]):
                if module_name in ("base", "registry"):
                    continue
                try:
                    full_name = f"{package_name}.{module_name}"
                    mod = importlib.import_module(full_name)
                    for _, obj in inspect.getmembers(mod, inspect.isclass):
                        if (
                            issubclass(obj, BaseOSINTPlugin)
                            and obj is not BaseOSINTPlugin
                            and not inspect.isabstract(obj)
                        ):
                            plugin_cls: Any = obj
                            instance = plugin_cls()
                            self.register(instance)
                except Exception:
                    pass
        except Exception:
            pass


PluginRegistry = PluginManager
plugin_manager = PluginManager()
