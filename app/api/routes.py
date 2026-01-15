from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from app.models.conversion import ConversionModel, ConversionResponse, ConversionType, ConversionStatus
from app.services.pdf_service import PDFService
from app.core.config import settings
import os

from datetime import datetime
from typing import Dict


router = APIRouter(prefix="/api", tags=["conversions"])

# In-memory storage for conversions
conversions_db: Dict[str, ConversionModel] = {}



def process_conversion_background(conversion_id: str, pdf_path: str, output_dir: str):
    """
    Background task for PDF to DOCX conversion (replaces Celery task)
    """
    if conversion_id not in conversions_db:
        return
        
    conversion = conversions_db[conversion_id]
    
    try:
        from app.core.exceptions import PDFConverterException
        
        print(f"🔄 Starting conversion for {conversion_id}")
        
        # Update status to PROCESSING
        conversion.status = ConversionStatus.PROCESSING
        
        # Validate PDF file
        # Service now raises specific exceptions (InvalidFileError, PasswordProtectedError, etc.)
        PDFService.validate_pdf_file(pdf_path)
        
        # Generate output file path
        output_path = os.path.join(output_dir, f"{conversion_id}.docx")
        
        # Perform conversion with automatic fallback
        # Service now raises specific exceptions/ConversionError on failure
        success, used_ocr = PDFService.convert_pdf_to_docx(pdf_path, output_path)
        
        # Update status to COMPLETED
        conversion.status = ConversionStatus.COMPLETED
        conversion.converted_file_path = output_path
        conversion.is_scanned_pdf = used_ocr
        conversion.completed_at = datetime.utcnow()
            
        print(f"✅ Conversion completed for {conversion_id} (OCR: {used_ocr})")
        
    except PDFConverterException as e:
        # Handle known errors (Password, Corrupt, OCR failed)
        error_message = e.message
        print(f"❌ Conversion failed (Expected): {error_message}")
        
        conversion.status = ConversionStatus.FAILED
        conversion.error_message = error_message

    except Exception as e:
        # Handle unknown errors
        error_message = f"Unexpected system error: {str(e)}"
        print(f"❌ Conversion failed (Unexpected): {error_message}")
        
        conversion.status = ConversionStatus.FAILED
        conversion.error_message = error_message
        
    finally:
        # Clean up uploaded file on failure if needed, or just keep common cleanup logic
        if conversion.status == ConversionStatus.FAILED and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass



@router.post("/conversions/", response_model=ConversionResponse, status_code=201)
async def create_conversion(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload PDF file and create conversion job
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )
    
    # Read file content
    try:
        content = await file.read()
        file_size = len(content)
            
        if file_size > settings.MAX_FILE_SIZE:
             raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")
    
    # Create conversion record
    conversion = ConversionModel(
        original_file_name=file.filename,
        file_size=file_size,
        upload_file_path="",
        conversion_type=ConversionType.PDF_TO_WORD
    )
    
    # Save file to disk
    file_path = os.path.join(settings.UPLOAD_DIR, f"{conversion.id}.pdf")
    
    try:
        with open(file_path, 'wb') as f:
            f.write(content)
        
        conversion.upload_file_path = file_path
        
        # Save to in-memory db
        conversions_db[conversion.id] = conversion
        
        # Trigger background task
        background_tasks.add_task(
            process_conversion_background,
            conversion.id,
            file_path,
            settings.OUTPUT_DIR
        )
        
        # Return response
        return ConversionResponse(
            id=conversion.id,
            original_file_name=conversion.original_file_name,
            file_size=conversion.file_size,
            status=conversion.status,
            conversion_type=conversion.conversion_type,
            is_scanned_pdf=conversion.is_scanned_pdf,
            error_message=conversion.error_message,
            created_at=conversion.created_at.isoformat(),
            completed_at=None
        )
        
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to create conversion: {str(e)}")


@router.get("/conversions/{conversion_id}/", response_model=ConversionResponse)
async def get_conversion(conversion_id: str):
    """
    Get conversion status by ID
    """
    if conversion_id not in conversions_db:
        raise HTTPException(status_code=404, detail="Conversion not found")
    
    conversion = conversions_db[conversion_id]
    
    return ConversionResponse(
        id=conversion.id,
        original_file_name=conversion.original_file_name,
        file_size=conversion.file_size,
        status=conversion.status,
        conversion_type=conversion.conversion_type,
        is_scanned_pdf=conversion.is_scanned_pdf,
        error_message=conversion.error_message,
        created_at=conversion.created_at.isoformat(),
        completed_at=conversion.completed_at.isoformat() if conversion.completed_at else None
    )


@router.get("/conversions/{conversion_id}/download/")
async def download_conversion(conversion_id: str):
    """
    Download converted DOCX file
    """
    if conversion_id not in conversions_db:
        raise HTTPException(status_code=404, detail="Conversion not found")
        
    conversion = conversions_db[conversion_id]
    
    if conversion.status != ConversionStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Conversion not ready. Current status: {conversion.status}"
        )
    
    if not conversion.converted_file_path or not os.path.exists(conversion.converted_file_path):
        raise HTTPException(status_code=404, detail="Converted file not found")
    
    # Generate download filename
    base_name = os.path.splitext(conversion.original_file_name)[0]
    download_name = f"{base_name}.docx"
    
    return FileResponse(
        path=conversion.converted_file_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )



