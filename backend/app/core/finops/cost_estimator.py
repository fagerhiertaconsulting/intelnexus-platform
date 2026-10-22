from typing import List
from pydantic import BaseModel, Field

from app.plugins.base import EntityInput
from app.plugins.registry import plugin_manager
from .cache import response_cache


class DryRunEstimate(BaseModel):
    plugin_slug: str
    plugin_name: str
    is_commercial: bool
    cost_per_query: float
    planned_calls: int
    cache_hits: int
    net_calls: int
    estimated_total_cost: float
    currency_or_unit: str = Field(default="credits", description="'credits' eller 'USD'")
    cached_targets: List[str]
    uncached_targets: List[str]


class CostEstimator:
    """
    Kalkylerar API-kostnader och förbrukningsestimering (Dry-Run)
    före körning av transform-batchar mot kommersiella API:er.
    """

    @staticmethod
    def estimate(
        plugin_slug: str,
        targets: List[EntityInput],
        force_refresh: bool = False,
    ) -> DryRunEstimate:
        plugin = plugin_manager.get_plugin(plugin_slug)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_slug}' hittades inte.")

        cached_targets = []
        uncached_targets = []

        for t in targets:
            is_cached = False
            if not force_refresh:
                cached_data = response_cache.get(plugin_slug, t.entity_type, t.value)
                if cached_data is not None:
                    is_cached = True

            if is_cached:
                cached_targets.append(t.value)
            else:
                uncached_targets.append(t.value)

        planned_calls = len(targets)
        cache_hits = len(cached_targets)
        net_calls = len(uncached_targets)
        cost_per_query = plugin.cost_per_query_estimate
        total_cost = round(net_calls * cost_per_query, 2)

        return DryRunEstimate(
            plugin_slug=plugin.slug,
            plugin_name=plugin.name,
            is_commercial=plugin.is_commercial,
            cost_per_query=cost_per_query,
            planned_calls=planned_calls,
            cache_hits=cache_hits,
            net_calls=net_calls,
            estimated_total_cost=total_cost,
            currency_or_unit="credits" if plugin.is_commercial else "free",
            cached_targets=cached_targets,
            uncached_targets=uncached_targets,
        )


cost_estimator = CostEstimator()
