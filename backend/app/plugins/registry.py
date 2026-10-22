import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from .base import BaseOSINTPlugin, EntityInput, TransformResult


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
        """Registrerar en plugin-instans i katalogen."""
        self._plugins[plugin.slug] = plugin

    def get_plugin(self, slug: str) -> Optional[BaseOSINTPlugin]:
        """Hämtar ett plugin via dess unika slug."""
        return self._plugins.get(slug)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Listar metadata för samtliga registrerade plugins."""
        result = []
        for p in self._plugins.values():
            result.append(
                {
                    "name": p.name,
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
        """Filtrerar ut plugins som stödjer en given entitetstyp."""
        cleaned = entity_type.strip().lower()
        matched = []
        for p in self._plugins.values():
            types_lower = [t.lower() for t in p.supported_inputs]
            if cleaned in types_lower or "*" in types_lower:
                matched.append(p)
        return matched

    get_plugins_for_type = get_plugins_for_input

    async def execute_plugin(
        self,
        slug: str,
        target: EntityInput,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> TransformResult:
        """Kör ett namngivet plugin mot målet."""
        plugin = self.get_plugin(slug)
        if not plugin:
            raise ValueError(f"Plugin med slug '{slug}' hittades inte.")
        return await plugin.execute(target, api_key=api_key, proxy_url=proxy_url)

    def discover_plugins(self, package_path: Optional[str] = None):
        """
        Söker dynamiskt igenom katalogen och importerar alla moduler
        som definierar en subklass till BaseOSINTPlugin.
        """
        plugins_dir = Path(__file__).parent
        package_name = "app.plugins"

        # Importera först kända inbyggda plugins direkt
        from .shodan_plugin import ShodanPlugin
        from .virustotal_plugin import VirusTotalPlugin
        from .whois_plugin import WhoisPlugin

        for cls in (ShodanPlugin, VirusTotalPlugin, WhoisPlugin):
            inst = cls()
            self.register(inst)

        # Skanna katalogen efter ytterligare plugins
        try:
            for _, module_name, is_pkg in pkgutil.iter_modules([str(plugins_dir)]):
                if is_pkg or module_name in ("base", "registry"):
                    continue
                try:
                    full_name = f"{package_name}.{module_name}"
                    mod = importlib.import_module(full_name)
                    for _, obj in inspect.getmembers(mod, inspect.isclass):
                        if issubclass(obj, BaseOSINTPlugin) and obj is not BaseOSINTPlugin:
                            instance = obj()
                            self.register(instance)
                except Exception:
                    pass
        except Exception:
            pass


plugin_manager = PluginManager()
