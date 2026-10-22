# Säkerhetspolicy och Etiska Riktlinjer (IntelNexus Platform)

## 🛡️ Säkerhetspolicy
IntelNexus Platform är utformad som en neutral integrations- och fusionshubb för defensiv säkerhetsanalys, brottsbekämpning, granskande journalistik och transparent verifiering mot externa API-leverantörer.

Om du upptäcker en säkerhetssårbarhet i plattformen, vänligen rapportera den ansvarsfullt till projektets underhållare via GitHub Security Advisories.

---

## 🔐 Kredentialvalv & Källsäkerhet (BYOAK Architecture)

1. **Lokal Kryptering i Vila (AES-256-GCM):**
   * Alla API-nycklar (t.ex. Shodan, Bolagsverket, Roaring, Etherscan) krypteras lokalt på användarens maskin med AES-256-GCM via PBKDF2/Argon2.
   * Plattformen implementerar strikt *Zero-Knowledge* – inga nycklar eller utredningsdata sänds till centrala servrar utöver den avsedda externa API-tjänsten.
2. **Källskydd för Whistleblowers:**
   * Inbyggt verktyg för metadatarensning (`MetadataStripper`) som raderar EXIF, GPS-koordinater, serienummer och kameraavtryck ur källfiler innan de delas eller publiceras.
3. **Kryptografisk Beviskedja (Chain of Custody):**
   * Alla inhämtade sidor och svar hashas omedelbart vid ankomst med SHA-256 och lagras i oföränderlig lagring.

---

## ⚖️ Juridiska och Etiska Skyddsräcken (Ethics by Design)

* **GDPR och Lokal Kontroll:** All utredningsdata sparas uteslutande hos användaren (`local-first`).
* **Anti-Stalking & Skydd mot trakasserier:**
  * För privatpersonsläget (t.ex. kontroll av dejt/kontakt) exponeras endast funktioner för *defensiv verifiering* (t.ex. bildgoogling mot catfish-databaser, telefonnummerverifiering, sökning i publika varningslistor för romansbedrägerier).
  * Systemet tillhandahåller inga verktyg för kontinuerlig realtidsövervakning av enskilda privatpersoners positioner eller obehörig intrångsdata.
* **Behörighetsstyrd API-tillgång (BYOAK):** Plattformen kringgår inga betalväggar eller autentiseringsspärrar. Tillgång till skyddade eller kommersiella register sker uteslutande via användarens egna, lagligt införskaffade API-nycklar.
