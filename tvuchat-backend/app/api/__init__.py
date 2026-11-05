from app.db.session import engine, Base
from app.db.models import User, StudentProfile, Document, DocumentVersion, DocumentChunk, Conversation, Message

def init_db():
    print("⏳ Đang kết nối Supabase và tạo các bảng CSDL...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ KHỞI TẠO THÀNH CÔNG! Đã tạo đầy đủ 7 bảng trên Supabase.")
    except Exception as e:
        print(f"❌ Lỗi khởi tạo CSDL: {e}")

if __name__ == "__main__":
    init_db()