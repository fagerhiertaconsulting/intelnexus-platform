## Description of Changes
<!-- Provide a concise summary of the changes introduced by this pull request. -->

### Related Issue(s) / Context
<!-- Link relevant issue(s) or provide context (e.g. fixes #123) -->

---

## Contributor License Agreement & Governance (CLA)
All contributions to **OpenIntel-OSINT Platform** are subject to the project's governance and licensing policy.

Please review and confirm the following statements before submitting your pull request:

- [ ] **Licensing & Rights Assignment:** I hereby certify that the code and documentation submitted in this pull request is my original work (or I have full authorization from the copyright holder to submit it). I agree that my contributions are licensed under the **Apache License 2.0** as set forth in the project root [`LICENSE`](../LICENSE).
- [ ] **Dual-Licensing & Re-licensing Authority:** I acknowledge and agree that the project owner, **Fagerhierta Consulting AB**, retains the full, irrevocable, and exclusive right to re-license, dual-license, or sublicense future releases and derivative versions of this project (including proprietary or enterprise commercial editions) without requiring separate consent from contributors.
- [ ] **Defensive & Ethical Intent:** I confirm that these changes adhere to the defensive, ethical, and lawful investigation guidelines outlined in [`DISCLAIMER.md`](../DISCLAIMER.md).

---

## Verification & Quality Assurance Checklist
- [ ] Formatted with **Ruff format** and passed **Ruff check** (0 lint errors).
- [ ] Static type validation passed via **Mypy** (0 type errors).
- [ ] Security audit passed with **Bandit** and **pip-audit**.
- [ ] Frontend checks passed (**ESLint** and `tsc --noEmit`).
- [ ] Pytest test suite executed and passed with minimum **85% test coverage** retained.
- [ ] Existing functionality (including voluntary 2FA and NATO Admiralty rating) remains unbroken.
