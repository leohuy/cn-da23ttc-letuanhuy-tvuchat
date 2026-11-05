from typing import List, Dict, Any, Tuple
import numpy as np
import google.generativeai as genai
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.vector_store import vector_service
from app.db import models

genai.configure(api_key=settings.GEMINI_API_KEY)

# Sử dụng chung 1 model thế hệ mới hoạt động ổn định nhất
GEMINI_TEXT_MODEL = "gemini-3.5-flash-lite"

SYSTEM_PROMPT_TEMPLATE = """
Bạn là Trợ lý Học vụ AI thông minh của Trường Đại học Trà Vinh (TVU). 
Nhiệm vụ của bạn là giải đáp thắc mắc của sinh viên dựa TRỰC TIẾP trên các đoạn Văn bản Quy chế được cung cấp dưới đây.

DỮ LIỆU QUY CHẾ THAM KHẢO:
{context}

YÊU CẦU TRẢ LỜI:
1. Chỉ dựa vào dữ liệu quy chế trên để trả lời. Không tự suy đoán nếu quy chế không đề cập.
2. Trả lời rõ ràng, mạch lạc, đúng trọng tâm bằng tiếng Việt.
3. Nếu dữ liệu không đủ để trả lời, hãy lịch sự thông báo sinh viên liên hệ Phòng Đào tạo TVU để được hỗ trợ chính xác.
"""

def retrieve_context(query: str, khoa: str, db: Session, top_k: int = 4) -> Tuple[str, List[Dict[str, Any]]]:
    """Tìm kiếm vector gần nhất trong FAISS và lọc theo Khóa tuyển sinh."""
    query_vec = vector_service.get_embedding(query, task_type="retrieval_query")
    
    # Tìm kiếm k kết quả gần nhất trong FAISS
    distances, indices = vector_service.index.search(np.array([query_vec], dtype=np.float32), top_k * 3)
    
    retrieved_chunks = []
    citations = []
    
    for idx in indices[0]:
        if idx < 0 or idx >= len(vector_service.metadata_store):
            continue
            
        meta = vector_service.metadata_store[idx]
        applies_to = meta.get("applies_to_khoa", [])
        
        # Kiểm tra điều kiện Khóa tuyển sinh (K23, K24...) hoặc áp dụng chung ("ALL")
        if "ALL" in applies_to or khoa in applies_to:
            retrieved_chunks.append(meta)
            
            # Lấy thông tin Tên văn bản và Số quyết định từ Supabase
            chunk_db = db.query(models.DocumentChunk).filter(models.DocumentChunk.faiss_id == meta["faiss_id"]).first()
            if chunk_db and chunk_db.version:
                citations.append({
                    "page_number": meta["page_number"],
                    "decision_number": chunk_db.version.decision_number,
                    "doc_title": chunk_db.version.document.title if chunk_db.version.document else "Quy chế TVU"
                })
                
        if len(retrieved_chunks) >= top_k:
            break

    # Ghép ngữ cảnh
    context_str = "\n---\n".join([c["content"] for c in retrieved_chunks])
    
    # Loại bỏ các trích dẫn trùng lặp
    unique_citations = []
    seen = set()
    for c in citations:
        key = (c["page_number"], c["decision_number"])
        if key not in seen:
            seen.add(key)
            unique_citations.append(c)

    return context_str, unique_citations

def generate_rag_response(query: str, khoa: str, db: Session) -> Tuple[str, List[Dict[str, Any]]]:
    """Thực hiện luồng RAG tìm kiếm ngữ cảnh và gọi Gemini tạo câu trả lời."""
    context_str, citations = retrieve_context(query, khoa, db)
    
    if not context_str.strip():
        return "Hiện tại chưa có dữ liệu quy chế áp dụng cho khóa của bạn về vấn đề này. Bạn vui lòng liên hệ Phòng Đào tạo TVU để được giải đáp cụ thể nhé.", []

    full_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context_str) + f"\n\nCÂU HỎI CỦA SINH VIÊN: {query}"
    
    model = genai.GenerativeModel(GEMINI_TEXT_MODEL)
    response = model.generate_content(full_prompt)
    
    return response.text, citations


def generate_rag_response_stream(query: str, khoa: str, db: Session):
    """
    Generator sinh câu trả lời RAG dạng Streaming từng chunk chữ.
    """
    context_str, citations = retrieve_context(query, khoa, db)
    
    if not context_str.strip():
        yield {
            "type": "content",
            "text": "Hiện tại chưa có dữ liệu quy chế áp dụng cho khóa của bạn về vấn đề này. Bạn vui lòng liên hệ Phòng Đào tạo TVU để được giải đáp cụ thể nhé."
        }
        yield {
            "type": "citations",
            "citations": []
        }
        return

    full_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context_str) + f"\n\nCÂU HỎI CỦA SINH VIÊN: {query}"
    
    model = genai.GenerativeModel(GEMINI_TEXT_MODEL)
    # Trong google.generativeai, streaming được bật qua tham số stream=True
    response_stream = model.generate_content(full_prompt, stream=True)
    
    # Bắn từng đoạn chữ sinh ra về router
    for chunk in response_stream:
        try:
            chunk_text = chunk.text
            if chunk_text:
                yield {
                    "type": "content",
                    "text": chunk_text
                }
        except Exception:
            continue

    # Bắn danh sách trích dẫn nguồn ở cuối dòng stream
    yield {
        "type": "citations",
        "citations": citations
    }
