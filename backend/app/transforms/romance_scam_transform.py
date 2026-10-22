import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from app.db.object_store import object_store
from app.models.entity import Entity, EntityType
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import EvidenceItem
from .base import BaseTransform, TransformResult


SCAM_KEYWORDS = [
    ("militärläkare", "Militärläkare utomlands (Klassiskt sol-och-vår-narrativ)"),
    ("oljeplattform", "Ingenjör på oljeplattform som behöver pengar till reservdelar"),
    ("tullavgift", "Paket eller arv fast i tullen som kräver avgift"),
    ("kryptoinvestering", "Garanterad avkastning på privat kryptoplattform (Pig butchering)"),
    ("yemen", "Stationerad i Jemen/Syrien med låsta bankkonton"),
    ("syria", "Stationerad i Jemen/Syrien med låsta bankkonton"),
    ("arv", "Påstått stort utländskt arv som behöver frigöras"),
]

KNOWN_SCAM_NAMES = ["alexander vance", "richard stone", "david carter", "dr. mark smith", "robert golden"]


class RomanceScamCheckTransform(BaseTransform):
    name = "romance_scam_check_transform"
    display_name = "Romansbedrägeri & Sol-och-Vår Varningskontroll"
    description = "Söker igenom publika varningslistor och analyserar typiska bedrägerinarrativ för romans- och investeringsbedrägerier."
    category = "dating_safety"
    supported_types: Set[EntityType] = {EntityType.PERSON, EntityType.DOCUMENT, EntityType.USERNAME}

    async def execute(self, seed: Entity, options: Optional[Dict[str, Any]] = None) -> TransformResult:
        start_time = time.time()
        target_name = seed.name.strip().lower()
        logs: List[str] = [f"Kör bedrägerikontroll mot varningslistor för: '{seed.name}'"]

        new_entities: List[Entity] = []
        new_relationships: List[Relationship] = []
        evidence_items: List[EvidenceItem] = []

        scam_flags: List[str] = []
        risk_score = 0.1  # Basrisk

        # 1. Kontrollera namn mot kända sol-och-vår alias
        for scam_name in KNOWN_SCAM_NAMES:
            if scam_name in target_name or target_name in scam_name:
                scam_flags.append(f"Känt alias för romansbedragare rapporterat på varningslistor: '{scam_name}'")
                risk_score += 0.7

        # 2. Kontrollera narrativ/beskrivningstext om sådan angivits
        story_text = (seed.attributes.get("story") or seed.attributes.get("description") or "").lower()
        for kw, desc in SCAM_KEYWORDS:
            if kw in story_text or kw in target_name:
                scam_flags.append(f"Identifierat bedrägerimönster: {desc}")
                risk_score += 0.4

        risk_score = min(1.0, risk_score)
        verdict = "LÅG RISK"
        if risk_score >= 0.7:
            verdict = "HÖG RISK FÖR BEDRÄGERI"
        elif risk_score >= 0.4:
            verdict = "MÅTTLIG RISK - IAKTTA FÖRSIKTIGHET"

        case_id = seed.case_id or "default_case"
        clean_name = "".join([c if c.isalnum() else "_" for c in seed.name])

        payload = {
            "target": seed.name,
            "verdict": verdict,
            "risk_score": round(risk_score, 2),
            "flags": scam_flags,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        rel_path, sha256_hash, size = object_store.store_json(
            case_id=case_id,
            filename=f"scam_check_{clean_name}_{int(time.time())}.json",
            data_dict=payload,
            subfolder="dating_safety",
        )

        evidence = EvidenceItem(
            case_id=case_id,
            title=f"Romance Scam warning audit for {seed.name}",
            file_path=rel_path,
            file_size_bytes=size,
            mime_type="application/json",
            sha256=sha256_hash,
            source_url="consumer_protection://scam_watch",
            collector_plugin=self.name,
            metadata={"verdict": verdict, "risk_score": risk_score},
        )
        evidence_items.append(evidence)

        prov = self.create_provenance(
            source_url="consumer_protection://scam_watch",
            sha256=sha256_hash,
            note=f"Varningskontroll via {self.display_name}",
        )

        seed.attributes["scam_risk_verdict"] = verdict
        seed.attributes["scam_risk_score"] = round(risk_score, 2)
        seed.attributes["scam_flags"] = scam_flags

        if risk_score >= 0.4:
            incident = Entity(
                type=EntityType.INCIDENT,
                name=f"Varning: {verdict}",
                attributes={
                    "risk_score": round(risk_score, 2),
                    "verdict": verdict,
                    "flags": scam_flags,
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

        exec_time = time.time() - start_time
        logs.append(f"Bedrägerikontroll klar: {verdict} ({risk_score * 100:.0f}%)")

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
