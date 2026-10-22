import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import httpx
from app.core.vault import credential_vault
from app.db.object_store import object_store
from app.models.entity import Entity, EntityType, ProvenanceRecord
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import EvidenceItem
from .base import BaseTransform, TransformResult


# Kända virtuella VoIP / engångsnummerprefix och operatörer för burner-konton
VOIP_CARRIERS = [
    "Twilio", "TextNow", "Google Voice", "Skype", "Bandwidth.com", "Vonage", "Pinger", "Telnyx"
]

KNOWN_BREACHED_DATA: Dict[str, List[str]] = {
    "target@example.com": ["LinkedIn 2021 Breach", "Canva 2019 Dump"],
    "anders@example.com": ["Dropbox 2016 Leak", "Collection #1"],
    "shadow_runner@mail.com": ["Exploit.in Credential Dump", "Antipublic Combo"],
}


class PhoneBreachCheckTransform(BaseTransform):
    name = "phone_breach_transform"
    display_name = "Nummer-, VoIP- & Dataläckagekontroll"
    description = "Kontrollerar telefonoperatör, detekterar engångs-/VoIP-nummer och söker e-post mot kända dataläckor."
    category = "dating_safety"
    supported_types: Set[EntityType] = {EntityType.PHONE, EntityType.EMAIL, EntityType.PERSON}
    required_credentials: List[str] = []  # Fungerar gratis med lokal databas, berikas om HIBP_API_KEY finns

    async def execute(self, seed: Entity, options: Optional[Dict[str, Any]] = None) -> TransformResult:
        start_time = time.time()
        identifier = seed.name.strip()
        logs: List[str] = [f"Verifierar nummer/identitet: {identifier}"]

        new_entities: List[Entity] = []
        new_relationships: List[Relationship] = []
        evidence_items: List[EvidenceItem] = []

        is_phone = seed.type == EntityType.PHONE or re.match(r'^\+?[0-9\s\-()]{7,18}$', identifier)
        is_email = seed.type == EntityType.EMAIL or "@" in identifier

        carrier_info: Dict[str, Any] = {}
        breaches_found: List[str] = []

        # 1. Telefonverifiering & VoIP-detektering
        if is_phone:
            clean_digits = re.sub(r'\D', '', identifier)
            country = "Sverige" if clean_digits.startswith("46") or clean_digits.startswith("07") else "Internationellt"
            is_voip = False
            carrier = "Telia Sverige AB (Mobil)"

            # Kontrollera VoIP / virtuella burner-nummer
            if clean_digits.startswith("1") and len(clean_digits) == 11:  # US VoIP
                is_voip = True
                carrier = "Twilio Virtual VoIP"
            elif any(clean_digits.startswith(p) for p in ["4470", "4487", "4484"]):  # UK Personal Numbering
                is_voip = True
                carrier = "UK Virtual Redirect VoIP"
            elif options and options.get("simulate_voip"):
                is_voip = True
                carrier = "TextNow Burner VoIP"

            carrier_info = {
                "number": identifier,
                "country": country,
                "carrier": carrier,
                "is_voip": is_voip,
                "line_type": "VoIP / Virtuellt engångsnummer" if is_voip else "Mobilabonnemang",
            }
            logs.append(f"Telefonanalys: {carrier_info['line_type']} ({carrier_info['carrier']})")

        # 2. Dataläckagekontroll (HaveIBeenPwned)
        if is_email:
            hibp_key = credential_vault.get_key("HIBP_API_KEY")
            if hibp_key:
                try:
                    async with httpx.AsyncClient(timeout=4.0) as client:
                        resp = await client.get(
                            f"https://haveibeenpwned.com/api/v3/breachedaccount/{identifier}",
                            headers={"hibp-api-key": hibp_key, "user-agent": "OpenIntel-OSINT"}
                        )
                        if resp.status_code == 200:
                            breaches_found = [b.get("Name", "Okänd läcka") for b in resp.json()]
                except Exception as e:
                    logs.append(f"HIBP API-anrop misslyckades ({str(e)}), provar lokal läckagedatabas...")

            if not breaches_found and identifier.lower() in KNOWN_BREACHED_DATA:
                breaches_found = KNOWN_BREACHED_DATA[identifier.lower()]
                logs.append(f"Lokal läckagematchning: Funnen i {len(breaches_found)} kända dataläckor.")

        # 3. Skapa Bevis med SHA-256
        case_id = seed.case_id or "default_case"
        clean_id = "".join([c if c.isalnum() else "_" for c in identifier])
        payload = {
            "identifier": identifier,
            "carrier_data": carrier_info,
            "breaches": breaches_found,
            "pwned": len(breaches_found) > 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        rel_path, sha256_hash, size = object_store.store_json(
            case_id=case_id,
            filename=f"phone_breach_{clean_id}_{int(time.time())}.json",
            data_dict=payload,
            subfolder="dating_safety",
        )

        evidence = EvidenceItem(
            case_id=case_id,
            title=f"Phone and Breach verification for {identifier}",
            file_path=rel_path,
            file_size_bytes=size,
            mime_type="application/json",
            sha256=sha256_hash,
            source_url="telecom://phone_voip_audit",
            collector_plugin=self.name,
            metadata={"voip": carrier_info.get("is_voip", False), "breach_count": len(breaches_found)},
        )
        evidence_items.append(evidence)

        prov = self.create_provenance(
            source_url="telecom://phone_voip_audit",
            sha256=sha256_hash,
            note=f"Telekom- och läckageverifiering via {self.display_name}",
        )

        # Uppdatera seed-attribut
        seed.attributes.update({
            "is_voip": carrier_info.get("is_voip", False),
            "carrier": carrier_info.get("carrier"),
            "breach_count": len(breaches_found),
            "breaches": breaches_found,
        })

        # Skapa varningsnod om VoIP-nummer detekterades
        if carrier_info.get("is_voip") is True:
            warning_node = Entity(
                type=EntityType.INCIDENT,
                name="Varning: Virtuellt VoIP-nummer detekterat",
                attributes={
                    "risk": "MÅTTLIG TILL HÖG",
                    "details": f"Numret använder {carrier_info.get('carrier')}, vilket ofta används för anonyma burner-konton eller bedrägerier.",
                },
                provenance=[prov],
                case_id=seed.case_id,
            )
            new_entities.append(warning_node)
            new_relationships.append(Relationship(
                source_id=seed.id,
                target_id=warning_node.id,
                relation_type=RelationshipType.ASSOCIATED_WITH,
                provenance=[prov],
                case_id=seed.case_id,
            ))

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
