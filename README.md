<p align="center"><img src="frontend/public/logo.svg" width="320" alt="IntelNexus Platform Logo"></p>

# IntelNexus Platform (v3.0)

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![Graph: NetworkX / Neo4j](https://img.shields.io/badge/Graph-NetworkX%20%7C%20Neo4j-orange.svg)]()
[![BYOAK: AES-256-GCM](https://img.shields.io/badge/Vault-AES--256--GCM-green.svg)]()
[![Tests: 85 Passed](https://img.shields.io/badge/Tests-85%20Passed-brightgreen.svg)]()
[![Coverage: 85.97%](https://img.shields.io/badge/Coverage-85.97%25-brightgreen.svg)]()

**IntelNexus Platform** är en modulär, neutral integrations- och fusionshubb för externa API-leverantörer med stöd för öppen underrättelseinsamling (OSINT), länk- och grafanalys, oföränderlig beviskedjehantering (Chain of Custody), FinOps-kvotkontroll och automatiserad rapportgenerering. Plattformen fungerar som en oberoende orkestreringsmotor som sammanför kommersiella och öppna datakällor under ett enhetligt Plugin-SDK.

---

## 🌟 Huvudfunktioner i IntelNexus Platform

* **Neutral API-integrationshubb:** Standardiserat Plugin-SDK (`BaseOSINTPlugin`) med enhetligt in- och utdatakontrakt (`EntityInput`, `EntityOutput`, `RelationOutput`, `TransformResult`) för sömlös inkoppling av externa API-leverantörer.
* **NATO Admiralty System (A1–F6):** Källans tillförlitlighet (A–F) och informationens trovärdighet (1–6) är djupt integrerat i datamodellerna, graferna och beviskorten för strikt underrättelsevärdering.
* **FinOps API-Kostnadskontroll:** Token Bucket rate limiting via Redis och trådsäker in-memory fallback, deterministisk SHA-256 caching med differentierad TTL samt en Dry-Run-kostnadsestimator i realtid (`/api/v1/transforms/dry-run`).
* **OpSec Egress Engine:** Policystyrd nätverkstrafik (`DIRECT`, `PROXY_RESIDENTIAL`, `TOR_STRICT`) med SOCKS5 DNS-läckageskydd och Tor-integration.
* **Flerspråksstöd (i18n):** Fullständigt flerspråksstöd med snabbväxlare i gränssnittet för engelska (`en`), svenska (`sv`) och ukrainska (`uk`), inklusive flerspråkig rapportgenerator. Ryska (`ru`) har uttryckligen utelämnats.
* **Frivillig 2FA & Step-Up Elevation:** Strikt valfritt (opt-in) skydd med FIDO2/WebAuthn hårdvarunycklar, RFC 6238 TOTP och kryptografiska engångsreservkoder.
* **Lokal Kryptering (BYOAK):** Bring-Your-Own-API-Key med lokal AES-256-GCM kryptering i vila.
* **GDPR & PII Sanitizer:** Automatisk maskering av svenskt personnummer (`YYYYMMDD-****`), adresser och oskyldiga tredje parter vid rapportexport.

---

## 🏛️ Rollbaserad Arkitektur (9 Specialiserade Personas)

Systemet anpassar gränssnitt, visualiseringar, aktiva widgets och rekommenderade API-nycklar baserat på 9 specialiserade utredarroller:

1. **Allmän Utredare (`investigator`):** Allmän personkartläggning, telefon/e-post-pivoter och dejtingsäkerhet.
2. **Länkanalytiker & Grafer (`analyst`):** Djup entitetskartläggning, nätverksmått, PageRank-centralitet och multirelationella kunskapsgrafer.
3. **Efterlevnad & Sanktioner (`compliance_officer`):** Screening mot internationella sanktionslistor (OFAC, EU, FN), PEP och bolagsregister.
4. **Systemadministratör (`administrator`):** Övervakning av systemhälsa, FinOps API-kvoter, revisionsloggar och nyckeladministration.
5. **Granskande Journalist & Visselblåsare (`journalist_whistleblower`):** Maximal OpSec, metadatarensning (`MetadataStripper`), kryptografisk beviskedja och källskydd.
6. **Polis & Åklagare (`law_enforcement_prosecutor`):** Rättslig bevisstandard med obruten Chain of Custody (SHA-256) och domstolsstrukturerade rapporter.
7. **Bolags- & Finansutredare (`corporate_fraud_investigator`):** Spårning av verkliga huvudmän (UBO), skalbolagskedjor och finansiell forensik.
8. **Cyber Threat Intelligence (`cyber_threat_intelligence`):** Hotaktörsanalys, Shodan/VirusTotal-pivoter, IoC-grafer, sandbox-analys och malware-infrastruktur.
9. **Mänskliga Rättigheter & Faktagranskning (`fact_checking_human_rights`):** Bellingcat-modell för verifiering av öppet källmaterial, GEOINT i konfliktzoner och bevisbevarande vid krigsbrottsutredningar.

---

## 🔐 Bring Your Own API Key (BYOAK) & Lokalt Valv

* **Lokal Kryptering:** Alla API-nycklar krypteras i vila på utredarens maskin med **AES-256-GCM**.
* **Zero-Knowledge:** Inga nycklar sänds någonsin till centrala servrar utöver den avsedda externa tjänstens endpoint.
* **Stödda Integrationer:**
  * **Svenska & Nordiska register:** Bolagsverket, InfoTorg, Roaring, SCB.
  * **Internationella bolag & AML:** OpenCorporates, OpenSanctions.
  * **Cyber & Infrastruktur:** Shodan, Censys, VirusTotal, crt.sh, Whois.
  * **Geoint & Rörelse:** NASA FIRMS, OpenSky Network (ADS-B), OpenStreetMap.
  * **Kryptovalutor:** Etherscan, Blockstream.
  * **Säkerhet & Läckor:** HaveIBeenPwned API.

---

## 🛡️ Frivillig Tvåfaktorsautentisering (2FA) & Step-Up Skydd

* **Strikt Frivilligt (Opt-In):** Plattformen fungerar till 100 % utan 2FA-krav tills användaren explicit väljer att aktivera det.
* **FIDO2 / WebAuthn:** Phishing-resistenta hårdvarunycklar (YubiKey, Nitrokey, Touch ID, Windows Hello) via W3C WebAuthn med kloningsskydd (`sign_count`).
* **TOTP (RFC 6238):** Kompatibelt med offline-autentiseringsappar (Aegis, YubiKey Authenticator, 1Password, Bitwarden).
* **Engångsnödkoder:** 10 kryptografiska engångskoder hashade i databasen med SHA-256 för att förhindra lockout.
* **Step-Up Elevation:** 15 minuters behörighetsfönster som låser upp det lokala AES-256 API-valvet vid känsliga moment.

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
API-dokumentation: [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Frontend (Next.js 14)
```powershell
cd frontend
npm install
npm run dev
```
Webbgränssnitt: [http://localhost:3000](http://localhost:3000).

### 3. Docker Compose (Enterprise Stack & Tor Egress)
```bash
docker compose up -d
```
Startar PostgreSQL (`pgvector`), Neo4j, Redis, MinIO S3 samt Tor SOCKS5-proxy.

---

## 🧪 Säkerhetsgranskning & Automatiserad Testsvit

Testsviten omfattar **85 automatiserade tester** med **85.97 % kodtäckning** (över tröskelkravet på $\ge 85.0\%$):
* **Fas 1 (Statisk analys & SAST):** `ruff check` (0 fel), `ruff format` (100%), `mypy` (69 källkodsfiler), `bandit` SAST (8 034 rader kod skannade, 0 sårbarheter), `pip-audit` SCA (0 kända CVE:er) samt Next.js ESLint & TypeScript typkontroll.
* **Fas 2 (Enhetstester & Auth-matris):** Deterministisk normalisering, AES-GCM manipulationstest (`InvalidTag`), och hela autentiseringsmatrisen **AUTH-01 till AUTH-09**.
* **Fas 3 (DAST & Kritiska sårbarheter):** SSRF-skydd (blockerar loopback, RFC 1918 och molnmetadata `169.254.169.254`), IDOR-isolering och valvsekretess.
* **Fas 4 (E2E Integration):** Komplett arbetsflöde från ärende och persona till 2FA, valv, grafanalys, GEXF-export och revisionsrapport.
* **Fas 5 (v3 Plugins, FinOps & OpSec):** Standardiserat Plugin-SDK, Redis Token Bucket rate limiting, responscache, dry-run estimering, Tor egress, PII-sanitisering, flerspråksstöd och NATO Admiralty A1–F6.

Kör hela verifieringssviten och generera `audit_results.json`:

```powershell
# Windows PowerShell
.\verify_all.ps1

# Linux / macOS / CI
./verify_all.sh
```

---

## ⚖️ Juridiska Skyddsräcken & Licens (Ethics by Design)

* **Licensiering:** IntelNexus Platform distribueras under [Apache License 2.0](LICENSE). Copyright &copy; 2026 Fagerhierta Consulting AB.
* **Juridisk Friskrivning:** Läs [DISCLAIMER.md](DISCLAIMER.md) för fullständiga friskrivningsklausuler.
* **GDPR & Local-First:** All utredningsdata stannar lokalt hos användaren utan telemetrispårning.
* **Anti-Stalking:** Systemet tillhandahåller inga verktyg för realtidsövervakning eller intrång mot privatpersoner.
