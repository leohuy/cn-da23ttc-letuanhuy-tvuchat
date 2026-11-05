from pydantic import BaseModel
from typing import Optional

# Dữ liệu Sinh viên gửi lên khi Đăng ký
class RegisterRequest(BaseModel):
    email: str
    password: str
    mssv: str
    full_name: str
    khoa_tuyen_sinh: str  
    nganh_hoc: str       

# Dữ liệu gửi lên khi Đăng nhập
class LoginRequest(BaseModel):
    email_or_mssv: str
    password: str

# Cấu trúc trả về của JWT Token
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    khoa_tuyen_sinh: str

# Cấu trúc Hồ sơ Sinh viên trả về
class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    role: str
    mssv: str
    full_name: str
    khoa_tuyen_sinh: str
    nganh_hoc: str

    class Config:
        from_attributes = True
