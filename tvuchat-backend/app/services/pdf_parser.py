import os
import sys
import pdfplumber
import pytesseract
import pypdfium2 as pdfium
from typing import List, Dict, Any
from app.services.text_cleaner import clean_vietnamese_text

# Cấu hình encoding an toàn cho console Windows tránh UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Cấu hình Tesseract OCR (Windows)
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def ocr_page_image(file_path: str, page_number: int) -> str:
    """Chuyển trang PDF thành ảnh bằng pypdfium2 và OCR bằng Tesseract."""
    try:
        pdf = pdfium.PdfDocument(file_path)
        # Trang trong pypdfium2 tính từ 0
        page = pdf[page_number - 1]
        
        # Render trang PDF ra ảnh PIL với độ phân giải cao (scale=2)
        pil_image = page.render(scale=2).to_pil()
        
        # Chạy OCR
        ocr_text = pytesseract.image_to_string(pil_image, lang='vie+eng')
        return ocr_text
    except Exception as e:
        print(f"[ERROR] OCR trang {page_number}: {e}")
        return ""

def extract_and_chunk_pdf(file_path: str, chunk_size: int = 600, overlap: int = 100) -> List[Dict[str, Any]]:
    chunks = []
    try:
        with pdfplumber.open(file_path) as pdf:
            full_page_texts = []
            print(f"[INFO] Dang xu ly file PDF co {len(pdf.pages)} trang...")
            
            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1
                page_text = page.extract_text() or ""
                cleaned_text = clean_vietnamese_text(page_text)
                
                # Nếu trang ít chữ -> Thử chạy OCR
                if len(cleaned_text.strip()) < 30:
                    print(f"[OCR] Trang {page_num} khong co text thuan, dang chay OCR...")
                    ocr_raw = ocr_page_image(file_path, page_num)
                    cleaned_text = clean_vietnamese_text(ocr_raw)
                
                if cleaned_text:
                    full_page_texts.append({
                        "page_number": page_num,
                        "text": cleaned_text
                    })

        # Chia chunk
        for item in full_page_texts:
            text = item["text"]
            page_num = item["page_number"]
            words = text.split(" ")
            
            if len(words) <= chunk_size:
                chunks.append({"content": text, "page_number": page_num})
            else:
                for i in range(0, len(words), chunk_size - overlap):
                    chunk_words = words[i:i + chunk_size]
                    chunk_str = " ".join(chunk_words)
                    if len(chunk_str.strip()) > 10:
                        chunks.append({"content": chunk_str, "page_number": page_num})
                        
    except Exception as e:
        print(f"[ERROR] READ PDF: {e}")

    print(f"[SUCCESS] Tong so chunks trich xuat duoc: {len(chunks)}")
    return chunks
