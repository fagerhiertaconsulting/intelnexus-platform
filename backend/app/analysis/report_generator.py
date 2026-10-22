from datetime import datetime, timezone
from typing import Any, Dict, List
from app.core.reporting.sanitizer import pii_sanitizer
from app.db.database import db
from app.db.graph_store import graph_store
from app.evidence.custody_manager import custody_manager

REPORT_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "sv": {
        "title": "Utredningsrapport",
        "sanitized_badge": " [SANITISERAD EXPORT / GDPR-MASKERAD]",
        "case_id": "Ärende-ID",
        "export_mode": "Exportläge",
        "mode_sanitized": "SANITIZED (Publik/GDPR)",
        "mode_full": "FULL (Intern/Rättslig)",
        "status": "Status",
        "priority": "Prioritet",
        "investigator": "Ansvarig utredare",
        "generated": "Genererad",
        "tags": "Taggar",
        "no_tags": "Inga taggar",
        "sec1_title": "1. Sammanfattning och utredningshypotes",
        "sec1_no_desc": "Ingen detaljerad beskrivning angiven för ärendet.",
        "sec1_stats": (
            "Totalt har **{entities} entiteter** och **{relationships} relationer** kartlagts. "
            "Samtliga bevis har kryptografiskt säkrats i beviskedjan med **{evidence} registrerade poster**.\n"
        ),
        "sec2_title": "2. Riskbedömning och efterlevnadskontroll",
        "sec2_sanction_alert": (
            "> [!CAUTION]\n> **KRITISK FLAGG: Träffar mot internationella sanktionslistor identifierade!**"
        ),
        "sec2_no_sanctions": (
            "Inga entiteter i detta ärende matchar för närvarande internationella sanktionslistor (OFAC/EU/FN).\n"
        ),
        "sec3_title": "3. Kartlagda entiteter",
        "sec3_type": "Typ",
        "sec3_count": "Antal",
        "sec3_det_title": "Detaljerad entitetslista",
        "sec3_th_name": "Namn",
        "sec3_th_type": "Typ",
        "sec3_th_conf": "Konfidens",
        "sec3_th_nato": "NATO Tillit",
        "sec3_th_alias": "Alias / Nyckelattribut",
        "sec4_title": "4. Nätverksanalys och nyckelaktörer (Grafmått)",
        "sec4_top_intro": (
            "Följande noder har identifierats som centrala nätverksaktörer baserat på sammansatt "
            "PageRank och Betweenness-centralitet:"
        ),
        "sec4_th_node": "Nod",
        "sec4_th_score": "Nätverkspoäng",
        "sec4_th_degree": "Grad",
        "sec4_no_metrics": "Inga nätverksrelationer registrerade ännu för centralitetsberäkning.\n",
        "sec5_title": "5. Länkanalys och identifierade kopplingar",
        "sec5_th_from": "Från",
        "sec5_th_rel": "Relation",
        "sec5_th_to": "Till",
        "sec5_no_rels": "Inga relationer mellan entiteter har skapats i detta ärende.\n",
        "sec6_title": "6. Beviskedja och kryptografisk spårbarhet (Chain of Custody)",
        "sec6_status_label": "Beviskedjans status",
        "sec6_status_intact": "OBRUTEN OCH VALID",
        "sec6_status_tampered": "AVVIKELSER FUNNA",
        "sec6_validated_files": "Validerade filer",
        "sec6_th_title": "Titel",
        "sec6_th_collector": "Insamlare",
        "sec6_th_hash": "SHA-256 Kontrollsumma",
        "sec6_th_mime": "MIME-typ",
        "sec7_title": "7. Slutsatser och rekommenderade åtgärder",
        "sec7_act1": (
            "1. **Fördjupad infrastrukturkontroll:** Fortsätt övervakning av associerade subdomäner och IP-adresser."
        ),
        "sec7_act2": (
            "2. **Ägarkartläggning:** Verifiera verkliga huvudmän för kopplade bolag via domstols- och "
            "officiella register."
        ),
        "sec7_act3": (
            "3. **Bevissäkring:** Exportera fallets grafdata i GEXF/GraphML och bevara genererade beviskopior."
        ),
        "footer": "\n---\n*Rapporten är automatiskt sammanställd av IntelNexus Platform.*",
    },
    "en": {
        "title": "Investigation Report",
        "sanitized_badge": " [SANITIZED EXPORT / PRIVACY-MASKED]",
        "case_id": "Case ID",
        "export_mode": "Export Mode",
        "mode_sanitized": "SANITIZED (Public/GDPR)",
        "mode_full": "FULL (Internal/Judicial)",
        "status": "Status",
        "priority": "Priority",
        "investigator": "Lead Investigator",
        "generated": "Generated",
        "tags": "Tags",
        "no_tags": "No tags",
        "sec1_title": "1. Executive Summary & Investigative Hypothesis",
        "sec1_no_desc": "No detailed case description provided.",
        "sec1_stats": (
            "A total of **{entities} entities** and **{relationships} relationships** have been mapped. "
            "All evidence items have been cryptographically secured in the chain of custody with "
            "**{evidence} registered records**.\n"
        ),
        "sec2_title": "2. Risk Assessment & Sanctions Compliance",
        "sec2_sanction_alert": (
            "> [!CAUTION]\n> **CRITICAL FLAG: Hits against international sanctions lists identified!**"
        ),
        "sec2_no_sanctions": ("No entities in this case currently match international sanctions lists (OFAC/EU/UN).\n"),
        "sec3_title": "3. Identified Entities",
        "sec3_type": "Type",
        "sec3_count": "Count",
        "sec3_det_title": "Detailed Entity List",
        "sec3_th_name": "Name",
        "sec3_th_type": "Type",
        "sec3_th_conf": "Confidence",
        "sec3_th_nato": "NATO Rating",
        "sec3_th_alias": "Aliases / Key Attributes",
        "sec4_title": "4. Network Analysis & Key Influencers (Graph Metrics)",
        "sec4_top_intro": (
            "The following nodes have been identified as key network actors based on composite "
            "PageRank and Betweenness centrality:"
        ),
        "sec4_th_node": "Node",
        "sec4_th_score": "Network Score",
        "sec4_th_degree": "Degree",
        "sec4_no_metrics": "No network relationships registered yet for centrality calculation.\n",
        "sec5_title": "5. Link Analysis & Identified Connections",
        "sec5_th_from": "From",
        "sec5_th_rel": "Relationship",
        "sec5_th_to": "To",
        "sec5_no_rels": "No entity relationships have been created in this case.\n",
        "sec6_title": "6. Chain of Custody & Cryptographic Traceability",
        "sec6_status_label": "Chain of Custody Status",
        "sec6_status_intact": "INTACT AND VALID",
        "sec6_status_tampered": "DISCREPANCIES DETECTED",
        "sec6_validated_files": "Validated Files",
        "sec6_th_title": "Title",
        "sec6_th_collector": "Collector",
        "sec6_th_hash": "SHA-256 Checksum",
        "sec6_th_mime": "MIME Type",
        "sec7_title": "7. Conclusions & Recommended Next Steps",
        "sec7_act1": "1. **In-depth infrastructure check:** Continue monitoring associated subdomains and IP addresses.",
        "sec7_act2": (
            "2. **Beneficial ownership mapping:** Verify UBOs for connected entities via commercial and court registries."
        ),
        "sec7_act3": (
            "3. **Evidence preservation:** Export case graph data to GEXF/GraphML and secure evidentiary archives."
        ),
        "footer": "\n---\n*Report automatically compiled by IntelNexus Platform.*",
    },
    "uk": {
        "title": "Звіт про розслідування",
        "sanitized_badge": " [САНІТОВАНИЙ ЕКСПОРТ / ЗАХИСТ ДАНИХ]",
        "case_id": "ID справи",
        "export_mode": "Режим експорту",
        "mode_sanitized": "САНІТОВАНО (Публічний/GDPR)",
        "mode_full": "ПОВНИЙ (Внутрішній/Судовий)",
        "status": "Статус",
        "priority": "Пріоритет",
        "investigator": "Відповідальний слідчий",
        "generated": "Створено",
        "tags": "Теги",
        "no_tags": "Немає тегів",
        "sec1_title": "1. Резюме та слідча гіпотеза",
        "sec1_no_desc": "Детальний опис справи відсутній.",
        "sec1_stats": (
            "Всього зафіксовано **{entities} об'єктів** та **{relationships} зв'язків**. "
            "Усі докази криптографічно захищені у ланцюжку зберігання з **{evidence} зареєстрованими записами**.\n"
        ),
        "sec2_title": "2. Оцінка ризиків та перевірка санкцій",
        "sec2_sanction_alert": (
            "> [!CAUTION]\n> **КРИТИЧНЕ ПОПЕРЕДЖЕННЯ: Виявлено збіги з міжнародними санкційними списками!**"
        ),
        "sec2_no_sanctions": (
            "Жоден об'єкт у цій справі наразі не відповідає міжнародним санкційним спискам (OFAC/ЄС/ООН).\n"
        ),
        "sec3_title": "3. Ідентифіковані об'єкти",
        "sec3_type": "Тип",
        "sec3_count": "Кількість",
        "sec3_det_title": "Детальний список об'єктів",
        "sec3_th_name": "Назва",
        "sec3_th_type": "Тип",
        "sec3_th_conf": "Достовірність",
        "sec3_th_nato": "Оцінка НАТО",
        "sec3_th_alias": "Псевдоніми / Ключові атрибути",
        "sec4_title": "4. Аналіз мережі та ключові фігуранти (Метрики графа)",
        "sec4_top_intro": (
            "Наступні вузли визначені як ключові фігуранти мережі на основі PageRank та посередницької центральності:"
        ),
        "sec4_th_node": "Вузол",
        "sec4_th_score": "Мережевий бал",
        "sec4_th_degree": "Ступінь",
        "sec4_no_metrics": "Мережеві зв'язки для розрахунку центральності ще не зареєстровані.\n",
        "sec5_title": "5. Аналіз зв'язків та виявлені з'єднання",
        "sec5_th_from": "Від",
        "sec5_th_rel": "Зв'язок",
        "sec5_th_to": "До",
        "sec5_no_rels": "У цій справі ще не створено зв'язків між об'єктами.\n",
        "sec6_title": "6. Ланцюжок доказів та криптографічна простежуваність (Chain of Custody)",
        "sec6_status_label": "Статус ланцюжка доказів",
        "sec6_status_intact": "НЕПОРУШЕНИЙ ТА ДІЙСНИЙ",
        "sec6_status_tampered": "ВИЯВЛЕНО НЕВІДПОВІДНОСТІ",
        "sec6_validated_files": "Перевірено файлів",
        "sec6_th_title": "Назва",
        "sec6_th_collector": "Джерело збору",
        "sec6_th_hash": "Контрольна сума SHA-256",
        "sec6_th_mime": "MIME-тип",
        "sec7_title": "7. Висновки та рекомендовані дії",
        "sec7_act1": (
            "1. **Поглиблений моніторинг інфраструктури:** Продовжувати моніторинг пов'язаних субдоменів та IP-адрес."
        ),
        "sec7_act2": (
            "2. **Встановлення кінцевих бенефіціарів:** Перевірити бенефіціарних власників (UBO) "
            "через офіційні та судові реєстри."
        ),
        "sec7_act3": (
            "3. **Фіксація доказів:** Експортувати дані графа у формат GEXF/GraphML та зберегти копії доказів."
        ),
        "footer": "\n---\n*Звіт автоматично сформовано платформою IntelNexus Platform.*",
    },
}


