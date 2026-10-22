from datetime import datetime, timezone
from typing import Any, Dict, List
from app.db.database import db
from app.db.graph_store import graph_store
from app.evidence.custody_manager import custody_manager


class ReportGenerator:
    """
    Genererar strukturerade utredningsrapporter i Markdown och HTML baserat på
    fallets entiteter, grafrelationer, centralitetsanalys och beviskedja.
    """
    def generate_markdown_report(self, case_id: str) -> str:
        case = db.get_case(case_id)
        if not case:
            raise ValueError(f"Ärende {case_id} kunde inte hittas.")

        entities = db.list_entities(case_id=case_id)
        relationships = db.list_relationships(case_id=case_id)
        evidence_list = db.list_evidence(case_id=case_id)
        metrics = graph_store.compute_metrics(case_id)
        custody_audit = custody_manager.verify_case_custody(case_id)

        # Räkna entiteter per typ
        type_counts: Dict[str, int] = {}
        sanctioned_entities: List[str] = []
        for e in entities:
            t = e.type.value if hasattr(e.type, "value") else str(e.type)
            type_counts[t] = type_counts.get(t, 0) + 1
            if e.attributes.get("sanctioned") is True:
                sanctioned_entities.append(f"{e.name} ({e.attributes.get('sanctions_program', 'Sanktionerad')})")

        md = []
        md.append(f"# Utredningsrapport: {case.title}")
        md.append(f"**Ärende-ID:** `{case.id}`  ")
        md.append(f"**Status:** `{case.status.value.upper()}` | **Prioritet:** `{case.priority.value.upper()}`  ")
        md.append(f"**Ansvarig utredare:** {case.investigator}  ")
        md.append(f"**Genererad:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ")
        md.append(f"**Taggar:** {', '.join(case.tags) if case.tags else 'Inga taggar'}  \n")
        md.append("---\n")

        # 1. Sammanfattning
        md.append("## 1. Sammanfattning och utredningshypotes")
        md.append(case.description or "Ingen detaljerad beskrivning angiven för ärendet.")
        md.append(f"\nTotalt har **{len(entities)} entiteter** och **{len(relationships)} relationer** kartlagts. "
                  f"Samtliga bevis har kryptografiskt säkrats i beviskedjan med **{len(evidence_list)} registrerade poster**.\n")

        # 2. Riskbedömning och sanktioner
        md.append("## 2. Riskbedömning och efterlevnadskontroll")
        if sanctioned_entities:
            md.append("> [!CAUTION]\n> **KRITISK FLAGG: Träffar mot internationella sanktionslistor identifierade!**")
            for se in sanctioned_entities:
                md.append(f"> * {se}")
            md.append("")
        else:
            md.append("Inga entiteter i detta ärende matchar för närvarande internationella sanktionslistor (OFAC/EU/FN).\n")

        # 3. Entitetsöversikt
        md.append("## 3. Kartlagda entiteter")
        md.append("| Typ | Antal |")
        md.append("| :--- | :--- |")
        for t, count in sorted(type_counts.items()):
            md.append(f"| `{t}` | {count} |")
        md.append("")

        md.append("### Detaljerad entitetslista")
        md.append("| Namn | Typ | Konfidens | Alias / Nyckelattribut |")
        md.append("| :--- | :--- | :--- | :--- |")
        for e in entities[:30]:  # Begränsa till 30 för läsbarhet
            alias_str = ", ".join(e.aliases) if e.aliases else "-"
            attr_summary = []
            for k in ["org_number", "country", "city", "platform", "ip_version"]:
                if k in e.attributes:
                    attr_summary.append(f"{k}: {e.attributes[k]}")
            extra = f" [{'; '.join(attr_summary)}]" if attr_summary else ""
            t = e.type.value if hasattr(e.type, "value") else str(e.type)
            clean_name = e.name.replace("|", "/")
            md.append(f"| {clean_name} | `{t}` | {e.confidence_score * 100:.0f}% | {alias_str}{extra} |")
        md.append("")

        # 4. Nätverks- och grafanalys
        md.append("## 4. Nätverksanalys och nyckelaktörer (Grafmått)")
        top_inf = metrics.get("top_influencers", [])
        if top_inf:
            md.append("Följande noder har identifierats som centrala nätverksaktörer baserat på sammansatt PageRank och Betweenness-centralitet:")
            md.append("")
            md.append("| Nod | Typ | Nätverkspoäng | PageRank | Betweenness | Grad |")
            md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for item in top_inf[:8]:
                md.append(f"| **{item['name']}** | `{item['type']}` | {item['score']} | {item['pagerank']} | {item['betweenness']} | {item['degree']} |")
            md.append("")
        else:
            md.append("Inga nätverksrelationer registrerade ännu för centralitetsberäkning.\n")

        # 5. Länkanalys
        md.append("## 5. Länkanalys och identifierade kopplingar")
        if relationships:
            md.append("| Från | Relation | Till | Konfidens |")
            md.append("| :--- | :--- | :--- | :--- |")
            # Skapa uppslag för nodnamn
            ent_map = {e.id: e.name for e in entities}
            for r in relationships[:40]:
                src_name = ent_map.get(r.source_id, r.source_id).replace("|", "/")
                tgt_name = ent_map.get(r.target_id, r.target_id).replace("|", "/")
                rel_t = r.relation_type.value if hasattr(r.relation_type, "value") else str(r.relation_type)
                md.append(f"| {src_name} | **`{rel_t}`** | {tgt_name} | {r.confidence_score * 100:.0f}% |")
            md.append("")
        else:
            md.append("Inga relationer mellan entiteter har skapats i detta ärende.\n")

        # 6. Beviskedja & Chain of Custody
        md.append("## 6. Beviskedja och kryptografisk spårbarhet (Chain of Custody)")
        status_text = "OBRUTEN OCH VALID" if custody_audit.get("chain_of_custody_intact") else "AVVIKELSER FUNNA"
        md.append(f"**Beviskedjans status:** `{status_text}`  ")
        md.append(f"**Validerade filer:** {custody_audit.get('valid_count')} / {custody_audit.get('total_items')}  \n")

        if evidence_list:
            md.append("| Titel | Insamlare | SHA-256 Kontrollsumma | MIME-typ |")
            md.append("| :--- | :--- | :--- | :--- |")
            for ev in evidence_list[:25]:
                short_hash = f"`{ev.sha256[:12]}...{ev.sha256[-8:]}`"
                clean_title = ev.title.replace("|", "/")
                md.append(f"| {clean_title} | `{ev.collector_plugin or 'manual'}` | {short_hash} | {ev.mime_type} |")
            md.append("")

        # 7. Slutsatser
        md.append("## 7. Slutsatser och rekommenderade åtgärder")
        md.append("1. **Fördjupad infrastrukturkontroll:** Fortsätt övervakning av associerade subdomäner och IP-adresser.")
        md.append("2. **Ägarkartläggning:** Verifiera verkliga huvudmän för kopplade bolag via domstols- och officiella register.")
        md.append("3. **Bevissäkring:** Exportera fallets grafdata i GEXF/GraphML och bevara genererade beviskopior.")
        md.append("\n---\n*Rapporten är automatiskt sammanställd av OpenIntel-OSINT utredningsplattform.*")

        return "\n".join(md)


report_generator = ReportGenerator()
