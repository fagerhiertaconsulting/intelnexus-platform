import pytest
from app.models.entity import Entity, EntityType
from app.transforms.registry import registry
from app.transforms.dns_transform import DnsWhoisTransform
from app.transforms.company_registry_transform import CompanyRegistryTransform
from app.transforms.social_footprint_transform import SocialFootprintTransform
from app.transforms.ip_geo_transform import IpGeoTransform
from app.transforms.crtsh_subdomain_transform import CrtshSubdomainTransform
from app.transforms.sanctions_transform import SanctionsTransform
from app.transforms.exif_metadata_transform import ExifMetadataTransform


def test_registry_registration():
    t_list = registry.list_transforms()
    names = [t["name"] for t in t_list]
    assert "dns_whois_transform" in names
    assert "company_registry_transform" in names
    assert "social_footprint_transform" in names
    assert "ip_geo_transform" in names
    assert "crtsh_subdomain_transform" in names
    assert "sanctions_transform" in names
    assert "exif_metadata_transform" in names


@pytest.mark.asyncio
async def test_company_registry_transform():
    t = CompanyRegistryTransform()
    seed = Entity(type=EntityType.ORGANIZATION, name="Nordic Tech AB", case_id="test_case")
    res = await t.execute(seed)
    assert res.success is True
    assert len(res.entities) > 0
    assert len(res.relationships) > 0
    assert len(res.evidence_items) > 0
    # Validera att VD och ägare genererades
    names = [e.name for e in res.entities]
    assert any("Anders Lindqvist" in n for n in names)


@pytest.mark.asyncio
async def test_ip_geo_transform():
    t = IpGeoTransform()
    seed = Entity(type=EntityType.IP, name="8.8.8.8", case_id="test_case")
    res = await t.execute(seed)
    assert res.success is True
    assert len(res.entities) > 0
    # Kontrollera att plats och koordinater fanns med
    loc_nodes = [e for e in res.entities if e.type == EntityType.LOCATION]
    assert len(loc_nodes) > 0


@pytest.mark.asyncio
async def test_sanctions_transform():
    t = SanctionsTransform()
    # Test med känd sanktionerad entitet
    seed = Entity(type=EntityType.ORGANIZATION, name="Wagner Group", case_id="test_case")
    res = await t.execute(seed)
    assert res.success is True
    assert seed.attributes.get("sanctioned") is True
    assert len(res.entities) > 0  # Incident-nod genererades

    # Test med icke-sanktionerad entitet
    clean_seed = Entity(type=EntityType.ORGANIZATION, name="Oskyldigt Lokalt Bageri AB", case_id="test_case")
    clean_res = await t.execute(clean_seed)
    assert clean_res.success is True
    assert clean_seed.attributes.get("sanctioned") is False


@pytest.mark.asyncio
async def test_exif_metadata_transform():
    t = ExifMetadataTransform()
    seed = Entity(
        type=EntityType.DOCUMENT,
        name="suspect_photo.jpg",
        attributes={"latitude": 59.3293, "longitude": 18.0686, "camera_make": "Apple", "camera_model": "iPhone 15"},
        case_id="test_case"
    )
    res = await t.execute(seed)
    assert res.success is True
    loc_nodes = [e for e in res.entities if e.type == EntityType.LOCATION]
    assert len(loc_nodes) == 1
    assert loc_nodes[0].attributes["latitude"] == 59.3293
