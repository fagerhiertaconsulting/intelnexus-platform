from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel
from app.db.database import db
from app.db.graph_store import graph_store
from app.models.entity import Entity, EntityType, ProvenanceRecord
from app.models.relationship import Relationship


def jaro_winkler_distance(s1: str, s2: str, scaling: float = 0.1) -> float:
    """
    Beräknar Jaro-Winkler likhetsavstånd mellan två strängar.
    Returnerar ett värde mellan 0.0 (helt olika) och 1.0 (identiska).
    """
    s1, s2 = s1.lower().strip(), s2.lower().strip()
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    max_dist = (max(len1, len2) // 2) - 1
    if max_dist < 0:
        max_dist = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - max_dist)
        end = min(i + max_dist + 1, len2)
        for j in range(start, end):
            if s2_matches[j]:
                continue
            if s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    jaro = ((matches / len1) + (matches / len2) + ((matches - transpositions / 2) / matches)) / 3.0

    # Winkler prefix bonus (upp till 4 tecken)
    prefix_len = 0
    for i in range(min(len1, len2, 4)):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break

    return jaro + (prefix_len * scaling * (1.0 - jaro))


class MatchCandidate(BaseModel):
    primary_entity_id: str
    secondary_entity_id: str
    primary_name: str
    secondary_name: str
    match_type: str  # 'deterministic' | 'probabilistic'
    confidence: float
    reasons: List[str]


class EntityResolver:
    """
    Modul för entitetsupplösning, deduplicering och länkning.
    Stödjer deterministisk identifiering (org-nummer, unika nycklar) och
    probabilistisk matchning (Jaro-Winkler likhet på namn/alias).
    """
    UNIQUE_ATTR_KEYS = [
        "org_number", "vat_number", "registration_number",
        "email", "phone_number", "crypto_address", "sha256", "national_id"
    ]

    def find_matches(self, case_id: str, probabilistic_threshold: float = 0.85) -> List[MatchCandidate]:
        """
        Söker igenom alla entiteter inom ett ärende och identifierar dubbletter
        och matchande kandidater för sammanslagning.
        """
        entities = db.list_entities(case_id=case_id)
        candidates: List[MatchCandidate] = []
        n = len(entities)

        for i in range(n):
            for j in range(i + 1, n):
                e1, e2 = entities[i], entities[j]

                # Endast samma övergripande typ eller person/username
                if e1.type != e2.type:
                    continue

                # 1. Deterministisk matchning (unika nycklar)
                det_reasons = []
                for key in self.UNIQUE_ATTR_KEYS:
                    val1 = e1.attributes.get(key)
                    val2 = e2.attributes.get(key)
                    if val1 and val2 and str(val1).strip().lower() == str(val2).strip().lower():
                        det_reasons.append(f"Identiskt unikt attribut '{key}': {val1}")

                if det_reasons:
                    candidates.append(MatchCandidate(
                        primary_entity_id=e1.id,
                        secondary_entity_id=e2.id,
                        primary_name=e1.name,
                        secondary_name=e2.name,
                        match_type="deterministic",
                        confidence=1.0,
                        reasons=det_reasons,
                    ))
                    continue

                # 2. Probabilistisk matchning (Jaro-Winkler på namn och alias)
                name_jw = jaro_winkler_distance(e1.name, e2.name)
                best_sim = name_jw
                prob_reasons = [f"Jaro-Winkler namnlikhet: {name_jw:.3f}"]

                # Kontrollera alias
                for a1 in e1.aliases:
                    sim = jaro_winkler_distance(a1, e2.name)
                    if sim > best_sim:
                        best_sim = sim
                        prob_reasons.append(f"Alias '{a1}' matchar namn med likhet {sim:.3f}")

                for a2 in e2.aliases:
                    sim = jaro_winkler_distance(e1.name, a2)
                    if sim > best_sim:
                        best_sim = sim
                        prob_reasons.append(f"Namn matchar alias '{a2}' med likhet {sim:.3f}")

                # Gemensamma attribut/kontaktpunkter förstärker förtroendet
                shared_attrs = 0
                for k in ["nationality", "city", "country", "birth_year"]:
                    if k in e1.attributes and k in e2.attributes:
                        if str(e1.attributes[k]).lower() == str(e2.attributes[k]).lower():
                            shared_attrs += 1
                            prob_reasons.append(f"Gemensamt attribut '{k}': {e1.attributes[k]}")

                final_confidence = min(1.0, best_sim + (shared_attrs * 0.05))

                if final_confidence >= probabilistic_threshold:
                    candidates.append(MatchCandidate(
                        primary_entity_id=e1.id,
                        secondary_entity_id=e2.id,
                        primary_name=e1.name,
                        secondary_name=e2.name,
                        match_type="probabilistic",
                        confidence=round(final_confidence, 3),
                        reasons=prob_reasons,
                    ))

        return candidates

    def merge_entities(self, primary_id: str, secondary_id: str, case_id: str) -> Entity:
        """
        Slår samman secondary_id in i primary_id:
        1. Överför unika attribut och alias.
        2. Sammanfogar beviskedja och proveniens.
        3. Omdirigerar alla relationer (kanter) till primary_id.
        4. Tar bort secondary_id.
        5. Uppdaterar grafmotorn.
        """
        primary = db.get_entity(primary_id)
        secondary = db.get_entity(secondary_id)
        if not primary or not secondary:
            raise ValueError("Kunde inte hitta båda entiteterna för sammanslagning.")

        # Alias
        combined_aliases = set(primary.aliases)
        combined_aliases.add(secondary.name)
        for a in secondary.aliases:
            combined_aliases.add(a)
        combined_aliases.discard(primary.name)
        primary.aliases = sorted(list(combined_aliases))

        # Attribut (behåll primary, addera från secondary om saknas)
        for k, v in secondary.attributes.items():
            if k not in primary.attributes:
                primary.attributes[k] = v
            elif isinstance(primary.attributes[k], list) and isinstance(v, list):
                primary.attributes[k] = list(set(primary.attributes[k] + v))

        # Proveniens
        primary_prov_hashes = {p.sha256 for p in primary.provenance}
        for p in secondary.provenance:
            if p.sha256 not in primary_prov_hashes:
                primary.provenance.append(p)
                primary_prov_hashes.add(p.sha256)

        primary.confidence_score = max(primary.confidence_score, secondary.confidence_score)
        db.save_entity(primary)

        # Omdirigera relationer
        all_rels = db.list_relationships(case_id=case_id)
        for r in all_rels:
            rewired = False
            if r.source_id == secondary.id:
                r.source_id = primary.id
                rewired = True
            if r.target_id == secondary.id:
                r.target_id = primary.id
                rewired = True
            if rewired:
                # Undvik självreferens
                if r.source_id != r.target_id:
                    db.save_relationship(r)
                else:
                    db.delete_relationship(r.id)

        # Ta bort secondary
        db.delete_entity(secondary.id)

        # Ladda om grafen
        graph_store.reload_case_graph(case_id)

        return primary


entity_resolver = EntityResolver()
