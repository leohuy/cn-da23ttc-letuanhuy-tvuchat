from pydantic import BaseModel
from typing import List, Optional

from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel

class CitationSchema(BaseModel):
    page_number: int
    decision_number: str
    doc_title: str

class ChatMessageRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    # khoa_tuyen_sinh giờ là tùy chọn (Optional)
    khoa_tuyen_sinh: Optional[str] = None

class ChatMessageResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: List[CitationSchema]

# --- LỊCH SỬ HỘI THOẠI ---
class ConversationResponse(BaseModel):
    """Schema trả về thông tin tóm tắt của một cuộc trò chuyện trên Sidebar."""
    id: str
    title: str
    scope_type: str
    created_at: datetime

    class Config:
        from_attributes = True  # Cho phép Pydantic đọc trực tiếp từ SQLAlchemy ORM Model

class MessageDetailResponse(BaseModel):
    """Schema trả về từng tin nhắn trong màn hình Chat chính."""
    id: int
    conversation_id: str
    sender_type: str
    content: str
    citations: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True