# OpenIntel-OSINT (v2.0)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![Graph: NetworkX / Neo4j](https://img.shields.io/badge/Graph-NetworkX%20%7C%20Neo4j-orange.svg)]()
[![BYOAK: AES-256-GCM](https://img.shields.io/badge/Vault-AES--256--GCM-green.svg)]()

En modulär, öppen källkodsbaserad plattform för insamling, länk- och grafanalys, beviskedjehantering och rapportgenerering av öppen underrättelsedata (OSINT) med stöd för **rollbaserade arbetsytor (Personas)** och adaptiva dashboards.

Systemet stödjer allt från snabba, guidade bakgrundskontroller för privatpersoner till forensiska utredningar för rättsväsende, finansiell underrättelseverksamhet (AML/UBO), undersökande journalistik och geopolitisk analys.

---

## 🏛️ Rollbaserad Arkitektur (Adaptive Personas)

Systemet anpassar gränssnittet, vilka moduler som laddas och vilka sökguider (Playbooks) som föreslås baserat på vald roll:

```
                    +--------------------------------+
                    |    ANVÄNDARE VÄLJER PROFIL     |
                    +--------------------------------+
                                    │
    ┌──────────────┬────────────────┼────────────────┬──────────────┐
    ▼              ▼                ▼                ▼              ▼
[Privatperson] [Rättsväsende] [Journalistik]   [Finans / AML] [Geopolitik / Ambassad]
    │              │                │                │              │
    ▼              ▼                ▼                ▼              ▼
Enkel guide    Forensisk vy    Källskydd        UBO & Nätverk  Satellit & Kartor
Catfish-koll   Kedja av bevis  Metadata-tvätt   Sanktionslistor Transpondrar (ADS-B)
Förenklad vy   Domstolsdata    Dokumentläckor   Kryptospårning Krisflöden & Media
```

### Stödda Roller och Arbetsytor
1. **Privatperson (`dating_safety`):** Säkerhetskoll vid dejting eller köp/sälj. Wizard-layout med omvänd bildsökning (catfish-detektering), VoIP/burner-nummerkontroll, romansbedrägerispärr och klartextbedömning.
2. **Rättsväsende & Polis (`law_enforcement`):** Forensisk arbetsyta med obruten beviskedja (SHA-256/512), telekom-/IP-korrelation och export strukturerad för förundersökningsprotokoll (FUP).
3. **Undersökande Journalistik (`journalism`):** Dokumentvalv med Metadata Stripper (radering av EXIF/GPS/enhetsdata för att skydda visselblåsare), OCR/NER-extrahering och diarier.
4. **Privatdetektiv & Konsult (`private_investigator`):** 360-graders dossier-vy med person-/bolagskorsreferenser, fordon, adresser och social footprint över 300+ forum.
5. **Finansanalytiker & Compliance (`finance_aml`):** Anti-Money Laundering (AML), rekursiv upplösning av verklig huvudman (UBO), offshore-kartläggning och blockkedjetransaktioner.
6. **Geopolitisk Analytiker (`geopolitical`):** Kartcentrerad situationsmedvetenhet med NASA FIRMS termiska satellitbränder och ADS-B flygtranspondrar.
7. **Diplomatisk Beskickning (`embassy`):** Fysisk perimeterövervakning med geofence-larm kring ambassader och residens i kriszoner.

---

## 🔐 Bring Your Own API Key (BYOAK) & Lokalt Valv

* **Lokal Kryptering:** Alla API-nycklar, tokens och hemligheter krypteras i vila på användarens maskin med **AES-256-GCM**.
* **Zero-Knowledge:** Inga nycklar skickas någonsin till centrala servrar utöver den avsedda tjänstens officiella endpoint.
* **Stödda Integrationer:**
  * **Svenska & Nordiska register:** Bolagsverket, InfoTorg, Roaring, SCB.
  * **Internationella bolag & AML:** OpenCorporates, OpenSanctions.
  * **Cyber & Infrastruktur:** Shodan, Censys, VirusTotal, crt.sh.
  * **Geoint & Rörelse:** NASA FIRMS, OpenSky Network (ADS-B), OpenStreetMap.
  * **Kryptovalutor:** Etherscan, Blockstream.
  * **Säkerhet & Läckor:** HaveIBeenPwned API.

---

## 🚀 Kom Igång

### 1. Backend (FastAPI & Zero-Setup SQLite/Graph)
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r backend/requirements.txt
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Swagger-dokumentation: [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Frontend (Next.js 14)
```powershell
cd frontend
npm install
npm run dev
```
Webbgränssnitt: [http://localhost:3000](http://localhost:3000).

### 3. Docker Compose (Enterprise Stack)
```bash
docker compose up -d
```
Startar PostgreSQL (`pgvector`), Neo4j, Redis och MinIO S3.

---

## 🧪 Köra testsviten

Testsviten omfattar 23 automatiserade tester som verifierar API, krypterat valv, transforms, grafmått och playbooks:

```powershell
$env:PYTHONPATH="backend"
pytest backend/tests -v
```

---

## ⚖️ Juridiska Skyddsräcken & Användarvillkor (Ethics by Design)

* **GDPR & Local-First:** All utredningsdata stannar lokalt. Ingen telemetri spårar användarens sökningar.
* **Anti-Stalking:** Systemet tillhandahåller inte realtidsspårning av privatpersoners fysiska positioner eller intrång i privata enheter. I privatpersonsläget exponeras endast *defensiv verifiering*.
* **Lagliga Källor:** Data hämtas endast från öppna protokoll, officiella API:er och användarens egna licensierade nycklar.
