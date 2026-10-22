from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import api_router
from app.db.database import db
from app.db.graph_store import graph_store
from app.models.case import CaseCreateRequest, CasePriority
from app.models.entity import Entity, EntityType, ProvenanceRecord
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import EvidenceItem


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed default investigation case if empty
    cases = db.list_cases()
    if len(cases) == 0:
        demo_case = db.create_case(
            CaseCreateRequest(
                title="Operation ShadowNet: Cyberinfrastruktur & Bolagskartläggning",
                description="Underrättelseutredning kring misstänkt hotaktörs infrastruktur, skalföretag och digitala fotspår.",
                priority=CasePriority.HIGH,
                tags=["threat-intelligence", "infrastructure", "corporate-investigation"],
                investigator="Chief OSINT Analyst",
            )
        )

        case_id = demo_case.id

        # Skapa startnoder (Seeds)
        prov = ProvenanceRecord(
            source_url="https://crt.sh/?q=target-intel.com",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            collector_plugin="seed_ingest",
            note="Initierande målseed",
        )

        domain_seed = db.save_entity(
            Entity(
                case_id=case_id,
                type=EntityType.DOMAIN,
                name="target-intel.com",
                provenance=[prov],
            )
        )

        ip_node = db.save_entity(
            Entity(
                case_id=case_id,
                type=EntityType.IP,
                name="185.220.101.5",
                attributes={
                    "country": "Sweden",
                    "city": "Stockholm",
                    "latitude": 59.3293,
                    "longitude": 18.0686,
                    "asn": "AS42237",
                },
                provenance=[prov],
            )
        )

        company_node = db.save_entity(
            Entity(
                case_id=case_id,
                type=EntityType.ORGANIZATION,
                name="Nordic Tech AB",
                attributes={"org_number": "556123-4567", "jurisdiction": "SE", "status": "Aktivt"},
                provenance=[prov],
            )
        )

        person_node = db.save_entity(
            Entity(
                case_id=case_id,
                type=EntityType.PERSON,
                name="Anders Lindqvist",
                aliases=["shadow_runner", "alindqvist_sec"],
                attributes={"role": "VD", "birth_year": 1984, "nationality": ["SE"]},
                provenance=[prov],
            )
        )

        subdomain_node = db.save_entity(
            Entity(
                case_id=case_id,
                type=EntityType.DOMAIN,
                name="vpn.target-intel.com",
                attributes={"parent_domain": "target-intel.com"},
                provenance=[prov],
            )
        )

        location_node = db.save_entity(
            Entity(
                case_id=case_id,
                type=EntityType.LOCATION,
                name="Kungsgatan 12, Stockholm",
                attributes={"latitude": 59.3361, "longitude": 18.0658, "country": "Sweden", "city": "Stockholm"},
                provenance=[prov],
            )
        )

        # Skapa relationer
        db.save_relationship(
            Relationship(
                case_id=case_id,
                source_id=domain_seed.id,
                target_id=ip_node.id,
                relation_type=RelationshipType.RESOLVES_TO,
                provenance=[prov],
            )
        )

        db.save_relationship(
            Relationship(
                case_id=case_id,
                source_id=subdomain_node.id,
                target_id=domain_seed.id,
                relation_type=RelationshipType.SUBDOMAIN_OF,
                provenance=[prov],
            )
        )

        db.save_relationship(
            Relationship(
                case_id=case_id,
                source_id=subdomain_node.id,
                target_id=ip_node.id,
                relation_type=RelationshipType.RESOLVES_TO,
                provenance=[prov],
            )
        )

        db.save_relationship(
            Relationship(
                case_id=case_id,
                source_id=person_node.id,
                target_id=company_node.id,
                relation_type=RelationshipType.DIRECTOR_OF,
                attributes={"role": "VD"},
                provenance=[prov],
            )
        )

        db.save_relationship(
            Relationship(
                case_id=case_id,
                source_id=company_node.id,
                target_id=domain_seed.id,
                relation_type=RelationshipType.OWNS,
                provenance=[prov],
            )
        )

        db.save_relationship(
            Relationship(
                case_id=case_id,
                source_id=company_node.id,
                target_id=location_node.id,
                relation_type=RelationshipType.LOCATED_AT,
                provenance=[prov],
            )
        )

        # Skapa initial bevispost
        db.save_evidence(
            EvidenceItem(
                case_id=case_id,
                title="Certificate Transparency Log for target-intel.com",
                file_path="initial_target_cert.json",
                file_size_bytes=1024,
                mime_type="application/json",
                sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                source_url="https://crt.sh/?q=target-intel.com",
                collector_plugin="seed_ingest",
            )
        )

        # Ladda in i grafminnet
        graph_store.reload_case_graph(case_id)

    yield


app = FastAPI(
    title="IntelNexus Platform",
    version=settings.APP_VERSION,
    description="Neutral integrations- och fusionshubb för externa API-leverantörer med datainsamling, länk- och grafanalys, beviskedja och rapportgenerering.",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs_url": "/docs",
        "api_prefix": "/api",
    }


@app.get("/health")
def health():
    return {"status": "healthy", "database": "connected"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
