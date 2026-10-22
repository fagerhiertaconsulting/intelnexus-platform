import asyncio
from typing import Any, Dict, List, Optional
from app.db.database import db
from app.db.graph_store import graph_store
from app.models.entity import Entity
from app.core.vault import credential_vault
from .base import BaseTransform, TransformResult
from .dns_transform import DnsWhoisTransform
from .company_registry_transform import CompanyRegistryTransform
from .social_footprint_transform import SocialFootprintTransform
from .ip_geo_transform import IpGeoTransform
from .crtsh_subdomain_transform import CrtshSubdomainTransform
from .sanctions_transform import SanctionsTransform
from .exif_metadata_transform import ExifMetadataTransform
from .catfish_transform import CatfishReverseImageTransform
from .phone_breach_transform import PhoneBreachCheckTransform
from .romance_scam_transform import RomanceScamCheckTransform
from .ubo_transform import UboUnwrapperTransform
from .geoint_crisis_transform import GeointCrisisTransform


class TransformRegistry:
    """
    Centralt register och exekveringsmotor för alla OSINT-transforms.
    Hanterar upptäckt, BYOAK-nyckelavkänning, asynkron parallellkörning, databassynk och evidensarkivering.
    """
    def __init__(self):
        self._transforms: Dict[str, BaseTransform] = {}
        self._register_default_transforms()

    def _register_default_transforms(self):
        default_classes = [
            DnsWhoisTransform,
            CompanyRegistryTransform,
            SocialFootprintTransform,
            IpGeoTransform,
            CrtshSubdomainTransform,
            SanctionsTransform,
            ExifMetadataTransform,
            CatfishReverseImageTransform,
            PhoneBreachCheckTransform,
            RomanceScamCheckTransform,
            UboUnwrapperTransform,
            GeointCrisisTransform,
        ]
        for cls in default_classes:
            instance = cls()
            self._transforms[instance.name] = instance

    def register(self, transform: BaseTransform):
        self._transforms[transform.name] = transform

    def get(self, name: str) -> Optional[BaseTransform]:
        return self._transforms.get(name)

    def list_transforms(self) -> List[Dict[str, Any]]:
        """Returnerar metadata om alla registrerade transforms och deras BYOAK-status."""
        result = []
        for t in self._transforms.values():
            is_unlocked = t.is_available(credential_vault)
            result.append({
                "name": t.name,
                "display_name": t.display_name,
                "description": t.description,
                "category": t.category,
                "supported_types": [s.value if hasattr(s, "value") else str(s) for s in t.supported_types],
                "required_credentials": t.required_credentials,
                "is_available": is_unlocked,
                "is_byoak": len(t.required_credentials) > 0,
            })
        return result

    def get_supported_transforms_for_entity(self, entity: Entity) -> List[Dict[str, Any]]:
        """Returnerar transforms som är kompatibla med den angivna entitetstypen."""
        available = []
        for t in self._transforms.values():
            if entity.type in t.supported_types:
                available.append({
                    "name": t.name,
                    "display_name": t.display_name,
                    "description": t.description,
                    "category": t.category,
                    "required_credentials": t.required_credentials,
                    "is_available": t.is_available(credential_vault),
                })
        return available

    async def execute_transform(self, transform_name: str, seed: Entity, options: Optional[Dict[str, Any]] = None) -> TransformResult:
        """
        Kör en specifik transform mot en nod, sparar alla genererade noder/relationer/bevis
        i databasen och grafen samt synkroniserar grafstrukturen.
        """
        transform = self.get(transform_name)
        if not transform:
            return TransformResult(
                transform_name=transform_name,
                success=False,
                seed_id=seed.id,
                error_message=f"Transform '{transform_name}' finns inte i registret.",
            )

        if not transform.validate_input(seed):
            return TransformResult(
                transform_name=transform_name,
                success=False,
                seed_id=seed.id,
                error_message=f"Entiteten '{seed.name}' ({seed.type}) stöds inte av {transform.display_name}.",
            )

        # Kör transform
        result = await transform.execute(seed, options)

        if result.success and seed.case_id:
            # 1. Uppdatera seed i DB
            db.save_entity(seed)

            # 2. Spara evidensposter
            for ev in result.evidence_items:
                db.save_evidence(ev)

            # 3. Spara nya entiteter och lägg till i graf
            for ent in result.entities:
                ent.case_id = seed.case_id
                db.save_entity(ent)
                graph_store.add_entity_to_graph(seed.case_id, ent)

            # 4. Spara relationer och lägg till i graf
            for rel in result.relationships:
                rel.case_id = seed.case_id
                db.save_relationship(rel)
                graph_store.add_relationship_to_graph(seed.case_id, rel)

        return result

    async def execute_parallel(self, transform_names: List[str], seed: Entity, options: Optional[Dict[str, Any]] = None) -> List[TransformResult]:
        """Kör flera transforms parallellt mot samma seed-nod."""
        tasks = [self.execute_transform(name, seed, options) for name in transform_names]
        return await asyncio.gather(*tasks)


registry = TransformRegistry()
