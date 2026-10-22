import io
from typing import Any, Dict, List, Optional
import networkx as nx
from app.db.database import db
from app.models.entity import Entity
from app.models.relationship import Relationship


class GraphStore:
    """
    Rik grafmotor som kombinerar NetworkX för in-memory och avancerade grafalgoritmer
    (PageRank, Betweenness centrality, Shortest Path) med automatisk synkronisering
    mot databasen och exportmöjligheter (GEXF, GraphML, JSON, CSV).
    """

    def __init__(self):
        self._graphs: Dict[str, nx.MultiDiGraph] = {}

    def get_graph(self, case_id: str) -> nx.MultiDiGraph:
        """Hämtar eller bygger upp grafen för ett specifikt ärende."""
        if case_id not in self._graphs:
            self.reload_case_graph(case_id)
        return self._graphs[case_id]

    def reload_case_graph(self, case_id: str) -> nx.MultiDiGraph:
        """Läser in alla entiteter och relationer för ett ärende från databasen till grafminnet."""
        G = nx.MultiDiGraph()
        entities = db.list_entities(case_id=case_id)
        for e in entities:
            G.add_node(
                e.id,
                name=e.name,
                type=e.type.value if hasattr(e.type, "value") else str(e.type),
                aliases=e.aliases,
                confidence_score=e.confidence_score,
                attributes=e.attributes,
                created_at=e.created_at.isoformat(),
            )

        relationships = db.list_relationships(case_id=case_id)
        for r in relationships:
            if G.has_node(r.source_id) and G.has_node(r.target_id):
                G.add_edge(
                    r.source_id,
                    r.target_id,
                    key=r.id,
                    id=r.id,
                    relation_type=r.relation_type.value if hasattr(r.relation_type, "value") else str(r.relation_type),
                    confidence_score=r.confidence_score,
                    attributes=r.attributes,
                    created_at=r.created_at.isoformat(),
                )

        self._graphs[case_id] = G
        return G

    def add_entity_to_graph(self, case_id: str, entity: Entity):
        G = self.get_graph(case_id)
        G.add_node(
            entity.id,
            name=entity.name,
            type=entity.type.value if hasattr(entity.type, "value") else str(entity.type),
            aliases=entity.aliases,
            confidence_score=entity.confidence_score,
            attributes=entity.attributes,
            created_at=entity.created_at.isoformat(),
        )

    def add_relationship_to_graph(self, case_id: str, rel: Relationship):
        G = self.get_graph(case_id)
        if not G.has_node(rel.source_id) or not G.has_node(rel.target_id):
            # Ladda om ifall nod nyligen lades till
            self.reload_case_graph(case_id)
            G = self.get_graph(case_id)

        if G.has_node(rel.source_id) and G.has_node(rel.target_id):
            G.add_edge(
                rel.source_id,
                rel.target_id,
                key=rel.id,
                id=rel.id,
                relation_type=rel.relation_type.value
                if hasattr(rel.relation_type, "value")
                else str(rel.relation_type),
                confidence_score=rel.confidence_score,
                attributes=rel.attributes,
                created_at=rel.created_at.isoformat(),
            )

    def get_graph_data(self, case_id: str) -> Dict[str, Any]:
        """
        Returnerar noder och kanter formaterade för frontend
        (kompatibelt med Cytoscape.js och React Flow).
        """
        G = self.get_graph(case_id)
        nodes = []
        for node_id, data in G.nodes(data=True):
            nodes.append(
                {
                    "id": node_id,
                    "data": {
                        "id": node_id,
                        "label": data.get("name", node_id),
                        "type": data.get("type", "unknown"),
                        "aliases": data.get("aliases", []),
                        "confidence_score": data.get("confidence_score", 1.0),
                        "attributes": data.get("attributes", {}),
                        "created_at": data.get("created_at"),
                    },
                }
            )

        edges = []
        for u, v, k, data in G.edges(keys=True, data=True):
            edges.append(
                {
                    "id": k,
                    "source": u,
                    "target": v,
                    "data": {
                        "id": k,
                        "source": u,
                        "target": v,
                        "label": data.get("relation_type", "RELATED_TO"),
                        "relation_type": data.get("relation_type", "RELATED_TO"),
                        "confidence_score": data.get("confidence_score", 1.0),
                        "attributes": data.get("attributes", {}),
                    },
                }
            )

        return {
            "case_id": case_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

    def compute_metrics(self, case_id: str) -> Dict[str, Any]:
        """
        Beräknar grafalgoritmer och centralitetsmått för att hitta nyckelnoder i nätverket:
        PageRank, Betweenness Centrality, Degree Centrality och In/Out-degree.
        """
        G = self.get_graph(case_id)
        if len(G.nodes) == 0:
            return {"degree": {}, "betweenness": {}, "pagerank": {}, "top_influencers": []}

        # Konvertera till enkel DiGraph för algoritmer som kräver det
        simple_digraph = nx.DiGraph(G)
        undirected = simple_digraph.to_undirected()

        degree_cent = nx.degree_centrality(G)
        in_degree_cent = nx.in_degree_centrality(G)
        out_degree_cent = nx.out_degree_centrality(G)

        try:
            betweenness = nx.betweenness_centrality(undirected)
        except Exception:
            betweenness = {n: 0.0 for n in G.nodes}

        try:
            pagerank = nx.pagerank(simple_digraph, max_iter=200)
        except Exception:
            pagerank = {n: 0.0 for n in G.nodes}

        # Samla top influencers
        rankings = []
        for node_id in G.nodes:
            node_name = G.nodes[node_id].get("name", node_id)
            node_type = G.nodes[node_id].get("type", "unknown")
            composite_score = (
                (pagerank.get(node_id, 0.0) * 0.4)
                + (betweenness.get(node_id, 0.0) * 0.4)
                + (degree_cent.get(node_id, 0.0) * 0.2)
            )
            rankings.append(
                {
                    "id": node_id,
                    "name": node_name,
                    "type": node_type,
                    "score": round(composite_score, 4),
                    "pagerank": round(pagerank.get(node_id, 0.0), 4),
                    "betweenness": round(betweenness.get(node_id, 0.0), 4),
                    "degree": round(degree_cent.get(node_id, 0.0), 4),
                }
            )

        rankings.sort(key=lambda x: x["score"], reverse=True)

        return {
            "degree": {k: round(v, 4) for k, v in degree_cent.items()},
            "in_degree": {k: round(v, 4) for k, v in in_degree_cent.items()},
            "out_degree": {k: round(v, 4) for k, v in out_degree_cent.items()},
            "betweenness": {k: round(v, 4) for k, v in betweenness.items()},
            "pagerank": {k: round(v, 4) for k, v in pagerank.items()},
            "top_influencers": rankings[:10],
        }

    def find_shortest_path(self, case_id: str, source_id: str, target_id: str) -> Optional[List[str]]:
        """Hittar kortaste vägen mellan två entiteter i grafen."""
        G = self.get_graph(case_id)
        undirected = G.to_undirected()
        if not undirected.has_node(source_id) or not undirected.has_node(target_id):
            return None
        try:
            return nx.shortest_path(undirected, source=source_id, target=target_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_ego_graph(self, case_id: str, node_id: str, radius: int = 1) -> Dict[str, Any]:
        """Hämtar delgraf centrerad runt en vald nod inom N hopp."""
        G = self.get_graph(case_id)
        if not G.has_node(node_id):
            return {"nodes": [], "edges": []}

        undirected = G.to_undirected()
        sub_nodes = nx.ego_graph(undirected, node_id, radius=radius).nodes()
        subgraph = G.subgraph(sub_nodes)

        nodes = []
        for n, data in subgraph.nodes(data=True):
            nodes.append({"id": n, "data": {"id": n, **data}})

        edges = []
        for u, v, k, data in subgraph.edges(keys=True, data=True):
            edges.append({"id": k, "source": u, "target": v, "data": {"id": k, **data}})

        return {"nodes": nodes, "edges": edges}

    # --- EXPORTFUNKTIONER ---

    def export_gexf(self, case_id: str) -> str:
        """Exporterar grafen till GEXF-format för Gephi."""
        G = self.get_graph(case_id)
        # GEXF stödjer enkel DiGraph eller Graph
        simple_g = nx.DiGraph()
        for n, d in G.nodes(data=True):
            # Serialisera komplexa attribut till strängar för GEXF-kompatibilitet
            clean_attrs = {
                "name": str(d.get("name", "")),
                "type": str(d.get("type", "")),
                "confidence_score": float(d.get("confidence_score", 1.0)),
            }
            simple_g.add_node(n, **clean_attrs)
        for u, v, k, d in G.edges(keys=True, data=True):
            simple_g.add_edge(u, v, id=k, label=str(d.get("relation_type", "RELATED_TO")))

        buf = io.BytesIO()
        nx.write_gexf(simple_g, buf)
        return buf.getvalue().decode("utf-8")

    def export_graphml(self, case_id: str) -> str:
        """Exporterar grafen till GraphML."""
        G = self.get_graph(case_id)
        simple_g = nx.DiGraph()
        for n, d in G.nodes(data=True):
            simple_g.add_node(
                n,
                name=str(d.get("name", "")),
                type=str(d.get("type", "")),
                confidence_score=float(d.get("confidence_score", 1.0)),
            )
        for u, v, k, d in G.edges(keys=True, data=True):
            simple_g.add_edge(u, v, id=k, label=str(d.get("relation_type", "RELATED_TO")))

        buf = io.BytesIO()
        nx.write_graphml(simple_g, buf)
        return buf.getvalue().decode("utf-8")

    def export_csv(self, case_id: str) -> Dict[str, str]:
        """Exporterar noder och kanter till separata CSV-strängar."""
        G = self.get_graph(case_id)
        nodes_csv = "id,name,type,confidence_score,created_at\n"
        for n, d in G.nodes(data=True):
            name = d.get("name", "").replace('"', '""')
            nodes_csv += (
                f'"{n}","{name}","{d.get("type", "")}",{d.get("confidence_score", 1.0)},"{d.get("created_at", "")}"\n'
            )

        edges_csv = "id,source,target,relation_type,confidence_score\n"
        for u, v, k, d in G.edges(keys=True, data=True):
            rel_type = d.get("relation_type", "RELATED_TO")
            edges_csv += f'"{k}","{u}","{v}","{rel_type}",{d.get("confidence_score", 1.0)}\n'

        return {"nodes_csv": nodes_csv, "edges_csv": edges_csv}


graph_store = GraphStore()
