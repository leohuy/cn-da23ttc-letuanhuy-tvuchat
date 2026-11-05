import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, Text, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base

# 1. BẢNG NGƯỜI DÙNG
class User(Base):
    __tablename__ = "users"

    id = Column(String(128), primary_key=True)  # UUID hoặc Firebase UID
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)         # Mật khẩu đã băm bcrypt
    role = Column(String(20), nullable=False, default="STUDENT")  # GUEST, STUDENT, ADMIN
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user")

# 2. HỒ SƠ SINH VIÊN
class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id = Column(String(128), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    mssv = Column(String(20), unique=True, nullable=True)
    full_name = Column(String(100), nullable=False)
    khoa_tuyen_sinh = Column(String(20), nullable=False)  # VD: K23, DA23TTC
    nganh_hoc = Column(String(100), nullable=False)       # VD: CNTT
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile")

# 3. DANH MỤC VĂN BẢN QUY CHẾ
class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)      # VD: QC_HOC_VU
    title = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)               # HOC_VU, THI, REN_LUAN
    created_at = Column(DateTime, default=datetime.utcnow)

    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")

# 4. PHIÊN BẢN & HIỆU LỰC VĂN BẢN
class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    decision_number = Column(String(100), nullable=False)      # VD: 9101/QĐ-ĐHTV
    effective_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="DRAFT") # DRAFT, PUBLISHED, DEPRECATED
    applies_to_khoa = Column(JSONB, nullable=False)             # VD: ["K22", "K23", "K24"]
    replaces_version_id = Column(Integer, ForeignKey("document_versions.id"), nullable=True)
    file_path = Column(String(255), nullable=False)
    created_by = Column(String(128), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="versions")
    chunks = relationship("DocumentChunk", back_populates="version", cascade="all, delete-orphan")

# 5. CHUNK DỮ LIỆU ÁNH XẠ FAISS
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_id = Column(Integer, ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=False)
    section_title = Column(String(255), nullable=True)
    faiss_id = Column(Integer, unique=True, nullable=False)

    version = relationship("DocumentVersion", back_populates="chunks")

# 6. CUỘC TRÒ CHUYỆN
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    scope_type = Column(String(20), default="GENERAL")          # GENERAL hoặc PROFILE
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

# 7. CHI TIẾT TIN NHẮN & TRÍCH DẪN
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_type = Column(String(10), nullable=False)           # USER hoặc BOT
    content = Column(Text, nullable=False)
    citations = Column(JSONB, nullable=True)                   # Lưu danh sách trích dẫn
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