class ReportGenerator:
    """
    Genererar strukturerade utredningsrapporter i Markdown och HTML baserat på
    fallets entiteter, grafrelationer, centralitetsanalys och beviskedja.
    Stödjer fullständig intern dossier och GDPR-sanitiserad export samt flerspråksstöd (sv, en, uk).
    """

    def generate_markdown_report(
        self,
        case_id: str,
        mode: str = "full",
        min_confidence: float = 0.6,
        locale: str = "sv",
    ) -> str:
        case = db.get_case(case_id)
        if not case:
            raise ValueError(f"Ärende {case_id} kunde inte hittas.")

        loc = locale.lower().strip()
        t = REPORT_TRANSLATIONS.get(loc) or REPORT_TRANSLATIONS.get("en") or REPORT_TRANSLATIONS["sv"]

        entities = db.list_entities(case_id=case_id)
        relationships = db.list_relationships(case_id=case_id)
        evidence_list = db.list_evidence(case_id=case_id)
        metrics: Dict[str, Any] = graph_store.compute_metrics(case_id)
        custody_audit = custody_manager.verify_case_custody(case_id)

        # Sanitiserat läge för publik/delad export
        is_sanitized = mode.lower() == "sanitized"
        if is_sanitized:
            entities, relationships = pii_sanitizer.sanitize_dossier(
                entities=entities,
                relationships=relationships,
                min_confidence_threshold=min_confidence,
                remove_innocent_contacts=True,
            )

        # Räkna entiteter per typ
        type_counts: Dict[str, int] = {}
        sanctioned_entities: List[str] = []
        for e in entities:
            etype = e.type.value if hasattr(e.type, "value") else str(e.type)
            type_counts[etype] = type_counts.get(etype, 0) + 1
            if e.attributes.get("sanctioned") is True:
                sanctioned_entities.append(f"{e.name} ({e.attributes.get('sanctions_program', 'Sanctioned')})")

        md: List[str] = []
        header_title = f"# {t['title']}: {case.title}"
        if is_sanitized:
            header_title += t["sanitized_badge"]
        md.append(header_title)
        md.append(f"**{t['case_id']}:** `{case.id}`  ")
        md.append(f"**{t['export_mode']}:** `{t['mode_sanitized'] if is_sanitized else t['mode_full']}`  ")
        md.append(
            f"**{t['status']}:** `{case.status.value.upper()}` | **{t['priority']}:** `{case.priority.value.upper()}`  "
        )
        md.append(f"**{t['investigator']}:** {case.investigator}  ")
        md.append(f"**{t['generated']}:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ")
        md.append(f"**{t['tags']}:** {', '.join(case.tags) if case.tags else t['no_tags']}  \n")
        md.append("---\n")

        # 1. Sammanfattning
        md.append(f"## {t['sec1_title']}")
        raw_desc = case.description or t["sec1_no_desc"]
        md.append(pii_sanitizer.mask_text(raw_desc) if is_sanitized else raw_desc)
        md.append(
            "\n"
            + t["sec1_stats"].format(
                entities=len(entities),
                relationships=len(relationships),
                evidence=len(evidence_list),
            )
        )

        # 2. Riskbedömning och sanktioner
        md.append(f"## {t['sec2_title']}")
        if sanctioned_entities:
            md.append(t["sec2_sanction_alert"])
            for se in sanctioned_entities:
                clean_se = pii_sanitizer.mask_text(se) if is_sanitized else se
                md.append(f"> * {clean_se}")
            md.append("")
        else:
            md.append(t["sec2_no_sanctions"])

        # 3. Entitetsöversikt
        md.append(f"## {t['sec3_title']}")
        md.append(f"| {t['sec3_type']} | {t['sec3_count']} |")
        md.append("| :--- | :--- |")
        for ent_t, count in sorted(type_counts.items()):
            md.append(f"| `{ent_t}` | {count} |")
        md.append("")

        md.append(f"### {t['sec3_det_title']}")
        md.append(
            f"| {t['sec3_th_name']} | {t['sec3_th_type']} | {t['sec3_th_conf']} | {t['sec3_th_nato']} | {t['sec3_th_alias']} |"
        )
        md.append("| :--- | :--- | :--- | :--- | :--- |")
        for e in entities[:30]:  # Begränsa till 30 för läsbarhet
            alias_str = ", ".join(e.aliases) if e.aliases else "-"
            attr_summary = []
            for k in ["org_number", "country", "city", "platform", "ip_version"]:
                if k in e.attributes:
                    attr_summary.append(f"{k}: {e.attributes[k]}")
            extra = f" [{'; '.join(attr_summary)}]" if attr_summary else ""
            ent_type_val = e.type.value if hasattr(e.type, "value") else str(e.type)
            clean_name = e.name.replace("|", "/")
            adm_badge = f"[{e.admiralty_code}]"
            md.append(
                f"| {clean_name} | `{ent_type_val}` | {e.confidence_score * 100:.0f}% | `{adm_badge}` | {alias_str}{extra} |"
            )
        md.append("")

        # 4. Nätverks- och grafanalys
        md.append(f"## {t['sec4_title']}")
        top_inf = metrics.get("top_influencers", [])
        if top_inf:
            md.append(t["sec4_top_intro"])
            md.append("")
            md.append(
                f"| {t['sec4_th_node']} | {t['sec3_th_type']} | {t['sec4_th_score']} | PageRank | Betweenness | {t['sec4_th_degree']} |"
            )
            md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for item in top_inf[:8]:
                md.append(
                    f"| **{item['name']}** | `{item['type']}` | {item['score']} | {item['pagerank']} | {item['betweenness']} | {item['degree']} |"
                )
            md.append("")
        else:
            md.append(t["sec4_no_metrics"])

        # 5. Länkanalys
        md.append(f"## {t['sec5_title']}")
        if relationships:
            md.append(f"| {t['sec5_th_from']} | {t['sec5_th_rel']} | {t['sec5_th_to']} | {t['sec3_th_conf']} |")
            md.append("| :--- | :--- | :--- | :--- |")
            ent_map = {e.id: e.name for e in entities}
            for r in relationships[:40]:
                src_name = ent_map.get(r.source_id, r.source_id).replace("|", "/")
                tgt_name = ent_map.get(r.target_id, r.target_id).replace("|", "/")
                rel_t = r.relation_type.value if hasattr(r.relation_type, "value") else str(r.relation_type)
                md.append(f"| {src_name} | **`{rel_t}`** | {tgt_name} | {r.confidence_score * 100:.0f}% |")
            md.append("")
        else:
            md.append(t["sec5_no_rels"])

        # 6. Beviskedja & Chain of Custody
        md.append(f"## {t['sec6_title']}")
        status_text = (
            t["sec6_status_intact"] if custody_audit.get("chain_of_custody_intact") else t["sec6_status_tampered"]
        )
        md.append(f"**{t['sec6_status_label']}:** `{status_text}`  ")
        md.append(
            f"**{t['sec6_validated_files']}:** {custody_audit.get('valid_count')} / {custody_audit.get('total_items')}  \n"
        )

        if evidence_list:
            md.append(
                f"| {t['sec6_th_title']} | {t['sec6_th_collector']} | {t['sec6_th_hash']} | {t['sec6_th_mime']} |"
            )
            md.append("| :--- | :--- | :--- | :--- |")
            for ev in evidence_list[:25]:
                short_hash = f"`{ev.sha256[:12]}...{ev.sha256[-8:]}`"
                clean_ev_title = ev.title.replace("|", "/")
                md.append(f"| {clean_ev_title} | `{ev.collector_plugin or 'manual'}` | {short_hash} | {ev.mime_type} |")
            md.append("")

        # 7. Slutsatser
        md.append(f"## {t['sec7_title']}")
        md.append(t["sec7_act1"])
        md.append(t["sec7_act2"])
        md.append(t["sec7_act3"])
        md.append(t["footer"])

        full_report = "\n".join(md)
        if is_sanitized:
            full_report = pii_sanitizer.mask_text(full_report)
        return full_report


report_generator = ReportGenerator()
