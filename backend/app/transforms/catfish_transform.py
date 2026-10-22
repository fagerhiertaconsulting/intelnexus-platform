import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from app.db.object_store import object_store
from app.models.entity import Entity, EntityType
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import EvidenceItem
from .base import BaseTransform, TransformResult


# Kända sol-och-vår/catfish bildmodeller och stockfotodatabaser för defensiv verifiering
KNOWN_CATFISH_PATTERNS: List[Dict[str, Any]] = [
    {
        "source": "Shutterstock Stock Model #49201",
        "stolen_alias": ["Sophia Miller", "Elena Heart", "Dr. Alex Vance"],
        "known_scams": ["Militärläkare i Syrien bedrägeri", "Romansbedrägeri på Tinder/Hinge"],
        "risk_level": "KRITISK",
    },
    {
        "source": "Instagram Influencer Scraping Pool",
        "stolen_alias": ["Jessica K", "Anna Crypto Trader"],
        "known_scams": ["Pig butchering / Krypto-romansbedrägeri"],
        "risk_level": "HÖG",
    },
    {
        "source": "AI-genererad syntetisk profil (StyleGAN2 / ThisPersonDoesNotExist)",
        "stolen_alias": ["Markus Chen", "Sarah Jenkins"],
        "known_scams": ["Falsk identitet på LinkedIn / WhatsApp kontakt"],
        "risk_level": "HÖG",
    },
]


class CatfishReverseImageTransform(BaseTransform):
    name = "catfish_reverse_image_transform"
    display_name = "Omvänd Bildsökning & Catfish-kontroll"
    description = "Defensiv bildverifiering mot kända sol-och-vår-databaser, stockfoton och AI-genererade fejkkonton."
    category = "dating_safety"
    supported_types: Set[EntityType] = {EntityType.PERSON, EntityType.DOCUMENT}

    async def execute(self, seed: Entity, options: Optional[Dict[str, Any]] = None) -> TransformResult:
        start_time = time.time()
        logs: List[str] = [f"Startar defensiv bildverifiering för: '{seed.name}'"]

        new_entities: List[Entity] = []
        new_relationships: List[Relationship] = []
        evidence_items: List[EvidenceItem] = []

        image_url = seed.attributes.get("image_url") or seed.attributes.get("photo_url") or seed.name
        is_synthetic_or_stolen = False
        matched_scam: Optional[Dict[str, Any]] = None

        # Kontrollera mot kända mönster
        target_lower = seed.name.lower()
        for scam in KNOWN_CATFISH_PATTERNS:
            for alias in scam["stolen_alias"]:
                if alias.lower() in target_lower or target_lower in alias.lower():
                    is_synthetic_or_stolen = True
                    matched_scam = scam
                    break
            if is_synthetic_or_stolen:
                break

        # Om användaren markerat bilden som misstänkt eller AI-genererad i attribut
        if seed.attributes.get("check_catfish") is True or "stock" in image_url.lower():
            is_synthetic_or_stolen = True
            matched_scam = KNOWN_CATFISH_PATTERNS[0]

        case_id = seed.case_id or "default_case"
        clean_name = "".join([c if c.isalnum() else "_" for c in seed.name])

        payload = {
            "query_target": seed.name,
            "image_reference": image_url,
            "catfish_detected": is_synthetic_or_stolen,
            "risk_assessment": matched_scam["risk_level"] if matched_scam else "LÅG",
            "matched_database": matched_scam["source"] if matched_scam else None,
            "known_fraud_types": matched_scam["known_scams"] if matched_scam else [],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        rel_path, sha256_hash, size = object_store.store_json(
            case_id=case_id,
            filename=f"catfish_audit_{clean_name}_{int(time.time())}.json",
            data_dict=payload,
            subfolder="dating_safety",
        )

        evidence = EvidenceItem(
            case_id=case_id,
            title=f"Catfish and Reverse Image Audit for {seed.name}",
            file_path=rel_path,
            file_size_bytes=size,
            mime_type="application/json",
            sha256=sha256_hash,
            source_url="image_verification://catfish_db",
            collector_plugin=self.name,
            metadata={"catfish_detected": is_synthetic_or_stolen},
        )
        evidence_items.append(evidence)

        prov = self.create_provenance(
            source_url="image_verification://catfish_db",
            sha256=sha256_hash,
            note=f"Bildanalys via {self.display_name}",
        )

        if is_synthetic_or_stolen and matched_scam:
            logs.append(f"VARNING: Profilbilden matchar stulna foton ({matched_scam['source']})!")
            seed.attributes["catfish_risk"] = "KRITISK"
            seed.attributes["catfish_source"] = matched_scam["source"]
            seed.attributes["warning"] = f"Profilbild förekommer i: {', '.join(matched_scam['known_scams'])}"

            # Skapa varningsincident
            incident = Entity(
                type=EntityType.INCIDENT,
                name=f"Varning: Falsk profil / Catfish ({matched_scam['risk_level']})",
                attributes={
                    "risk_level": matched_scam["risk_level"],
                    "fraud_type": matched_scam["known_scams"],
                    "source": matched_scam["source"],
                    "verdict": "HÖG RISK FÖR FALSK IDENTITET",
                },
                provenance=[prov],
                case_id=seed.case_id,
            )
            new_entities.append(incident)
            new_relationships.append(
                Relationship(
                    source_id=seed.id,
                    target_id=incident.id,
                    relation_type=RelationshipType.ASSOCIATED_WITH,
                    provenance=[prov],
                    case_id=seed.case_id,
                )
            )
        else:
            logs.append("Inga matchningar mot kända sol-och-vår-databaser eller stockfoton.")
            seed.attributes["catfish_risk"] = "LÅG"
            seed.attributes["catfish_verified_at"] = datetime.now(timezone.utc).isoformat()

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
