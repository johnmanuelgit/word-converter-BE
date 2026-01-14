from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
from uuid import uuid4


class ConversionStatus(str, Enum):
    """Conversion status enumeration"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ConversionType(str, Enum):
    """Conversion type enumeration"""
    PDF_TO_WORD = "PDF_TO_WORD"
    # Future: PDF_TO_EXCEL, IMAGE_TO_PDF, etc.


class ConversionModel(BaseModel):
    """Conversion document model"""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    original_file_name: str
    file_size: int
    upload_file_path: str
    converted_file_path: Optional[str] = None
    status: ConversionStatus = ConversionStatus.PENDING
    conversion_type: ConversionType = ConversionType.PDF_TO_WORD
    is_scanned_pdf: bool = False
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ConversionResponse(BaseModel):
    """Response model for conversion API"""
    
    id: str
    original_file_name: str
    file_size: int
    status: ConversionStatus
    conversion_type: ConversionType
    is_scanned_pdf: bool
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    
    class Config:
        from_attributes = True
