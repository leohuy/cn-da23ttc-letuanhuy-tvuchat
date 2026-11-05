import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db import models
from app.core.security import get_password_hash, verify_password, create_access_token
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserProfileResponse

router = APIRouter()

def authenticate_user(identifier: str, password: str, db: Session) -> TokenResponse:
    """Hàm xác thực dùng chung cho cả Login JSON và Token Form của OAuth2."""
    # Tìm user theo Email hoặc truy vấn MSSV sang bảng student_profiles
    user = db.query(models.User).filter(models.User.email == identifier).first()
    
    if not user:
        profile = db.query(models.StudentProfile).filter(models.StudentProfile.mssv == identifier).first()
        if profile:
            user = db.query(models.User).filter(models.User.id == profile.user_id).first()

    if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thông tin tài khoản hoặc mật khẩu không chính xác.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị khóa."
        )

    # Lấy hồ sơ sinh viên
    profile = user.profile
    khoa = profile.khoa_tuyen_sinh if profile else "ALL"
    full_name = profile.full_name if profile else "Sinh viên"

    # Tạo JWT Token đính kèm thông tin Khóa tuyển sinh
    access_token = create_access_token(
        subject=user.id,
        extra_data={
            "role": user.role,
            "khoa_tuyen_sinh": khoa
        }
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        full_name=full_name,
        khoa_tuyen_sinh=khoa
    )


@router.post("/register", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
def register_student(
    payload: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Đăng ký tài khoản sinh viên mới (tạo đồng thời User và StudentProfile).
    """
    # 1. Kiểm tra Email đã tồn tại chưa
    existing_user = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email này đã được đăng ký tài khoản trên hệ thống."
        )

    # 2. Kiểm tra MSSV đã tồn tại chưa
    existing_mssv = db.query(models.StudentProfile).filter(models.StudentProfile.mssv == payload.mssv).first()
    if existing_mssv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã số sinh viên (MSSV) này đã được sử dụng."
        )

    # 3. Tạo User trong transaction
    user_id = str(uuid.uuid4())
    new_user = models.User(
        id=user_id,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role="STUDENT",
        is_active=True
    )
    db.add(new_user)
    db.flush()  # Giữ transaction để lấy user_id

    # 4. Tạo StudentProfile liên kết
    profile = models.StudentProfile(
        user_id=user_id,
        mssv=payload.mssv,
        full_name=payload.full_name,
        khoa_tuyen_sinh=payload.khoa_tuyen_sinh,
        nganh_hoc=payload.nganh_hoc
    )
    db.add(profile)
    db.commit()
    db.refresh(new_user)

    return UserProfileResponse(
        user_id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        mssv=profile.mssv,
        full_name=profile.full_name,
        khoa_tuyen_sinh=profile.khoa_tuyen_sinh,
        nganh_hoc=profile.nganh_hoc
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Đăng nhập bằng Email hoặc MSSV + Mật khẩu (Dành cho Frontend / JSON Body).
    """
    return authenticate_user(payload.email_or_mssv, payload.password, db)


@router.post("/token", response_model=TokenResponse)
def login_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Endpoint chuẩn OAuth2 Password Flow (Dành cho nút 'Authorize' trên Swagger UI).
    """
    return authenticate_user(form_data.username, form_data.password, db)
