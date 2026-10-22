import pytest
from app.db.database import db
from app.db.graph_store import graph_store
from app.models.case import CaseCreateRequest
from app.models.entity import Entity, EntityType
from app.models.relationship import Relationship, RelationshipType
from app.resolution.entity_resolver import entity_resolver, jaro_winkler_distance


def test_jaro_winkler():
    assert jaro_winkler_distance("Anders Lindqvist", "Anders Lindqvist") == 1.0
    sim = jaro_winkler_distance("Anders Lindqvist", "Anders Lindkvist")
    assert sim > 0.90
    assert jaro_winkler_distance("Anders", "Zebulon") < 0.5


def test_graph_and_metrics():
    case = db.create_case(CaseCreateRequest(title="Graph Test Case"))
    cid = case.id

    e1 = db.save_entity(Entity(case_id=cid, type=EntityType.PERSON, name="Alice"))
    e2 = db.save_entity(Entity(case_id=cid, type=EntityType.ORGANIZATION, name="Corp A"))
    e3 = db.save_entity(Entity(case_id=cid, type=EntityType.DOMAIN, name="corp-a.com"))

    db.save_relationship(Relationship(case_id=cid, source_id=e1.id, target_id=e2.id, relation_type=RelationshipType.DIRECTOR_OF))
    db.save_relationship(Relationship(case_id=cid, source_id=e2.id, target_id=e3.id, relation_type=RelationshipType.OWNS))

    graph_store.reload_case_graph(cid)
    gdata = graph_store.get_graph_data(cid)
    assert gdata["node_count"] == 3
    assert gdata["edge_count"] == 2

    # Metrics
    metrics = graph_store.compute_metrics(cid)
    assert "degree" in metrics
    assert "pagerank" in metrics
    assert len(metrics["top_influencers"]) > 0

    # Shortest path
    path = graph_store.find_shortest_path(cid, e1.id, e3.id)
    assert path == [e1.id, e2.id, e3.id]


def test_entity_resolution_and_merge():
    case = db.create_case(CaseCreateRequest(title="Resolution Case"))
    cid = case.id

    e1 = db.save_entity(Entity(
        case_id=cid,
        type=EntityType.PERSON,
        name="Carl Gustafsson",
        attributes={"national_id": "19800101-1234", "city": "Stockholm"}
    ))

    e2 = db.save_entity(Entity(
        case_id=cid,
        type=EntityType.PERSON,
        name="Karl Gustafsson",
        attributes={"national_id": "19800101-1234", "phone": "+4670112233"}
    ))

    # Hitta deterministisk matchning
    matches = entity_resolver.find_matches(cid)
    assert len(matches) > 0
    assert matches[0].match_type == "deterministic"

    # Merge
    merged = entity_resolver.merge_entities(e1.id, e2.id, cid)
    assert merged.id == e1.id
    assert "Karl Gustafsson" in merged.aliases
    assert merged.attributes.get("phone") == "+4670112233"
    assert db.get_entity(e2.id) is None
