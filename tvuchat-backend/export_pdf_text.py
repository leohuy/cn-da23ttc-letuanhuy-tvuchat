import os
import sys
import time
import argparse
import pdfplumber
from app.services.text_cleaner import clean_vietnamese_text
from app.services.pdf_parser import ocr_page_image

# Thiết lập bảng mã UTF-8 an toàn cho console Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def export_pdf_to_text(pdf_path: str, output_path: str, chunk_size: int = 600, overlap: int = 100, max_pages: int = None):
    """
    Trích xuất toàn bộ văn bản từ PDF (hỗ trợ OCR cho trang scan)
    và xuất ra file .txt định dạng rõ ràng theo từng trang và từng chunk.
    """
    if not os.path.exists(pdf_path):
        print(f"[ERROR] Khong tim thay file PDF tai: {pdf_path}")
        return

    start_time = time.time()
    print(f"[INFO] Bat dau trich xuat tu file: {pdf_path}")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    page_records = []
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        process_pages = total_pages if max_pages is None else min(total_pages, max_pages)
        print(f"[INFO] Tong so trang can xu ly: {process_pages}/{total_pages}")
        
        for idx in range(process_pages):
            page_num = idx + 1
            page = pdf.pages[idx]
            page_text = page.extract_text() or ""
            cleaned = clean_vietnamese_text(page_text)
            
            method = "PDF_TEXT"
            # Nếu trang ít chữ -> Chạy OCR
            if len(cleaned.strip()) < 30:
                print(f"[OCR] Trang {page_num}/{process_pages} khong co text thuan, dang chay OCR...")
                ocr_raw = ocr_page_image(pdf_path, page_num)
                cleaned = clean_vietnamese_text(ocr_raw)
                method = "OCR_TESSERACT"
            else:
                print(f"[TEXT] Trang {page_num}/{process_pages} trich xuat text truc tiep thanh cong.")
                
            page_records.append({
                "page_num": page_num,
                "method": method,
                "text": cleaned,
                "char_count": len(cleaned),
                "word_count": len(cleaned.split()) if cleaned else 0
            })

    # Cắt thành các chunk
    chunks = []
    for item in page_records:
        text = item["text"]
        p_num = item["page_num"]
        words = text.split(" ") if text else []
        
        if not words:
            continue
            
        if len(words) <= chunk_size:
            chunks.append({
                "page_number": p_num,
                "content": text,
                "word_count": len(words)
            })
        else:
            for i in range(0, len(words), chunk_size - overlap):
                chunk_words = words[i:i + chunk_size]
                chunk_str = " ".join(chunk_words).strip()
                if len(chunk_str) > 10:
                    chunks.append({
                        "page_number": p_num,
                        "content": chunk_str,
                        "word_count": len(chunk_words)
                    })

    # Ghi ra file .txt
    with open(output_path, "w", encoding="utf-8-sig") as f:
        f.write("=" * 80 + "\n")
        f.write("BÁO CÁO KẾT QUẢ TRÍCH XUẤT VĂN BẢN QUY CHẾ TVU TỪ PDF\n")
        f.write("=" * 80 + "\n")
        f.write(f"- File nguồn: {pdf_path}\n")
        f.write(f"- Số trang đã đọc: {len(page_records)} / {total_pages}\n")
        f.write(f"- Tổng số chunks tạo thành: {len(chunks)}\n")
        f.write(f"- Thời gian xuất: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        # PHẦN 1: TOÀN VĂN THEO TỪNG TRANG
        f.write("#" * 80 + "\n")
        f.write("PHẦN 1: NỘI DUNG VĂN BẢN CHI TIẾT THEO TỪNG TRANG\n")
        f.write("#" * 80 + "\n\n")
        
        for item in page_records:
            f.write("-" * 80 + "\n")
            f.write(f"TRANG {item['page_num']} | Phương thức: {item['method']} | Số ký tự: {item['char_count']} | Số từ: {item['word_count']}\n")
            f.write("-" * 80 + "\n")
            f.write(item["text"] if item["text"] else "[KHÔNG CÓ DỮ LIỆU]")
            f.write("\n\n")

        # PHẦN 2: DANH SÁCH CHUNKS PHỤC VỤ VECTOR DB
        f.write("\n" + "#" * 80 + "\n")
        f.write("PHẦN 2: DANH SÁCH CÁC CHUNKS SAU KHI PHÂN ĐOẠN (DÙNG CHO VECTOR DB)\n")
        f.write(f"(Cấu hình: Chunk Size = {chunk_size} từ, Overlap = {overlap} từ)\n")
        f.write("#" * 80 + "\n\n")
        
        for idx, chunk in enumerate(chunks, 1):
            f.write("=" * 80 + "\n")
            f.write(f"CHUNK #{idx} | Nguồn: Trang {chunk['page_number']} | Độ dài: {chunk['word_count']} từ\n")
            f.write("=" * 80 + "\n")
            f.write(chunk["content"])
            f.write("\n\n")

    elapsed_time = time.time() - start_time
    print(f"\n[SUCCESS] Da xuat toan bo du lieu thanh cong ra file: {output_path}")
    print(f"[THONG SO] Tong so trang: {len(page_records)} | Tong so chunks: {len(chunks)} | Thoi gian: {elapsed_time:.2f}s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script trich xuat noi dung PDF ra file TXT de kiem tra chat luong")
    parser.add_argument("--pdf", type=str, default="data/pdfs/quychehocvu.pdf", help="Duong dan den file PDF")
    parser.add_argument("--output", type=str, default="data/extracted_quychehocvu.txt", help="Duong dan file TXT dau ra")
    parser.add_argument("--max-pages", type=int, default=None, help="So trang toi da can xu ly (de test nhanh, mac dinh xu ly het)")
    parser.add_argument("--chunk-size", type=int, default=600, help="Kich thuoc chunk (so tu)")
    parser.add_argument("--overlap", type=int, default=100, help="Do chong lap chunk (so tu)")
    
    args = parser.parse_args()
    export_pdf_to_text(
        pdf_path=args.pdf,
        output_path=args.output,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        max_pages=args.max_pages
    )

