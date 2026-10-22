import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import dns.resolver
import httpx
from app.db.object_store import object_store
from app.models.entity import Entity, EntityType
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import EvidenceItem
from .base import BaseTransform, TransformResult


class DnsWhoisTransform(BaseTransform):
    name = "dns_whois_transform"
    display_name = "DNS & WHOIS/RDAP Network Analysis"
    description = "Slår upp DNS-poster (A, AAAA, MX, TXT, NS) och hämtar domänregistreringsdata via RDAP."
    category = "network"
    supported_types: Set[EntityType] = {EntityType.DOMAIN}

    @staticmethod
    def normalize_domain(domain_str: str) -> str:
        """Normaliserar domännamn genom att strippa protokoll, portar och avslutande punkter."""
        d = domain_str.strip().lower()
        if d.startswith("http://"):
            d = d[7:]
        elif d.startswith("https://"):
            d = d[8:]
        d = d.split("/")[0].split(":")[0]
        return d.rstrip(".")

    async def execute(self, seed: Entity, options: Optional[Dict[str, Any]] = None) -> TransformResult:
        start_time = time.time()
        logs: List[str] = []
        domain_name = seed.name.strip().lower()
        if domain_name.startswith("http://"):
            domain_name = domain_name[7:]
        if domain_name.startswith("https://"):
            domain_name = domain_name[8:]
        domain_name = domain_name.split("/")[0].split(":")[0]

        logs.append(f"Startar DNS/RDAP-analys för domän: {domain_name}")

        new_entities: List[Entity] = []
        new_relationships: List[Relationship] = []
        evidence_items: List[EvidenceItem] = []

        dns_records: Dict[str, List[str]] = {"A": [], "AAAA": [], "MX": [], "TXT": [], "NS": [], "CNAME": []}

        # 1. DNS Lookup (via dnspython med fallback till Cloudflare DoH)
        loop = asyncio.get_event_loop()

        def _resolve_dns():
            res = {}
            for rtype in ["A", "AAAA", "MX", "TXT", "NS", "CNAME"]:
                try:
                    answers = dns.resolver.resolve(domain_name, rtype, lifetime=3.0)
                    if rtype == "MX":
                        res[rtype] = [f"{r.preference} {r.exchange.to_text().rstrip('.')}" for r in answers]
                    else:
                        res[rtype] = [r.to_text().strip('"').rstrip(".") for r in answers]
                except Exception:
                    res[rtype] = []
            return res

        try:
            dns_records = await loop.run_in_executor(None, _resolve_dns)
            logs.append(f"DNS-uppslag slutfört: {sum(len(v) for v in dns_records.values())} poster funna.")
        except Exception as e:
            logs.append(f"Lokal DNS-upplösning stötte på fel ({str(e)}), provar DoH...")

        # DoH Fallback om A-poster saknas
        if not dns_records.get("A"):
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get(
                        f"https://cloudflare-dns.com/dns-query?name={domain_name}&type=A",
                        headers={"Accept": "application/dns-json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        answers = data.get("Answer", [])
                        dns_records["A"] = [ans["data"] for ans in answers if ans.get("type") == 1]
                        logs.append(f"DoH A-poster hämtade: {dns_records['A']}")
            except Exception as e:
                logs.append(f"DoH fallback misslyckades: {str(e)}")

        # 2. RDAP Lookup (modern WHOIS)
        rdap_data: Dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                rdap_url = f"https://rdap.org/domain/{domain_name}"
                logs.append(f"Hämtar RDAP från {rdap_url}")
                rdap_resp = await client.get(rdap_url, follow_redirects=True)
                if rdap_resp.status_code == 200:
                    rdap_data = rdap_resp.json()
                    logs.append("RDAP-svar mottaget och avkodat.")
                else:
                    logs.append(f"RDAP returnerade statuskod: {rdap_resp.status_code}")
        except Exception as e:
            logs.append(f"RDAP-förfrågan gav fel: {str(e)}")

        # 3. Skapa bevispost med SHA-256
        combined_payload = {
            "target_domain": domain_name,
            "dns_records": dns_records,
            "rdap": rdap_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        case_id = seed.case_id or "default_case"
        rel_path, sha256_hash, size = object_store.store_json(
            case_id=case_id,
            filename=f"dns_rdap_{domain_name}_{int(time.time())}.json",
            data_dict=combined_payload,
            subfolder="dns",
        )
        evidence = EvidenceItem(
            case_id=case_id,
            title=f"DNS & RDAP query result for {domain_name}",
            file_path=rel_path,
            file_size_bytes=size,
            mime_type="application/json",
            sha256=sha256_hash,
            source_url=f"dns://{domain_name}",
            collector_plugin=self.name,
            metadata={"domain": domain_name, "records_found": sum(len(v) for v in dns_records.values())},
        )
        evidence_items.append(evidence)

        prov = self.create_provenance(
            source_url=f"dns://{domain_name}",
            sha256=sha256_hash,
            note=f"Hämtat via {self.display_name}",
        )

        # 4. Generera noder & relationer
        # IP-noder (A-poster)
        for ip_addr in dns_records.get("A", []):
            ip_entity = Entity(
                type=EntityType.IP,
                name=ip_addr,
                attributes={"ip_version": "IPv4", "domain": domain_name},
                provenance=[prov],
                case_id=seed.case_id,
            )
            new_entities.append(ip_entity)
            rel = Relationship(
                source_id=seed.id,
                target_id=ip_entity.id,
                relation_type=RelationshipType.RESOLVES_TO,
                attributes={"dns_record": "A"},
                provenance=[prov],
                case_id=seed.case_id,
            )
            new_relationships.append(rel)

        # IPv6-noder (AAAA-poster)
        for ip6_addr in dns_records.get("AAAA", []):
            ip6_entity = Entity(
                type=EntityType.IP,
                name=ip6_addr,
                attributes={"ip_version": "IPv6", "domain": domain_name},
                provenance=[prov],
                case_id=seed.case_id,
            )
            new_entities.append(ip6_entity)
            rel = Relationship(
                source_id=seed.id,
                target_id=ip6_entity.id,
                relation_type=RelationshipType.RESOLVES_TO,
                attributes={"dns_record": "AAAA"},
                provenance=[prov],
                case_id=seed.case_id,
            )
            new_relationships.append(rel)

        # MX-servrar
        for mx_val in dns_records.get("MX", []):
            mx_host = mx_val.split()[-1].rstrip(".")
            mx_entity = Entity(
                type=EntityType.DOMAIN,
                name=mx_host,
                attributes={"role": "mail_exchange", "raw_mx": mx_val},
                provenance=[prov],
                case_id=seed.case_id,
            )
            new_entities.append(mx_entity)
            rel = Relationship(
                source_id=seed.id,
                target_id=mx_entity.id,
                relation_type=RelationshipType.COMMUNICATES_WITH,
                attributes={"service": "email_server", "raw_mx": mx_val},
                provenance=[prov],
                case_id=seed.case_id,
            )
            new_relationships.append(rel)

        # Nameservers
        for ns_val in dns_records.get("NS", []):
            ns_host = ns_val.rstrip(".")
            ns_entity = Entity(
                type=EntityType.DOMAIN,
                name=ns_host,
                attributes={"role": "authoritative_nameserver"},
                provenance=[prov],
                case_id=seed.case_id,
            )
            new_entities.append(ns_entity)
            rel = Relationship(
                source_id=seed.id,
                target_id=ns_entity.id,
                relation_type=RelationshipType.ASSOCIATED_WITH,
                attributes={"role": "nameserver"},
                provenance=[prov],
                case_id=seed.case_id,
            )
            new_relationships.append(rel)

        # Registrant / Registrar från RDAP
        entities_in_rdap = rdap_data.get("entities", [])
        for ent in entities_in_rdap:
            roles = ent.get("roles", [])
            vcard = ent.get("vcardArray", [])
            ent_name = None
            if len(vcard) > 1:
                for item in vcard[1]:
                    if item[0] == "fn":
                        ent_name = item[3]
                        break
            if not ent_name:
                ent_name = ent.get("handle")

            if ent_name and ("registrar" in roles or "registrant" in roles):
                reg_entity = Entity(
                    type=EntityType.ORGANIZATION,
                    name=ent_name,
                    attributes={"roles": roles, "handle": ent.get("handle")},
                    provenance=[prov],
                    case_id=seed.case_id,
                )
                new_entities.append(reg_entity)
                rel = Relationship(
                    source_id=seed.id,
                    target_id=reg_entity.id,
                    relation_type=RelationshipType.REGISTERED_BY,
                    attributes={"roles": roles},
                    provenance=[prov],
                    case_id=seed.case_id,
                )
                new_relationships.append(rel)

        exec_time = time.time() - start_time
        logs.append(
            f"DNS/RDAP transform klar på {exec_time:.2f}s. Skapade {len(new_entities)} entiteter och {len(new_relationships)} relationer."
        )

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
