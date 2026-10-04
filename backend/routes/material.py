"""
Material routes – PDF upload and retrieval for learning materials.
"""

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, UploadFile, File

from database import materials_collection
from models.material import (
    LearningMaterialInDB,
    MaterialUploadResponse,
    MaterialDetailResponse,
)
from services.pdf_service import extract_text_from_pdf, PDFExtractionError
from services.material_service import analyze_material, MaterialAnalysisError

router = APIRouter(prefix="/api/material")


@router.post("/upload", response_model=MaterialUploadResponse)
def upload_material(file: UploadFile = File(...)):
    """
    Accept a PDF, extract text, analyse with Gemma, validate,
    store in MongoDB, and return structured topics + diagnostic questions.
    """
    # ── 1. Extract text from PDF ──────────────────────────────────────
    try:
        extraction = extract_text_from_pdf(
            file=file.file,
            filename=file.filename or "unknown.pdf",
        )
    except PDFExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # ── 2. Analyse with Gemma ─────────────────────────────────────────
    try:
        analysis = analyze_material(extraction.text)
    except MaterialAnalysisError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI analysis failed: {exc}",
        )

    # ── 3. Store in MongoDB ───────────────────────────────────────────
    material = LearningMaterialInDB(
        filename=file.filename or "unknown.pdf",
        page_count=extraction.page_count,
        extracted_text_preview=extraction.text[:2000],
        title=analysis.title,
        topics=analysis.topics,
        diagnostic_questions=analysis.diagnostic_questions,
    )

    try:
        result = materials_collection().insert_one(material.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    # ── 4. Return response ────────────────────────────────────────────
    return MaterialUploadResponse(
        success=True,
        material_id=str(result.inserted_id),
        title=analysis.title,
        topics=analysis.topics,
        diagnostic_questions=analysis.diagnostic_questions,
    )


@router.get("/{material_id}", response_model=MaterialDetailResponse)
def get_material(material_id: str):
    """Retrieve a stored learning material by its ID."""
    try:
        oid = ObjectId(material_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="Invalid material_id format.")

    doc = materials_collection().find_one({"_id": oid})
    if doc is None:
        raise HTTPException(status_code=404, detail="Material not found.")

    return MaterialDetailResponse(
        material_id=str(doc["_id"]),
        filename=doc["filename"],
        page_count=doc["page_count"],
        title=doc["title"],
        topics=doc["topics"],
        diagnostic_questions=doc["diagnostic_questions"],
        created_at=doc["created_at"],
    )
