from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Response
from app.db.graph_store import graph_store

router = APIRouter(prefix="/graph", tags=["Graph & Link Analysis"])


@router.get("/{case_id}")
def get_graph(case_id: str):
    """Hämtar noder och relationer för ett ärende, formaterat för Cytoscape/React Flow."""
    return graph_store.get_graph_data(case_id)


@router.get("/{case_id}/metrics")
def get_graph_metrics(case_id: str):
    """Beräknar grafmått: PageRank, Betweenness centrality, Degree centrality och toppaktörer."""
    return graph_store.compute_metrics(case_id)


@router.get("/{case_id}/ego/{node_id}")
def get_ego_graph(case_id: str, node_id: str, radius: int = Query(1, ge=1, le=5)):
    """Hämtar delgraf centrerad runt en vald nod inom N hopp."""
    return graph_store.get_ego_graph(case_id, node_id, radius=radius)


@router.get("/{case_id}/shortest-path")
def get_shortest_path(case_id: str, source_id: str = Query(...), target_id: str = Query(...)):
    """Hittar kortaste vägen i nätverket mellan två valda entiteter."""
    path = graph_store.find_shortest_path(case_id, source_id, target_id)
    if path is None:
        return {"found": False, "path": [], "message": "Ingen väg finns mellan de två noderna."}
    return {"found": True, "path": path, "hop_count": len(path) - 1}


@router.get("/{case_id}/export/gexf")
def export_gexf(case_id: str):
    """Exporterar grafen till GEXF-format för Gephi."""
    gexf_content = graph_store.export_gexf(case_id)
    return Response(
        content=gexf_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="case_{case_id}.gexf"'}
    )


@router.get("/{case_id}/export/graphml")
def export_graphml(case_id: str):
    """Exporterar grafen till GraphML-format."""
    graphml_content = graph_store.export_graphml(case_id)
    return Response(
        content=graphml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="case_{case_id}.graphml"'}
    )


@router.get("/{case_id}/export/csv")
def export_csv(case_id: str):
    """Exporterar noder och kanter som CSV."""
    return graph_store.export_csv(case_id)
