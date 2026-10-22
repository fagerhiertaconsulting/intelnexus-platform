from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from app.analysis.ner_extractor import ner_extractor
from app.analysis.report_generator import report_generator
from app.db.database import db
from app.db.graph_store import graph_store
from app.models.entity import Entity

router = APIRouter(prefix="/analysis", tags=["AI & NLP Analysis"])


class ExtractTextRequest(BaseModel):
    text: str
    case_id: str
    source_url: Optional[str] = "text://manual_analysis"
    auto_commit_to_case: bool = False


@router.post("/ner")
def extract_entities_from_text(req: ExtractTextRequest):
    """
    Kör Named Entity Recognition (NER) på ostrukturerad text och extraherar personer,
    organisationer, e-post, IP, domäner, kryptoplånböcker och telefonnummer.
    """
    discovered = ner_extractor.extract_entities_from_text(
        text=req.text,
        case_id=req.case_id,
        source_url=req.source_url or "text://manual_analysis",
    )

    if req.auto_commit_to_case:
        for ent in discovered:
            db.save_entity(ent)
            graph_store.add_entity_to_graph(req.case_id, ent)

    return {
        "case_id": req.case_id,
        "extracted_count": len(discovered),
        "entities": discovered,
        "auto_committed": req.auto_commit_to_case,
    }


@router.get("/report/{case_id}/markdown")
def get_markdown_report(case_id: str):
    """Genererar en fullständig utredningsrapport i Markdown-format."""
    try:
        content = report_generator.generate_markdown_report(case_id)
        return Response(content=content, media_type="text/markdown; charset=utf-8")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/report/{case_id}/html")
def get_html_report(case_id: str):
    """Genererar en snyggt stylad, utskriftsklar HTML-rapport för ärendet."""
    try:
        md_content = report_generator.generate_markdown_report(case_id)
        # Enkel ren HTML-konvertering för utskrift
        html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <title>Utredningsrapport - {case_id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1f2937; max-width: 900px; margin: 40px auto; padding: 0 20px; }}
        h1 {{ color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 12px; }}
        h2 {{ color: #1f2937; margin-top: 32px; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; font-size: 14px; }}
        th, td {{ border: 1px solid #d1d5db; padding: 8px 12px; text-align: left; }}
        th {{ background-color: #f3f4f6; }}
        code {{ background-color: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 13px; }}
        blockquote {{ border-left: 4px solid #ef4444; background: #fef2f2; padding: 12px 16px; margin: 16px 0; color: #991b1b; }}
        .header {{ margin-bottom: 30px; }}
        @media print {{ body {{ margin: 20mm; }} }}
    </style>
</head>
<body>
    <pre style="white-space: pre-wrap; font-family: inherit;">{md_content}</pre>
</body>
</html>"""
        return Response(content=html, media_type="text/html; charset=utf-8")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
