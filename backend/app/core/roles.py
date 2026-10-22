from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkspaceRoleConfig(BaseModel):
    role_id: str
    display_name: str
    description: str
    target_audience: str
    icon_name: str
    theme: str
    default_view: str  # 'wizard' | 'graph' | 'document' | 'dossier' | 'financial' | 'map'
    active_widgets: List[str]
    suggested_api_keys: List[Dict[str, str]]
    default_playbooks: List[Dict[str, str]]


WORKSPACE_ROLES: Dict[str, WorkspaceRoleConfig] = {
    # A. Privatperson
    "dating_safety": WorkspaceRoleConfig(
        role_id="dating_safety",
        display_name="Privatperson: Säkerhetskoll",
        description="Förenklad och guidad verifiering av dejter, okända kontaktpersoner och köp/sälj-annonser för att upptäcka romansbedrägerier och catfishing.",
        target_audience="Privatpersoner och konsumenter",
        icon_name="HeartHandshake",
        theme="dating_soft",
        default_view="wizard",
        active_widgets=[
            "catfish_image_checker",
            "phone_voip_detector",
            "romance_scam_screener",
            "social_footprint_compact",
            "safety_verdict_card",
        ],
        suggested_api_keys=[
            {"key_name": "HIBP_API_KEY", "label": "HaveIBeenPwned API (Läckta lösenord & konton)"},
        ],
        default_playbooks=[
            {"id": "dating_verification_playbook", "title": "Komplett dejt- och kontaktverifiering", "description": "Kör omvänd bildsökning, kontrollerar VoIP/engångsnummer och söker i varningslistor."}
        ],
    ),

    # B. Rättsväsende & Polis
    "law_enforcement": WorkspaceRoleConfig(
        role_id="law_enforcement",
        display_name="Rättsväsende & Polis",
        description="Forensisk utredningsmiljö med strikt beviskedja (Chain of Custody), telekom-/IP-korrelation och juridisk export för förundersökningsprotokoll (FUP).",
        target_audience="Polis, åklagare och forensiker",
        icon_name="ShieldCheck",
        theme="police_dark",
        default_view="graph",
        active_widgets=[
            "custody_ledger_sha",
            "ip_telecom_correlator",
            "network_graph_forensic",
            "court_record_search",
            "fup_export_builder",
        ],
        suggested_api_keys=[
            {"key_name": "INFOTORG_API_KEY", "label": "InfoTorg Folkbokföring & Fordon"},
            {"key_name": "VIRUSTOTAL_API_KEY", "label": "VirusTotal Enterprise"},
            {"key_name": "SHODAN_API_KEY", "label": "Shodan Enterprise"},
        ],
        default_playbooks=[
            {"id": "infrastructure_correlation_playbook", "title": "Infrastruktur- & Cyberkorrelation", "description": "Kartlägger nätverksinfrastruktur, VPN-maskering, certifikat och domänägare."},
            {"id": "fup_evidence_audit_playbook", "title": "Beviskedjeaudit för FUP", "description": "Validerar SHA-256 kontrollsummor och sammanställer forensisk bevistabell."}
        ],
    ),

    # C. Undersökande Journalistik
    "journalism": WorkspaceRoleConfig(
        role_id="journalism",
        display_name="Undersökande Journalistik",
        description="Fokus på källskydd, rensning av dokumentmetadata för att skydda visselblåsare, myndighetsdiarier och automatisk arkivering.",
        target_audience="Grävande journalister och redaktioner",
        icon_name="Newspaper",
        theme="journalism_clean",
        default_view="document",
        active_widgets=[
            "metadata_stripper_vault",
            "document_ner_extractor",
            "public_diarier_search",
            "wayback_change_tracker",
            "source_protection_guard",
        ],
        suggested_api_keys=[
            {"key_name": "OPENCORPORATES_API_KEY", "label": "OpenCorporates Global API"},
        ],
        default_playbooks=[
            {"id": "whistleblower_sanitization_flow", "title": "Källskydd & Metadata-tvätt", "description": "Rensar all EXIF-, GPS- och enhetsmetadata ur dokument och bilder innan publicering."},
            {"id": "public_procurement_audit", "title": "Granskning av upphandlingar", "description": "Korsrefererar bolagsstyrelser mot offentliga företrädare."}
        ],
    ),

    # D. Privatdetektiv & Säkerhetskonsult
    "private_investigator": WorkspaceRoleConfig(
        role_id="private_investigator",
        display_name="Privatdetektiv & Konsult",
        description="360-graders bakgrundskontroll, tillgångsspårning (Asset Tracing), folkbokföringsadresser och relationsmatris över individer och bolag.",
        target_audience="Privatutredare och säkerhetschefer",
        icon_name="UserCheck",
        theme="dossier_dark",
        default_view="dossier",
        active_widgets=[
            "dossier_profile_card",
            "company_person_matrix",
            "social_footprint_grid_300",
            "vehicle_address_crossref",
            "client_report_pdf_builder",
        ],
        suggested_api_keys=[
            {"key_name": "BOLAGSVERKET_API_KEY", "label": "Bolagsverket API"},
            {"key_name": "INFOTORG_API_KEY", "label": "InfoTorg Person & Bolag"},
            {"key_name": "ROARING_API_KEY", "label": "Roaring Business Intelligence"},
        ],
        default_playbooks=[
            {"id": "full_background_dossier", "title": "Fullständig 360-graders bakgrundskontroll", "description": "Kombinerar adresshistorik, bolagsengagemang, fordon och digitala fotspår."}
        ],
    ),

    # E. Finansanalytiker & Compliance (AML/UBO)
    "finance_aml": WorkspaceRoleConfig(
        role_id="finance_aml",
        display_name="Finansbrott, AML & Compliance",
        description="Anti-Money Laundering (AML), upplösning av verklig huvudman (UBO), ägarträd, kryptoanalys och sanktionskontroll.",
        target_audience="Compliance officers, AML-analytiker och finanskriminalpoliser",
        icon_name="Landmark",
        theme="finance_dark",
        default_view="financial",
        active_widgets=[
            "ubo_unwrapper_tree",
            "sanctions_pep_matrix",
            "crypto_blockchain_tracker",
            "insolvency_bankruptcy_history",
            "transaction_flow_graph",
        ],
        suggested_api_keys=[
            {"key_name": "OPENSANCTIONS_API_KEY", "label": "OpenSanctions API"},
            {"key_name": "ETHERSCAN_API_KEY", "label": "Etherscan Crypto API"},
            {"key_name": "ROARING_API_KEY", "label": "Roaring UBO Register"},
        ],
        default_playbooks=[
            {"id": "ubo_unwrapping_playbook", "title": "Rekursiv UBO-upplösning", "description": "Identifierar verkliga huvudmän genom holdingbolagskedjor och offshorestrukturer."},
            {"id": "sanctions_deep_screening", "title": "Fördjupad sanktions- & PEP-granskning", "description": "Matchar mot OFAC SDN, EU Consolidated och FN med fuzzy Jaro-Winkler."}
        ],
    ),

    # F. Geopolitisk analytiker & Ambassad
    "geopolitical": WorkspaceRoleConfig(
        role_id="geopolitical",
        display_name="Geopolitik & Krisövervakning",
        description="Situationsmedvetenhet (Situational Awareness), realtids satellitlager (NASA FIRMS), ADS-B flygspårning och desinformationsanalys.",
        target_audience="Geopolitiska analytiker, försvar och tankesmedjor",
        icon_name="Globe",
        theme="geoint_satellite",
        default_view="map",
        active_widgets=[
            "geoint_satellite_layer",
            "transponder_flight_tracker",
            "thermal_firms_hotspots",
            "conflict_news_telegram_feed",
            "narrative_disinfo_monitor",
        ],
        suggested_api_keys=[
            {"key_name": "NASA_FIRMS_KEY", "label": "NASA FIRMS API (Termisk branddata)"},
            {"key_name": "OPENSKY_CREDENTIALS", "label": "OpenSky Network (ADS-B)"},
        ],
        default_playbooks=[
            {"id": "crisis_zone_correlation", "title": "Kriszonsövervakning", "description": "Kombinerar satellitlager, NASA FIRMS värmedata och flygtranspondrar i realtid."}
        ],
    ),

    # G. Diplomatisk Beskickning & Fysisk Säkerhet
    "embassy": WorkspaceRoleConfig(
        role_id="embassy",
        display_name="Ambassad & Diplomatisk Säkerhet",
        description="Fysisk säkerhetsövervakning av beskickningar och residens, geofencing perimeterskydd och krisvarningar.",
        target_audience="Ambassadsäkerhet och diplomatiska rådgivare",
        icon_name="Building2",
        theme="embassy_secure",
        default_view="map",
        active_widgets=[
            "facility_perimeter_geofence",
            "diplomatic_incident_alerts",
            "crisis_evacuation_routes",
            "local_media_monitor",
            "air_maritime_traffic_radar",
        ],
        suggested_api_keys=[
            {"key_name": "NASA_FIRMS_KEY", "label": "NASA FIRMS API"},
        ],
        default_playbooks=[
            {"id": "perimeter_threat_assessment", "title": "Perimeter Threat Assessment", "description": "Analyserar incidenter och oroligheter inom 5 km radie kring beskickningen."}
        ],
    ),
}


class RoleManager:
    """Hanterar tillgängliga roller och sparar aktiv roll per ärende eller användarsession."""
    def list_roles(self) -> List[WorkspaceRoleConfig]:
        return list(WORKSPACE_ROLES.values())

    def get_role(self, role_id: str) -> Optional[WorkspaceRoleConfig]:
        return WORKSPACE_ROLES.get(role_id)


role_manager = RoleManager()
