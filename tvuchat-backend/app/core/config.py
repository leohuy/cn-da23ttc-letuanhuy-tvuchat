import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "TVUCHAT API"
    API_V1_STR: str = "/api/v1"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Cấu hình JWT Authentication
    SECRET_KEY: str = os.getenv("SECRET_KEY", "tvuchat_secret_key_super_secure_2026_grad_project")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # Token có hiệu lực trong 7 ngày

settings = Settings()
