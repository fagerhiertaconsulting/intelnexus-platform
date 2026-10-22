import re
from typing import Any, Dict, List, Set, Tuple
from app.models.entity import Entity
from app.models.relationship import Relationship


class PIISanitizer:
    """
    Tjänst för GDPR- och integritetsskyddande export.
    Maskerar personnummer, adresser för icke-relevanta parter och filtrerar
    oskyldiga personkopplingar med låg konfidens vid delning eller publik export.
    """

    # Svenska personnummer (12-siffrigt: YYYYMMDD-XXXX eller YYYYMMDDXXXX)
    PN_12_REGEX = re.compile(r"\b(19\d{2}|20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[-+]?(\d{4})\b")

    # Svenska personnummer (10-siffrigt: YYMMDD-XXXX eller YYMMDDXXXX)
    PN_10_REGEX = re.compile(r"\b(\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[-+]?(\d{4})\b")

    # Känsliga adressattribut
    ADDRESS_KEYS = {
        "address",
        "street_address",
        "residential_address",
        "postal_address",
        "home_address",
        "gatuadress",
        "folkbokforingsadress",
        "bostadsadress",
    }

    def mask_personal_id(self, text: str) -> str:
        """
        Ersätter personnummer med 'ÅÅÅÅMMDD-****' eller 'ÅÅMMDD-****' enligt GDPR-minimering.
        """
        # Först 12-siffriga
        res = self.PN_12_REGEX.sub(r"\1\2\3-****", text)
        # Därefter 10-siffriga
        res = self.PN_10_REGEX.sub(r"\1\2\3-****", res)
        return res

    def mask_text(self, text: str) -> str:
        """Kör fullständig textmaskering av personnummer och explicita personuppgifter."""
        return self.mask_personal_id(text)

    def sanitize_attributes(
        self,
        attributes: Dict[str, Any],
        is_third_party: bool = False,
    ) -> Dict[str, Any]:
        """
        Rensar och maskerar attribut i en entitet:
        - Personnummer maskeras alltid.
        - Adresser maskeras om entiteten är en tredje part eller vid allmän sanitiserad export.
        """
        sanitized: Dict[str, Any] = {}
        for key, val in attributes.items():
            k_lower = key.lower()

            # Om adressfält och relevant att maskera
            if is_third_party and any(addr_key in k_lower for addr_key in self.ADDRESS_KEYS):
                sanitized[key] = "[MASKERAD ADRESS / GDPR]"
                continue

            if isinstance(val, str):
                if any(addr_key in k_lower for addr_key in self.ADDRESS_KEYS):
                    sanitized[key] = "[MASKERAD ADRESS / GDPR]"
                else:
                    sanitized[key] = self.mask_personal_id(val)
            elif isinstance(val, dict):
                sanitized[key] = self.sanitize_attributes(val, is_third_party=is_third_party)
            elif isinstance(val, list):
                sanitized[key] = [
                    self.mask_personal_id(item)
                    if isinstance(item, str)
                    else (
                        self.sanitize_attributes(item, is_third_party=is_third_party)
                        if isinstance(item, dict)
                        else item
                    )
                    for item in val
                ]
            else:
                sanitized[key] = val

        return sanitized

    def sanitize_entity(
        self,
        entity: Entity,
        is_third_party: bool = False,
    ) -> Entity:
        """Skapar en sanitiserad kopia av en entitet med maskerat namn och attribut."""
        # Djupkopiera entiteten
        data = entity.model_dump()

        data["name"] = self.mask_personal_id(entity.name)
        data["aliases"] = [self.mask_personal_id(a) for a in entity.aliases]
        data["attributes"] = self.sanitize_attributes(entity.attributes, is_third_party=is_third_party)

        return Entity.model_validate(data)

    def sanitize_dossier(
        self,
        entities: List[Entity],
        relationships: List[Relationship],
        min_confidence_threshold: float = 0.6,
        remove_innocent_contacts: bool = True,
    ) -> Tuple[List[Entity], List[Relationship]]:
        """
        Sanitiserar en hel dossier (entiteter och relationer):
        1. Maskerar personnummer och adresser.
        2. Raderar oskyldiga personkopplingar och tredjeparter under konfidenströskeln.
        3. Säkerställer att kvarvarande relationer pekar på existerande noder.
        """
        retained_entities: List[Entity] = []
        retained_ids: Set[str] = set()

        for ent in entities:
            # Kontrollera om entiteten är en perifer person med låg konfidens
            is_person = ent.type == "Person" or getattr(ent.type, "value", str(ent.type)).lower() == "person"
            is_third_party = bool(ent.attributes.get("is_third_party", False))

            if remove_innocent_contacts and is_person:
                # Om konfidensen understiger tröskeln eller explicit flaggad som tredje part utan brottsmisstanke
                if ent.confidence_score < min_confidence_threshold:
                    continue
                if is_third_party and ent.attributes.get("suspect") is not True:
                    continue

            sanitized_ent = self.sanitize_entity(ent, is_third_party=is_third_party)
            retained_entities.append(sanitized_ent)
            retained_ids.add(sanitized_ent.id)

        # Filtrera relationer så att inga brutna kanter kvarstår
        retained_relationships: List[Relationship] = []
        for rel in relationships:
            if rel.source_id in retained_ids and rel.target_id in retained_ids:
                rel_data = rel.model_dump()
                rel_data["attributes"] = self.sanitize_attributes(rel.attributes, is_third_party=False)
                retained_relationships.append(Relationship.model_validate(rel_data))

        return retained_entities, retained_relationships


pii_sanitizer = PIISanitizer()
