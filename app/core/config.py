from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # File Storage
    UPLOAD_DIR: str = "./uploads"
    OUTPUT_DIR: str = "./outputs"
    MAX_FILE_SIZE: int = 107374182400  # 100GB (Effectively unlimited)
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    
    # App
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Create upload and output directories
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
