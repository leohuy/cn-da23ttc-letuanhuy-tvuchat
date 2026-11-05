import os
import shutil
import json
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db import models
from app.services.pdf_parser import extract_and_chunk_pdf
from app.services.vector_store import vector_service

router = APIRouter()

@router.post("/upload-document")
async def upload_document(
    code: str = Form(...),
    title: str = Form(...),
    category: str = Form(...),
    decision_number: str = Form(...),
    effective_date: str = Form(...),
    applies_to_khoa: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # 1. Lưu file PDF
        os.makedirs("data/pdfs", exist_ok=True)
        file_path = f"data/pdfs/{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Ep kiểu Ngày tháng & Khoa áp dụng
        try:
            date_obj = datetime.strptime(effective_date, "%Y-%m-%d").date()
        except Exception:
            date_obj = datetime.now().date()

        try:
            khoa_list = json.loads(applies_to_khoa)
        except Exception:
            khoa_list = ["ALL"]

        # 3. Tạo hoặc lấy Document
        doc = db.query(models.Document).filter(models.Document.code == code).first()
        if not doc:
            doc = models.Document(code=code, title=title, category=category)
            db.add(doc)
            db.commit()
            db.refresh(doc)

        # 4. Tạo DocumentVersion
        doc_version = models.DocumentVersion(
            document_id=doc.id,
            decision_number=decision_number,
            effective_date=date_obj,
            status="PUBLISHED",
            applies_to_khoa=khoa_list,
            file_path=file_path
        )
        db.add(doc_version)
        db.commit()
        db.refresh(doc_version)

        # 5. Extract PDF và Chunking
        raw_chunks = extract_and_chunk_pdf(file_path)
        if not raw_chunks:
            raise HTTPException(status_code=400, detail="Không thể trích xuất nội dung từ file PDF này.")

        # 6. Chuẩn bị nạp Vector
        chunks_for_vector = []
        for chunk in raw_chunks:
            chunks_for_vector.append({
                "content": chunk["content"],
                "page_number": chunk["page_number"],
                "version_id": doc_version.id,
                "applies_to_khoa": khoa_list,
                "status": "PUBLISHED"
            })

        # 7. Add Embeddings vào FAISS
        faiss_ids = vector_service.add_chunks(chunks_for_vector)

        # 8. Lưu Chunks vào Supabase
        db_chunks = []
        for idx, chunk in enumerate(raw_chunks):
            db_chunks.append(models.DocumentChunk(
                version_id=doc_version.id,
                chunk_index=idx,
                content=chunk["content"],
                page_number=chunk["page_number"],
                faiss_id=faiss_ids[idx]
            ))
        db.add_all(db_chunks)
        db.commit()

        return {
            "status": "success",
            "message": "Upload và nạp dữ liệu tri thức thành công!",
            "version_id": doc_version.id,
            "total_chunks": len(db_chunks)
        }

    except Exception as e:
        db.rollback()
        print(f"[ERROR] IN UPLOAD: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi xử lý hệ thống: {str(e)}"
        )
