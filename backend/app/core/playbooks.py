from typing import Any, Dict, List, Optional
from app.db.database import db
from app.models.entity import Entity, EntityType, ProvenanceRecord
from app.transforms.registry import registry


class PlaybookOrchestrator:
    """
    Orkestrerar rollspecifika sökguider (Playbooks).
    Kör kedjade transforms, sammanställer riskbedömningar och genererar färdiga resultat.
    """

    async def run_dating_verification(
        self,
        case_id: str,
        name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        image_url: Optional[str] = None,
        story: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Playbook för Privatperson: Säkerhetskoll / Dejt-verifiering.
        Kör catfish-kontroll, VoIP/engångsnummerdetektering, dataläckor och romansbedrägerikontroll.
        """
        prov = ProvenanceRecord(
            source_url="wizard://dating_safety",
            sha256="wizard_session",
            collector_plugin="dating_wizard",
            note="Initierad via Säkerhetskoll / Dejt-verifiering",
        )

        # 1. Skapa eller hämta målperson
        person_entity = db.save_entity(
            Entity(
                case_id=case_id,
                type=EntityType.PERSON,
                name=name.strip(),
                attributes={
                    "image_url": image_url,
                    "phone": phone,
                    "email": email,
                    "story": story,
                },
                provenance=[prov],
            )
        )

        sub_entities = []

        # 2. Om telefonnummer finns, skapa telefonnod
        phone_node = None
        if phone and phone.strip():
            phone_node = db.save_entity(
                Entity(
                    case_id=case_id,
                    type=EntityType.PHONE,
                    name=phone.strip(),
                    provenance=[prov],
                )
            )
            sub_entities.append(phone_node)

        # 3. Kör Catfish Reverse Image Transform
        _catfish_res = await registry.execute_transform("catfish_reverse_image_transform", person_entity)

        # 4. Kör Phone & Breach Transform om nummer angavs
        _phone_res = None
        if phone_node:
            _phone_res = await registry.execute_transform("phone_breach_transform", phone_node)

        # 5. Kör Romance Scam & Varningslistekontroll
        _scam_res = await registry.execute_transform("romance_scam_check_transform", person_entity)

        # 6. Kör Social Footprint på namnet
        footprint_res = await registry.execute_transform("social_footprint_transform", person_entity)

        # 7. Beräkna sammansatt riskbedömning och klartextrapport
        catfish_detected = person_entity.attributes.get("catfish_risk") in ["HÖG", "KRITISK"]
        voip_detected = phone_node.attributes.get("is_voip", False) if phone_node else False
        scam_score = person_entity.attributes.get("scam_risk_score", 0.0)

        total_risk_score = 0.0
        risk_factors: List[str] = []

        if catfish_detected:
            total_risk_score += 0.50
            risk_factors.append("Profilbild matchar kända sol-och-vår- eller stockfotodatabaser.")

        if voip_detected:
            total_risk_score += 0.30
            risk_factors.append("Telefonnumret är ett anonymt VoIP / virtuellt engångsnummer.")

        if scam_score >= 0.4:
            total_risk_score += 0.40
            risk_factors.extend(person_entity.attributes.get("scam_flags", []))

        total_risk_score = min(1.0, total_risk_score)

        if total_risk_score >= 0.6:
            overall_verdict = "HÖG RISK FÖR FALSK IDENTITET / BEDRÄGERI"
            verdict_badge = "CRITICAL"
            advice = "Överför ALDRIG pengar eller kryptovaluta. Avbryt kontakt och kräv videosamtal i realtid."
        elif total_risk_score >= 0.3:
            overall_verdict = "MÅTTLIG RISK - IAKTTA FÖRSIKTIGHET"
            verdict_badge = "WARNING"
            advice = "Vissa avvikelser upptäcktes. Verifiera identiteten via alternativa oberoende kanaler."
        else:
            overall_verdict = "LÅG RISK - INGA AVVIKELSER HITTADES"
            verdict_badge = "LOW"
            advice = "Inga kända varningsflaggor eller stulna foton identifierades i publika databaser."

        return {
            "target_name": name,
            "overall_verdict": overall_verdict,
            "risk_level": verdict_badge,
            "risk_score_pct": round(total_risk_score * 100),
            "risk_factors": risk_factors,
            "recommended_action": advice,
            "catfish_check": {
                "detected": catfish_detected,
                "source": person_entity.attributes.get("catfish_source"),
            },
            "phone_check": {
                "checked": bool(phone_node),
                "is_voip": voip_detected,
                "carrier": phone_node.attributes.get("carrier") if phone_node else None,
            },
            "profiles_found": len(footprint_res.entities) if footprint_res else 0,
        }


playbook_orchestrator = PlaybookOrchestrator()
