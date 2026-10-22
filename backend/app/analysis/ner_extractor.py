import re
from typing import List
from app.models.entity import Entity, EntityType, ProvenanceRecord


# Regex-mönster för strukturerade OSINT-entiteter
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
IPV4_REGEX = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
)
DOMAIN_REGEX = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+(?:com|se|org|net|io|co|uk|de|eu|info|biz|ru|cn)\b",
    re.IGNORECASE,
)
BTC_REGEX = re.compile(r"\b(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b")
ETH_REGEX = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
PHONE_REGEX = re.compile(r"(?:\+?46|0)[ -]?[0-9]{2,3}[ -]?[0-9]{2,3}[ -]?[0-9]{2,4}\b")
ORG_NR_REGEX = re.compile(r"\b\d{6}-\d{4}\b")

# Mönster för vanliga namn- och organisationsstrukturer
ORG_SUFFIX_REGEX = re.compile(
    r"\b([A-ZÅÄÖ][a-zA-ZåäöÅÄÖ0-9\s&]{2,30}?\s+(?:AB|Ltd|LLC|Inc|GmbH|Corp|Holdings|Group|Sverige|Bank))\b"
)
PERSON_NAME_REGEX = re.compile(r"\b([A-ZÅÄÖ][a-zåäö]{2,15}\s+[A-ZÅÄÖ][a-zåäö]{2,20})\b")


class NerExtractor:
    """
    NLP och mönsterbaserad extraherare (Named Entity Recognition) för ostrukturerad text
    (artiklar, domstolsprotokoll, läckor, webbsidor).
    Identifierar e-post, IP, domäner, kryptoplånböcker, telefon, organisationsnummer,
    företag och personnamn.
    """

    def extract_entities_from_text(self, text: str, case_id: str, source_url: str = "text://input") -> List[Entity]:
        discovered: List[Entity] = []
        seen_keys = set()

        prov = ProvenanceRecord(
            source_url=source_url,
            sha256="ner_extracted",
            collector_plugin="ner_extractor",
            note="Extraherat från ostrukturerad text via NER-analys",
        )

        # 1. E-postadresser
        for match in EMAIL_REGEX.findall(text):
            val = match.strip().lower()
            if val not in seen_keys:
                seen_keys.add(val)
                discovered.append(
                    Entity(
                        type=EntityType.EMAIL,
                        name=val,
                        provenance=[prov],
                        case_id=case_id,
                    )
                )

        # 2. IP-adresser
        for match in IPV4_REGEX.findall(text):
            val = match.strip()
            if val not in seen_keys and not val.startswith("0.") and not val.startswith("255."):
                seen_keys.add(val)
                discovered.append(
                    Entity(
                        type=EntityType.IP,
                        name=val,
                        provenance=[prov],
                        case_id=case_id,
                    )
                )

        # 3. Krypto-plånböcker (Bitcoin & Ethereum)
        for match in BTC_REGEX.findall(text):
            val = match if isinstance(match, str) else match[0]
            val = val.strip()
            if val not in seen_keys:
                seen_keys.add(val)
                discovered.append(
                    Entity(
                        type=EntityType.CRYPTO_WALLET,
                        name=val,
                        attributes={"blockchain": "Bitcoin"},
                        provenance=[prov],
                        case_id=case_id,
                    )
                )

        for match in ETH_REGEX.findall(text):
            val = match.strip()
            if val not in seen_keys:
                seen_keys.add(val)
                discovered.append(
                    Entity(
                        type=EntityType.CRYPTO_WALLET,
                        name=val,
                        attributes={"blockchain": "Ethereum"},
                        provenance=[prov],
                        case_id=case_id,
                    )
                )

        # 4. Domäner
        for match in DOMAIN_REGEX.findall(text):
            val = match.strip().lower()
            if val not in seen_keys and "@" not in val:
                seen_keys.add(val)
                discovered.append(
                    Entity(
                        type=EntityType.DOMAIN,
                        name=val,
                        provenance=[prov],
                        case_id=case_id,
                    )
                )

        # 5. Organisationsnummer
        for match in ORG_NR_REGEX.findall(text):
            val = match.strip()
            if val not in seen_keys:
                seen_keys.add(val)
                discovered.append(
                    Entity(
                        type=EntityType.ORGANIZATION,
                        name=f"Bolag ({val})",
                        attributes={"org_number": val},
                        provenance=[prov],
                        case_id=case_id,
                    )
                )

        # 6. Organisationer med suffix
        for match in ORG_SUFFIX_REGEX.findall(text):
            val = match.strip()
            if val not in seen_keys and len(val) > 4:
                seen_keys.add(val)
                discovered.append(
                    Entity(
                        type=EntityType.ORGANIZATION,
                        name=val,
                        provenance=[prov],
                        case_id=case_id,
                    )
                )

        # 7. Personnamn (filtrera vanliga ord)
        stopwords = {"Sverige", "Stockholm", "Göteborg", "Malmö", "Europa", "Internet", "Google", "Microsoft"}
        for match in PERSON_NAME_REGEX.findall(text):
            val = match.strip()
            parts = val.split()
            if len(parts) == 2 and parts[0] not in stopwords and parts[1] not in stopwords:
                if val not in seen_keys and len(val) > 5:
                    seen_keys.add(val)
                    discovered.append(
                        Entity(
                            type=EntityType.PERSON,
                            name=val,
                            provenance=[prov],
                            case_id=case_id,
                        )
                    )

        return discovered


ner_extractor = NerExtractor()
