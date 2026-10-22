# OpenIntel-OSINT

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![Graph: NetworkX / Neo4j](https://img.shields.io/badge/Graph-NetworkX%20%7C%20Neo4j-orange.svg)]()

En modern, öppen källkodsbaserad plattform för informationsinsamling, länk- och grafanalys, beviskedjehantering och rapportgenerering av öppen underrättelsedata (OSINT).

Systemet fungerar som en enhetlig utredningsmiljö för både enskilda granskningar (bakgrundskontroller, digitala fotspår, infrastruktur) och komplexa utredningar (hotaktörer, bolagsstrukturer och ekonomisk brottslighet).

---

## 🏛️ Systemarkitektur

```
+--------------------------------------------------------------------------+
|                       ANVÄNDARGRÄNSSNITT (Next.js)                       |
|   • Interaktiv grafduk (Cytoscape.js) med nodexpansion & layoutmotor    |
|   • Tidslinjevy (kronologiska händelser och relationer)                  |
|   • Kartvy (geografisk visualisering med Leaflet & OpenStreetMap)        |
|   • Beviskedjelogg med realtids SHA-256 verifiering                      |
|   • Rapporteditor & automatiserad PDF/Markdown export                    |
+--------------------------------------------------------------------------+
                                    │  REST / WebSocket
                                    ▼
+--------------------------------------------------------------------------+
|                      API GATEWAY (FastAPI / Python)                      |
|   • Ärendehantering (/api/cases), Entiteter & Länkar (/api/entities)     |
|   • Transform Engine (/api/transforms), Grafalgoritmer (/api/graph)      |
|   • Beviskedja (/api/evidence), AI/NLP & Textanalys (/api/analysis)      |
+--------------------------------------------------------------------------+
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
+──────────────+           +──────────────────+          +---------------+
|  INGESTION   |           |  GRAPH & ENTITY  |          |   ANALYSIS &  |
|    ENGINE    |           |    RESOLUTION    |          |   ENRICHMENT  |
| (Transforms) |           |  (Länkanalys)    |          |  (LLM & NLP)  |
+──────────────+           +──────────────────+          +---------------+
       │                            │                            │
       └────────────────────────────┼────────────────────────────┘
                                    ▼
+--------------------------------------------------------------------------+
|                          PERSISTENSLAGER                                 |
|   • Zero-Setup Lokal Drift: SQLite/JSON Metadata + Persistent Graph      |
|   • Enterprise Drift: PostgreSQL + Neo4j + Redis + MinIO S3              |
+--------------------------------------------------------------------------+
```

---

## ✨ Kärnfunktioner

### 1. Ingestion Engine & Modulära Transforms
* **Startpunkter (Seeds):** Domän, IP-adress, person, organisation, e-post, telefon, användarnamn, kryptoplånbok, plats och dokument.
* **Färdiga kärntransforms:**
  1. `DNS & WHOIS/RDAP`: Slår upp A, AAAA, MX, TXT, NS-poster och registrar via RDAP.
  2. `Company Registry`: Extraherar bolagsstruktur, VD, styrelseledamöter, ägare och registrerad adress.
  3. `Social Footprint Checker`: Asynkron kontroll över 20+ plattformar (GitHub, Reddit, GitLab, Keybase, Steam, etc.).
  4. `IP & GeoIP`: Omvänd DNS (PTR), ASN, ISP och exakta GPS-koordinater.
  5. `Certificate Transparency (CT)`: Automatisk upptäckt av subdomäner via crt.sh.
  6. `Sanctions Screening`: Matchning mot internationella sanktionslistor (OFAC, EU, FN).
  7. `EXIF & Media Extractor`: Extraherar bildmetadata, kameramodell, datum och GPS-taggar.

### 2. Graf- och länkanalys
* **Grafmotor:** Nativ NetworkX-grafmotor med noder och riktade kanter (`OWNS`, `DIRECTOR_OF`, `RESOLVES_TO`, `SUBDOMAIN_OF`, `LOCATED_AT`, etc.).
* **Nätverksalgoritmer:** Beräknar PageRank, Betweenness centrality och Degree centrality för att automatiskt identifiera nyckelaktörer och central infrastruktur.
* **Vägsökning:** Identifierar kortaste vägen (Shortest Path) mellan två godtyckliga noder.
* **Export:** Exportera nätverksgrafen till **GEXF** (för Gephi), **GraphML**, **CSV** och **JSON**.

### 3. Entitetsupplösning (Deduplicering)
* **Deterministisk:** Automatisk sammanslagning vid identiska unika nycklar (organisationsnummer, momsregistreringsnummer, kryptoplånbok, etc.).
* **Probabilistisk:** Viktning baserad på Jaro-Winkler likhetsavstånd för namn och alias med konfidenspoäng ($0.0 - 1.0$).

### 4. Beviskedja (Chain of Custody)
* **Kryptografisk bevisföring:** Alla hämtade sidor och API-svar hashas omedelbart med SHA-256 och lagras i oföränderlig lagring.
* **Web Snapshotting:** Inbyggd motor för att frysa webbsidor och rådata med HTTP-huvuden och tidsstämplar.
* **Integritetsrevision:** Kör fullständig revision med ett klick för att matematiskt bekräfta att inga bevisfiler har manipulerats.

### 5. AI- & NLP-textanalys och Rapportgenerering
* **Named Entity Recognition (NER):** Klistra in artiklar eller domstolsprotokoll för att automatiskt extrahera personer, företag, IP-adresser, domäner och krypto-adresser.
* **Automatiserade Rapporter:** Genererar utredningsrapporter i Markdown och utskriftsklar PDF/HTML.

---

## 🚀 Snabbstart

### Alternativ A: Lokal körning (Zero External Setup)

Plattformen kan köras lokalt utan externa databasservrar då den har ett inbyggt, persistent SQLite- och grafminneslager.

#### 1. Backend
```bash
# Skapa och aktivera virtuell miljö
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # Linux/macOS

# Installera beroenden
pip install -r backend/requirements.txt

# Starta API Gateway
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
API:et och interaktiv Swagger-dokumentation finns nu på: `http://localhost:8000/docs`.

#### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
Öppna webbläsaren på `http://localhost:3000`.

---

### Alternativ B: Docker Compose (Produktionsmiljö)

Startar hela mikrotjänstarkitekturen inklusive PostgreSQL, Neo4j, Redis och MinIO:

```bash
docker compose up -d
```

| Tjänst | Adress | Användarnamn / Lösenord |
| :--- | :--- | :--- |
| **Frontend UI** | `http://localhost:3000` | - |
| **Backend API Gateway** | `http://localhost:8000/docs` | - |
| **Neo4j Browser** | `http://localhost:7474` | `neo4j` / `openintel_neo4j_pass` |
| **MinIO Console** | `http://localhost:9001` | `openintel_minio_admin` / `openintel_minio_secret_key` |

---

## 🧪 Köra tester

Backend innehåller en komplett testsvit med automatiserade enhetstester och integrationstester:

```bash
$env:PYTHONPATH="backend"
pytest backend/tests -v
```

---

## ⚖️ Juridiska och etiska principer (Ethics by Design)

* **GDPR & Local-First:** Plattformen stödjer lokal lagring utan att data exponeras till tredje part.
* **Anti-stalking:** Systemet tillhandahåller inte realtidsspårning av privatpersoners mobila enheter eller exploatering av dataläckor.
* **Offentliga källor:** All datainsamling utgår från öppna protokoll, register och officiella API:er.
