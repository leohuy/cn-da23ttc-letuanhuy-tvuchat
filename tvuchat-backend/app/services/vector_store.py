import os
import pickle
import faiss
import numpy as np
from typing import List, Dict, Any
import google.generativeai as genai
from app.core.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

INDEX_PATH = "data/faiss_index/index.faiss"
METADATA_PATH = "data/faiss_index/metadata.pkl"

class VectorStoreService:
    def __init__(self):
        self.dimension = 768  # Kích thước vector chuẩn tương thích FAISS
        self.index = None
        self.metadata_store: List[Dict[str, Any]] = []
        self.embedding_model = "models/gemini-embedding-001"
        self._load_or_create_index()

    def _load_or_create_index(self):
        """Khôi phục FAISS Index từ đĩa hoặc tạo mới nếu chưa tồn tại."""
        os.makedirs("data/faiss_index", exist_ok=True)
        if os.path.exists(INDEX_PATH) and os.path.exists(METADATA_PATH):
            try:
                self.index = faiss.read_index(INDEX_PATH)
                with open(METADATA_PATH, "rb") as f:
                    self.metadata_store = pickle.load(f)
                print(f"[INFO] Khoi phuc FAISS index thanh cong: {self.index.ntotal} vectors")
            except Exception as e:
                print(f"[WARN] Khong the doc index cu ({e}), tao index moi...")
                self.index = faiss.IndexFlatL2(self.dimension)
                self.metadata_store = []
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata_store = []

    def save_index(self):
        """Lưu trạng thái FAISS Index và Metadata xuống đĩa."""
        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
        faiss.write_index(self.index, INDEX_PATH)
        with open(METADATA_PATH, "wb") as f:
            pickle.dump(self.metadata_store, f)

    def get_embedding(self, text: str, task_type: str = "retrieval_document") -> List[float]:
        """Tạo Vector Embedding đơn lẻ (dùng cho query tìm kiếm hoặc văn bản đơn)."""
        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=text,
                task_type=task_type,
                output_dimensionality=self.dimension
            )
            return result['embedding']
        except Exception:
            # Fallback không truyền task_type nếu model yêu cầu tham số tối giản
            result = genai.embed_content(
                model=self.embedding_model,
                content=text,
                output_dimensionality=self.dimension
            )
            return result['embedding']

    def get_batch_embeddings(self, texts: List[str], batch_size: int = 20) -> List[List[float]]:
        """Tạo Vector Embeddings theo lô (Batch) nhằm tăng tốc và tiết kiệm quota gọi API."""
        all_embeddings: List[List[float]] = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                res = genai.embed_content(
                    model=self.embedding_model,
                    content=batch,
                    task_type="retrieval_document",
                    output_dimensionality=self.dimension
                )
                embeddings = res.get('embedding', [])
                all_embeddings.extend(embeddings)
            except Exception as e:
                print(f"[WARN] Batch embedding gap loi ({e}), fallback sang embed tung text...")
                for item in batch:
                    vec = self.get_embedding(item, task_type="retrieval_document")
                    all_embeddings.append(vec)
                    
        return all_embeddings

    def add_chunks(self, chunks: List[Dict[str, Any]]) -> List[int]:
        """Tạo Embedding cho các chunk theo batch và nạp vào FAISS Index."""
        if not chunks:
            return []

        assigned_ids = []
        start_id = len(self.metadata_store)

        texts = [chunk["content"] for chunk in chunks]
        print(f"[INFO] Dang tao embedding cho {len(texts)} chunks...")
        embeddings = self.get_batch_embeddings(texts, batch_size=20)

        for idx, chunk in enumerate(chunks):
            faiss_id = start_id + idx
            assigned_ids.append(faiss_id)
            
            self.metadata_store.append({
                "faiss_id": faiss_id,
                "content": chunk["content"],
                "page_number": chunk["page_number"],
                "version_id": chunk["version_id"],
                "applies_to_khoa": chunk["applies_to_khoa"],
                "status": chunk["status"]
            })

        embeddings_np = np.array(embeddings, dtype=np.float32)
        self.index.add(embeddings_np)
        self.save_index()
        print(f"[SUCCESS] Da nap thanh cong {len(chunks)} chunks vao FAISS.")
        
        return assigned_ids

vector_service = VectorStoreService()
