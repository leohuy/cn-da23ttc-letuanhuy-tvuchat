import uuid
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.db import models
from app.db.session import SessionLocal
from app.schemas.chat import (
    ChatMessageRequest, 
    ChatMessageResponse, 
    ConversationResponse, 
    MessageDetailResponse
)
from app.services.gemini_service import generate_rag_response, generate_rag_response_stream

router = APIRouter()

# 1. API GỬI TIN NHẮN (Đã bảo mật + Tự động lấy Khóa tuyển sinh)
@router.post("/send-message", response_model=ChatMessageResponse)
def send_message(
    payload: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)  # <--- BẮT BUỘC AUTH
):
    # Lấy thông tin Hồ sơ sinh viên từ token
    profile = current_user.profile
    khoa_sinh_vien = profile.khoa_tuyen_sinh if profile else "ALL"

    conversation_id = payload.conversation_id

    # Kiểm tra conversation_id hợp lệ
    existing_conv = None
    if conversation_id and conversation_id.strip() and conversation_id != "string":
        existing_conv = db.query(models.Conversation).filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == current_user.id  # Kiểm tra đúng chủ sở hữu
        ).first()

    # Tạo conversation mới gắn liền với user_id của sinh viên
    if not existing_conv:
        conversation_id = str(uuid.uuid4())
        conv = models.Conversation(
            id=conversation_id,
            user_id=current_user.id,  # Gán ID sinh viên đang đăng nhập
            title=payload.message[:50],
            scope_type="GENERAL"
        )
        db.add(conv)
        db.commit()

    # Lưu câu hỏi USER
    user_msg = models.Message(
        conversation_id=conversation_id,
        sender_type="USER",
        content=payload.message
    )
    db.add(user_msg)
    db.commit()

    # Chạy RAG Core với Khóa tuyển sinh lấy tự động từ Profile
    answer, citations = generate_rag_response(
        query=payload.message,
        khoa=payload.khoa_tuyen_sinh or khoa_sinh_vien,
        db=db
    )

    # Lưu câu trả lời BOT
    bot_msg = models.Message(
        conversation_id=conversation_id,
        sender_type="BOT",
        content=answer,
        citations=citations
    )
    db.add(bot_msg)
    db.commit()

    return ChatMessageResponse(
        conversation_id=conversation_id,
        answer=answer,
        citations=citations
    )


# 2. API LẤY DANH SÁCH CUỘC TRÒ CHUYỆN (Chỉ lấy của Sinh viên đang đăng nhập)
@router.get("/conversations", response_model=List[ConversationResponse])
def get_conversations(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    conversations = (
        db.query(models.Conversation)
        .filter(models.Conversation.user_id == current_user.id)  # Lọc theo ID sinh viên
        .order_by(models.Conversation.created_at.desc())
        .limit(limit)
        .all()
    )
    return conversations


# 3. API LẤY CHI TIẾT TIN NHẮN CỦA 1 CUỘC TRÒ CHUYỆN
@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageDetailResponse])
def get_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()
    
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cuộc trò chuyện hoặc bạn không có quyền truy cập."
        )

    messages = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conversation_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
    return messages


# 4. API XÓA CUỘC TRÒ CHUYỆN
@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()
    
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cuộc trò chuyện để xóa."
        )

    db.query(models.Message).filter(models.Message.conversation_id == conversation_id).delete()
    db.delete(conv)
    db.commit()

    return {"status": "success", "message": f"Đã xóa thành công cuộc trò chuyện {conversation_id}"}


# 5. API GỬI TIN NHẮN STREAMING (Server-Sent Events)
@router.post("/send-message-stream")
def send_message_stream(
    payload: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    profile = current_user.profile
    khoa_sinh_vien = profile.khoa_tuyen_sinh if profile else "ALL"

    conversation_id = payload.conversation_id

    # 1. Kiểm tra / Tạo mới cuộc trò chuyện
    existing_conv = None
    if conversation_id and conversation_id.strip() and conversation_id != "string":
        existing_conv = db.query(models.Conversation).filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == current_user.id
        ).first()

    if not existing_conv:
        conversation_id = str(uuid.uuid4())
        conv = models.Conversation(
            id=conversation_id,
            user_id=current_user.id,
            title=payload.message[:50],
            scope_type="GENERAL"
        )
        db.add(conv)
        db.commit()

    # 2. Lưu câu hỏi USER vào CSDL
    user_msg = models.Message(
        conversation_id=conversation_id,
        sender_type="USER",
        content=payload.message
    )
    db.add(user_msg)
    db.commit()

    # 3. Định nghĩa Generator đóng gói chuẩn định dạng SSE
    def sse_event_generator():
        stream_db = SessionLocal()
        try:
            full_bot_answer = ""
            final_citations = []

            # Gửi thông điệp khởi tạo chứa conversation_id để Frontend lưu state
            init_payload = json.dumps({"type": "init", "conversation_id": conversation_id}, ensure_ascii=False)
            yield f"data: {init_payload}\n\n"

            # Lấy từng chunk từ Gemini Stream
            for item in generate_rag_response_stream(
                query=payload.message,
                khoa=payload.khoa_tuyen_sinh or khoa_sinh_vien,
                db=stream_db
            ):
                if item["type"] == "content":
                    full_bot_answer += item["text"]
                    chunk_payload = json.dumps({"type": "content", "text": item["text"]}, ensure_ascii=False)
                    yield f"data: {chunk_payload}\n\n"
                elif item["type"] == "citations":
                    final_citations = item["citations"]
                    citations_payload = json.dumps({"type": "citations", "citations": final_citations}, ensure_ascii=False)
                    yield f"data: {citations_payload}\n\n"

            # 4. Khi stream hoàn tất: Lưu câu trả lời tổng hợp đầy đủ của BOT vào Supabase
            bot_msg = models.Message(
                conversation_id=conversation_id,
                sender_type="BOT",
                content=full_bot_answer,
                citations=final_citations
            )
            stream_db.add(bot_msg)
            stream_db.commit()
        except Exception as e:
            stream_db.rollback()
            error_payload = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            yield f"data: {error_payload}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")
