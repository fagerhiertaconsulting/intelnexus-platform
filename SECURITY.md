# Säkerhetspolicy och Etiska Riktlinjer (Security & Ethics)

## 🛡️ Säkerhetspolicy
OpenIntel-OSINT är utformad för defensiv säkerhetsanalys, brottsbekämpning och transparent granskning.

Om du upptäcker en säkerhetssårbarhet i plattformen, vänligen rapportera den ansvarsfullt till projektets underhållare via GitHub Security Advisories.

---

## ⚖️ Juridisk och Etisk Ram (Ethics by Design)

För att plattformen ska kunna användas och publiceras lagligt och etiskt gäller följande principer:

### 1. GDPR och Personuppgiftslagstiftning
* **Lokal kontroll (Local-First):** Systemet skickar ingen utredningsdata till externa molntjänster utan utredarens aktiva godkännande.
* **Dataminimering:** Endast data som är nödvändig för den specifika utredningen ska inhämtas.
* **Kryptering i vila:** Känsliga fallfiler och bevisdatabaser lagras lokalt med strikta åtkomstbegränsningar.

### 2. Anti-Stalking och Säkerhetsspärrar
* **Ingen realtidsspårning av privatpersoners mobila enheter:** Systemet tillhandahåller inte verktyg för spårning av enskilda privatpersoners fysiska positioner.
* **Ingen exploatering av dataläckor:** Plattformen samlar uteslutande in data från öppna, tillåtna och officiella källor (DNS, WHOIS, publika certifikat, öppna bolagsregister, sanktionslistor).
* **Ingen obehörig geolokalisering:** Geolokalisering sker endast på IP-infrastruktur och offentligt registrerade adresser eller fotometadata där tillstånd föreligger.

### 3. API ToS och Rate Limits
* Förfrågningar mot externa API:er respekterar `robots.txt`, plattformsspecifika användarvillkor och implementerar fördröjningar och concurrency limits för att undvika överbelastning.

---

## 🔒 Kryptografisk beviskedja
Alla inhämtade data hashas omedelbart vid ankomst med SHA-256. Genom `api.auditCustody()` kan utredaren när som helst verifiera att inga bevisfiler på lagringsmediet har modifierats, raderats eller utsatts för manipulering.
