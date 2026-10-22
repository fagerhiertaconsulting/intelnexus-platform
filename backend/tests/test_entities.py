from app.models.entity import Entity, EntityType
from app.models.relationship import Relationship, RelationshipType
from app.models.case import Case
from app.db.database import DatabaseManager


def test_entity_creation():
    ent = Entity(
        type=EntityType.PERSON,
        name="Test Person",
        aliases=["tp123"],
        attributes={"country": "SE"},
        confidence_score=0.95,
    )
    assert ent.id.startswith("entity--")
    assert ent.name == "Test Person"
    assert ent.type == EntityType.PERSON
    assert ent.confidence_score == 0.95


def test_relationship_creation():
    rel = Relationship(
        source_id="entity--123",
        target_id="entity--456",
        relation_type=RelationshipType.OWNS,
    )
    assert rel.id.startswith("relationship--")
    assert rel.relation_type == RelationshipType.OWNS


def test_database_crud(tmp_path):
    test_db = DatabaseManager(db_path=tmp_path / "test.db")

    # Create Case
    case = test_db.create_case(Case(title="Test Case", description="Description"))
    assert case.id.startswith("case--")

    # Save Entity
    ent = Entity(case_id=case.id, type=EntityType.DOMAIN, name="example.com")
    saved_ent = test_db.save_entity(ent)
    assert saved_ent.name == "example.com"

    # List Entities
    ents = test_db.list_entities(case_id=case.id)
    assert len(ents) == 1
    assert ents[0].name == "example.com"

    # Save Relationship
    ent2 = test_db.save_entity(Entity(case_id=case.id, type=EntityType.IP, name="93.184.216.34"))
    rel = Relationship(
        case_id=case.id,
        source_id=saved_ent.id,
        target_id=ent2.id,
        relation_type=RelationshipType.RESOLVES_TO,
    )
    test_db.save_relationship(rel)

    rels = test_db.list_relationships(case_id=case.id)
    assert len(rels) == 1
    assert rels[0].relation_type == RelationshipType.RESOLVES_TO
