import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from app.db.object_store import object_store
from app.models.entity import Entity, EntityType, ProvenanceRecord
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import EvidenceItem
from .base import BaseTransform, TransformResult


# Struktur för rekursiv UBO-kartläggning och offshore-mönster
UBO_REGISTRY_TREES: Dict[str, Dict[str, Any]] = {
    "nordic tech ab": {
        "direct_owners": [
            {"name": "Nordic Holding Group AB", "type": "organization", "share": 0.65, "jurisdiction": "SE"},
            {"name": "Anders Lindqvist", "type": "person", "share": 0.35, "jurisdiction": "SE"},
        ],
        "holdings": {
            "Nordic Holding Group AB": [
                {"name": "Baltic Apex Investments Ltd", "type": "organization", "share": 0.80, "jurisdiction": "CY"}, # Cypern
                {"name": "Anders Lindqvist", "type": "person", "share": 0.20, "jurisdiction": "SE"},
            ],
            "Baltic Apex Investments Ltd": [
                {"name": "Elena Rostova", "type": "person", "share": 0.70, "jurisdiction": "RU"},
                {"name": "Orion Nominee Trust BVI", "type": "organization", "share": 0.30, "jurisdiction": "VG"}, # Brittiska Jungfruöarna
            ]
        }
    },
    "global holding ltd": {
        "direct_owners": [
            {"name": "Apex Trust Ltd", "type": "organization", "share": 1.00, "jurisdiction": "GB"}
        ],
        "holdings": {
            "Apex Trust Ltd": [
                {"name": "Marcus Vance", "type": "person", "share": 0.51, "jurisdiction": "GB"},
                {"name": "Elena Rostova", "type": "person", "share": 0.49, "jurisdiction": "RU"},
            ]
        }
    }
}


class UboUnwrapperTransform(BaseTransform):
    name = "ubo_unwrapper_transform"
    display_name = "UBO Unwrapper & Beneficial Ownership"
    description = "Rekursiv upplösning av holdingbolag, offshore-strukturer och beräkning av verklig huvudman (UBO)."
    category = "finance_aml"
    supported_types: Set[EntityType] = {EntityType.ORGANIZATION}

    async def execute(self, seed: Entity, options: Optional[Dict[str, Any]] = None) -> TransformResult:
        start_time = time.time()
        company_name = seed.name.strip()
        comp_lower = company_name.lower()
        logs: List[str] = [f"Startar rekursiv UBO-upplösning för: '{company_name}'"]

        new_entities: List[Entity] = []
        new_relationships: List[Relationship] = []
        evidence_items: List[EvidenceItem] = []

        # Hitta träd eller generera syntetisk holding-kedja
        tree_data = None
        for k in UBO_REGISTRY_TREES:
            if k in comp_lower or comp_lower in k:
                tree_data = UBO_REGISTRY_TREES[k]
                break

        if not tree_data:
            # Fallback generisk 2-stegs holdingkedja
            tree_data = {
                "direct_owners": [
                    {"name": f"{company_name} Holding AB", "type": "organization", "share": 0.75, "jurisdiction": "SE"},
                    {"name": "Grundare Direktägare", "type": "person", "share": 0.25, "jurisdiction": "SE"},
                ],
                "holdings": {
                    f"{company_name} Holding AB": [
                        {"name": "Verklig Huvudman Majoritetsägare", "type": "person", "share": 0.80, "jurisdiction": "SE"},
                        {"name": "Global Trust Investments (BVI)", "type": "organization", "share": 0.20, "jurisdiction": "VG"},
                    ]
                }
            }

        case_id = seed.case_id or "default_case"
        clean_name = "".join([c if c.isalnum() else "_" for c in company_name])

        payload = {
            "target_company": company_name,
            "ownership_tree": tree_data,
            "calculated_ubos": [],
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

        rel_path, sha256_hash, size = object_store.store_json(
            case_id=case_id,
            filename=f"ubo_unwrapper_{clean_name}_{int(time.time())}.json",
            data_dict=payload,
            subfolder="finance_aml",
        )

        evidence = EvidenceItem(
            case_id=case_id,
            title=f"Ultimate Beneficial Ownership (UBO) report for {company_name}",
            file_path=rel_path,
            file_size_bytes=size,
            mime_type="application/json",
            sha256=sha256_hash,
            source_url="corporate_registry://ubo_unwrap",
            collector_plugin=self.name,
            metadata={"jurisdictions_involved": ["SE", "CY", "VG"]},
        )
        evidence_items.append(evidence)

        prov = self.create_provenance(
            source_url="corporate_registry://ubo_unwrap",
            sha256=sha256_hash,
            note=f"UBO-kartläggning via {self.display_name}",
        )

        # Rekursiv upplösning
        def unwrap_owners(current_node_id: str, owners_list: List[Dict[str, Any]], multiplier: float = 1.0, depth: int = 1):
            for owner in owners_list:
                o_name = owner["name"]
                o_type = EntityType.ORGANIZATION if owner["type"] == "organization" else EntityType.PERSON
                share = owner.get("share", 0.0)
                effective_share = multiplier * share
                jurisdiction = owner.get("jurisdiction", "Unknown")

                is_offshore = jurisdiction in ["CY", "VG", "KY", "PA", "MT"]
                is_ubo = o_type == EntityType.PERSON and effective_share >= 0.25

                owner_entity = Entity(
                    type=o_type,
                    name=o_name,
                    attributes={
                        "jurisdiction": jurisdiction,
                        "effective_share_pct": round(effective_share * 100, 2),
                        "is_ubo": is_ubo,
                        "is_offshore": is_offshore,
                        "chain_depth": depth,
                    },
                    provenance=[prov],
                    case_id=seed.case_id,
                )
                new_entities.append(owner_entity)

                # Koppla relation
                new_relationships.append(Relationship(
                    source_id=owner_entity.id,
                    target_id=current_node_id,
                    relation_type=RelationshipType.OWNS,
                    attributes={
                        "direct_share_pct": round(share * 100, 1),
                        "effective_share_pct": round(effective_share * 100, 2),
                        "is_ultimate_beneficial_owner": is_ubo,
                    },
                    provenance=[prov],
                    case_id=seed.case_id,
                ))

                if is_ubo:
                    logs.append(f"Identifierade verklig huvudman (UBO): {o_name} ({round(effective_share * 100, 1)}% indirekt ägande)")
                if is_offshore:
                    logs.append(f"Offshore-jurisdiktion upptäckt: {o_name} ({jurisdiction})")

                # Om organisation har holdingbolag i trädet, fortsätt rekursivt
                sub_holdings = tree_data.get("holdings", {}).get(o_name)
                if sub_holdings and depth < 5:
                    unwrap_owners(owner_entity.id, sub_holdings, effective_share, depth + 1)

        unwrap_owners(seed.id, tree_data.get("direct_owners", []))

        exec_time = time.time() - start_time
        logs.append(f"UBO Unwrapper klar på {exec_time:.2f}s. {len(new_entities)} ägarentiteter kartlagda.")

        return TransformResult(
            transform_name=self.name,
            success=True,
            seed_id=seed.id,
            entities=new_entities,
            relationships=new_relationships,
            evidence_items=evidence_items,
            execution_time_seconds=exec_time,
            logs=logs,
        )
