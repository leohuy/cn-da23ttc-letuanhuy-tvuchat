import re

def clean_vietnamese_text(text: str) -> str:
    """Làm sạch văn bản PDF: sửa lỗi font VNI, loại bỏ ký tự rác và khoảng trắng thừa."""
    if not text:
        return ""
    
    # Sửa lỗi font VNI phổ biến trong tài liệu quy chế cũ
    vni_map = {
        "ƣ": "ư", "Ƣ": "Ư",
        "ơ": "ơ", "Ơ": "Ơ",
        "à": "à", "á": "á", "ả": "ả", "ã": "ã", "ạ": "ạ",
        "ề": "ề", "ế": "ế", "ể": "ể", "ễ": "ễ", "ệ": "ệ",
    }
    for old, new in vni_map.items():
        text = text.replace(old, new)
        
    # Loại bỏ các gạch dọc bảng biểu rác do pdfplumber tạo ra
    text = re.sub(r'\|\s*', ' ', text)
    
    # Thu gọn khoảng trắng thừa và dòng trống liên tiếp
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    
    return text.strip()