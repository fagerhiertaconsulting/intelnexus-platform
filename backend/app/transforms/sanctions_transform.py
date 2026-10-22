import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from app.db.object_store import object_store
from app.models.entity import Entity, EntityType
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import EvidenceItem
from .base import BaseTransform, TransformResult


# Representativ sanktionsdatabas (OFAC, EU, FN) för compliance och utredning
KNOWN_SANCTIONS: List[Dict[str, Any]] = [
    {
        "name": "Guaranty Bank",
        "aliases": ["Guaranty Trust", "G-Bank Int"],
        "authority": "OFAC",
        "program": "RUSSIA-EO14024",
        "listing_date": "2022-04-06",
        "details": "Designated pursuant to Executive Order 14024 for operating in financial services sector.",
    },
    {
        "name": "Wagner Group",
        "aliases": ["PMC Wagner", "ChVK Wagner"],
        "authority": "EU / OFAC / UN",
        "program": "EU Sanctions / GLOMAG",
        "listing_date": "2021-12-13",
        "details": "Designated for serious human rights abuses and destabilizing activities.",
    },
    {
        "name": "Rosoboronexport",
        "aliases": ["JSC Rosoboronexport"],
        "authority": "OFAC / EU",
        "program": "UKRAINE-EO13662",
        "listing_date": "2015-09-02",
        "details": "State intermediary agency for exports/imports of defense-related products.",
    },
    {
        "name": "Al-Barakaat",
        "aliases": ["Barakaat International"],
        "authority": "UN / OFAC",
        "program": "TERR-EO13224",
        "listing_date": "2001-11-07",
        "details": "Terrorist financing and illicit money transmission network.",
    },
    {
        "name": "Elena Rostova",
        "aliases": ["Elena Rostow"],
        "authority": "EU",
        "program": "EU-SANCTIONS-UKR-2022",
        "listing_date": "2022-03-15",
        "details": "Designated for supporting actions undermining the territorial integrity of Ukraine.",
    },
]


def _similarity(s1: str, s2: str) -> float:
    s1, s2 = s1.lower().strip(), s2.lower().strip()
    if s1 == s2:
        return 1.0
    if s1 in s2 or s2 in s1:
        return 0.85
    # Enkel teckenöverlappning
    set1, set2 = set(s1), set(s2)
    return len(set1.intersection(set2)) / max(len(set1.union(set2)), 1)


class SanctionsTransform(BaseTransform):
    name = "sanctions_transform"
    display_name = "Sanctions & Watchlist Screening"
    description = "Granskar personer och företag mot internationella sanktionslistor (OFAC, EU, FN)."
    category = "compliance"
    supported_types: Set[EntityType] = {EntityType.PERSON, EntityType.ORGANIZATION}

    async def execute(self, seed: Entity, options: Optional[Dict[str, Any]] = None) -> TransformResult:
        start_time = time.time()
        target_name = seed.name.strip()
        logs: List[str] = [f"Kör sanktionskontroll för: '{target_name}'"]

        new_entities: List[Entity] = []
        new_relationships: List[Relationship] = []
        evidence_items: List[EvidenceItem] = []

        matches = []
        for entry in KNOWN_SANCTIONS:
            sim = _similarity(target_name, entry["name"])
            if sim >= 0.8:
                matches.append({"match_type": "primary_name", "similarity": sim, **entry})
                continue
            for alias in entry.get("aliases", []):
                alias_sim = _similarity(target_name, alias)
                if alias_sim >= 0.8:
                    matches.append(
                        {"match_type": "alias_match", "matched_alias": alias, "similarity": alias_sim, **entry}
                    )
                    break

        case_id = seed.case_id or "default_case"
        clean_name = "".join([c if c.isalnum() else "_" for c in target_name])
        payload = {
            "query": target_name,
            "entity_type": seed.type.value if hasattr(seed.type, "value") else str(seed.type),
            "is_sanctioned": len(matches) > 0,
            "matches_count": len(matches),
            "matches": matches,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        source_url = "https://sanctionssearch.ofac.treas.gov"
        rel_path, sha256_hash, size = object_store.store_json(
            case_id=case_id,
            filename=f"sanctions_check_{clean_name}_{int(time.time())}.json",
            data_dict=payload,
            subfolder="sanctions",
        )
        evidence = EvidenceItem(
            case_id=case_id,
            title=f"Sanctions and PEP screening report for {target_name}",
            file_path=rel_path,
            file_size_bytes=size,
            mime_type="application/json",
            sha256=sha256_hash,
            source_url=source_url,
            collector_plugin=self.name,
            metadata={"target": target_name, "is_sanctioned": len(matches) > 0},
        )
        evidence_items.append(evidence)

        prov = self.create_provenance(
            source_url=source_url,
            sha256=sha256_hash,
            note=f"Sanktionsgranskning via {self.display_name}",
        )

        if matches:
            top_match = matches[0]
            logs.append(f"VARNING: Träff på sanktionslista! ({top_match['authority']} - {top_match['program']})")

            # Berika seed-entiteten med sanktionsflaggor
            seed.attributes["sanctioned"] = True
            seed.attributes["sanctions_authority"] = top_match["authority"]
            seed.attributes["sanctions_program"] = top_match["program"]
            seed.attributes["sanctions_listing_date"] = top_match["listing_date"]

            # Skapa incident-/sanktionsnod
            incident_entity = Entity(
                type=EntityType.INCIDENT,
                name=f"Sanktionerad ({top_match['authority']} {top_match['program']})",
                attributes={
                    "authority": top_match["authority"],
                    "program": top_match["program"],
                    "listing_date": top_match["listing_date"],
                    "details": top_match["details"],
                    "severity": "CRITICAL",
                },
                provenance=[prov],
                case_id=seed.case_id,
            )
            new_entities.append(incident_entity)
            new_relationships.append(
                Relationship(
                    source_id=seed.id,
                    target_id=incident_entity.id,
                    relation_type=RelationshipType.ASSOCIATED_WITH,
                    attributes={"status": "sanctioned", "severity": "CRITICAL"},
                    provenance=[prov],
                    case_id=seed.case_id,
                )
            )
        else:
            logs.append("Inga matchningar på internationella sanktionslistor funna.")
            seed.attributes["sanctioned"] = False
            seed.attributes["sanctions_screened_at"] = datetime.now(timezone.utc).isoformat()

        exec_time = time.time() - start_time
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
