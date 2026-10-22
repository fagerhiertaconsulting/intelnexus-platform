# Bidrags- och Utvecklarguide: OpenIntel-OSINT

Tack för att du vill bidra till OpenIntel-OSINT! Denna guide förklarar hur plattformen är uppbyggd och hur du bygger och registrerar nya datainsamlingstransforms.

---

## 🧩 Så bygger du en ny OSINT-Transform

Alla insamlingsmoduler ärver från `BaseTransform` i `backend/app/transforms/base.py`.

### 1. Skapa en ny fil
Skapa `backend/app/transforms/my_custom_transform.py`:

```python
import time
from typing import Any, Dict, Optional, Set
from app.models.entity import Entity, EntityType
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import EvidenceItem
from app.db.object_store import object_store
from .base import BaseTransform, TransformResult


class MyCustomTransform(BaseTransform):
    name = "my_custom_transform"
    display_name = "My Custom OSINT Transform"
    description = "Hämtar information från en extern öppen källa."
    category = "network" # 'network', 'corporate', 'social', 'compliance', etc.
    supported_types: Set[EntityType] = {EntityType.DOMAIN}

    async def execute(self, seed: Entity, options: Optional[Dict[str, Any]] = None) -> TransformResult:
        start_time = time.time()
        logs = [f"Startar {self.display_name} för {seed.name}"]

        new_entities = []
        new_relationships = []
        evidence_items = []

        # 1. Hämta data från öppen källa (API, DNS, etc.)
        external_data = {"target": seed.name, "example_result": "active"}

        # 2. Spara rådata i beviskedjan med SHA-256
        case_id = seed.case_id or "default_case"
        rel_path, sha256_hash, size = object_store.store_json(
            case_id=case_id,
            filename=f"my_transform_{int(time.time())}.json",
            data_dict=external_data,
            subfolder="custom",
        )
        evidence = EvidenceItem(
            case_id=case_id,
            title=f"Rådata för {seed.name}",
            file_path=rel_path,
            file_size_bytes=size,
            sha256=sha256_hash,
            collector_plugin=self.name,
        )
        evidence_items.append(evidence)

        # 3. Skapa proveniens
        prov = self.create_provenance(
            source_url="https://api.example.com",
            sha256=sha256_hash,
            note="Hämtat via MyCustomTransform",
        )

        # 4. Skapa nya entiteter och relationer
        new_node = Entity(
            type=EntityType.IP,
            name="1.2.3.4",
            provenance=[prov],
            case_id=seed.case_id,
        )
        new_entities.append(new_node)

        new_relationships.append(Relationship(
            source_id=seed.id,
            target_id=new_node.id,
            relation_type=RelationshipType.RESOLVES_TO,
            provenance=[prov],
            case_id=seed.case_id,
        ))

        exec_time = time.time() - start_time
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
```

### 2. Registrera transformen
Lägg till klassen i `backend/app/transforms/registry.py`:

```python
from .my_custom_transform import MyCustomTransform

# Lägg till i _register_default_transforms()
default_classes = [
    # ...
    MyCustomTransform,
]
```

### 3. Skriv ett test
Skapa ett testfall i `backend/tests/test_transforms.py` och verifiera med:
```bash
pytest backend/tests/test_transforms.py -v
```

---

## 🛠️ Kodstandarder
* Använd Pydantic v2 för alla datamodeller.
* Alla nätverksanrop ska vara asynkrona (`httpx.AsyncClient` eller `asyncio.to_thread`).
* Respektera rate-limits och använd rimliga timeouts ($3-8$ sekunder).
* Alla hämtade råsvar ska arkiveras som bevis (`object_store`) med automatisk SHA-256 hash.
