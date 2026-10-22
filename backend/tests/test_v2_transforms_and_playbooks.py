import pytest
from app.core.roles import role_manager
from app.core.playbooks import playbook_orchestrator
from app.core.metadata_stripper import metadata_stripper
from app.models.case import CaseCreateRequest
from app.models.entity import Entity, EntityType
from app.transforms.catfish_transform import CatfishReverseImageTransform
from app.transforms.ubo_transform import UboUnwrapperTransform
from app.transforms.geoint_crisis_transform import GeointCrisisTransform
from app.db.database import db
from PIL import Image
import io


def test_roles_configuration():
    roles = role_manager.list_roles()
    assert len(roles) >= 7
    role_ids = [r.role_id for r in roles]
    assert "dating_safety" in role_ids
    assert "law_enforcement" in role_ids
    assert "journalism" in role_ids
    assert "private_investigator" in role_ids
    assert "finance_aml" in role_ids
    assert "geopolitical" in role_ids
    assert "embassy" in role_ids
    assert "cyber_threat_intelligence" in role_ids
    assert "fact_checking_human_rights" in role_ids


@pytest.mark.asyncio
async def test_catfish_transform():
    t = CatfishReverseImageTransform()
    seed = Entity(
        type=EntityType.PERSON,
        name="Elena Heart",
        attributes={"image_url": "https://example.com/model.jpg"},
        case_id="catfish_test",
    )
    res = await t.execute(seed)
    assert res.success is True
    assert seed.attributes.get("catfish_risk") in ["HÖG", "KRITISK"]
    assert len(res.entities) > 0  # Varningsincident skapad


@pytest.mark.asyncio
async def test_ubo_unwrapper_transform():
    t = UboUnwrapperTransform()
    seed = Entity(type=EntityType.ORGANIZATION, name="Nordic Tech AB", case_id="ubo_test")
    res = await t.execute(seed)
    assert res.success is True
    assert len(res.entities) >= 3
    # Kontrollera att verklig huvudman (UBO) eller offshore-enheter hittades
    assert any(e.attributes.get("is_offshore") is True for e in res.entities)
    assert any(e.attributes.get("is_ubo") is True for e in res.entities)


@pytest.mark.asyncio
async def test_geoint_crisis_transform():
    t = GeointCrisisTransform()
    seed = Entity(
        type=EntityType.LOCATION,
        name="Kyiv Kriszon",
        attributes={"latitude": 50.4501, "longitude": 30.5234},
        case_id="geo_test",
    )
    res = await t.execute(seed)
    assert res.success is True
    assert len(res.entities) >= 2


def test_metadata_stripper():
    # Skapa en testbild i minnet
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    raw_bytes = buf.getvalue()

    clean_bytes, hashes = metadata_stripper.strip_image_metadata(raw_bytes)
    assert hashes["status"] == "METADATA_STRIPPED"
    assert len(clean_bytes) > 0


@pytest.mark.asyncio
async def test_dating_verification_playbook():
    case = db.create_case(CaseCreateRequest(title="Dating Case"))
    result = await playbook_orchestrator.run_dating_verification(
        case_id=case.id,
        name="Sophia Miller",
        phone="+12025550199",
        image_url="https://stockphoto.example/model1.jpg",
        story="Påstådd militärläkare i Syrien",
    )
    assert result["risk_level"] in ["WARNING", "CRITICAL"]
    assert len(result["risk_factors"]) > 0
    assert result["catfish_check"]["detected"] is True
