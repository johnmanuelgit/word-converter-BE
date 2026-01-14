from app.tasks.celery_worker import celery_app
from app.services.pdf_service import PDFService
from app.models.conversion import ConversionStatus
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import os
import asyncio


def get_sync_db():
    """Get synchronous MongoDB connection for Celery tasks"""
    from pymongo import MongoClient
    client = MongoClient(settings.MONGODB_URL)
    return client[settings.MONGODB_DB_NAME]


@celery_app.task(bind=True, name='app.tasks.convert_pdf_to_docx')
def convert_pdf_to_docx_task(self, conversion_id: str, pdf_path: str, output_dir: str):
    """
    Celery task for PDF to DOCX conversion
    
    Args:
        conversion_id: Conversion ID
        pdf_path: Path to uploaded PDF file
        output_dir: Directory for output files
    """
    db = get_sync_db()
    collection = db.conversions
    
    try:
        # Update status to PROCESSING
        collection.update_one(
            {"id": conversion_id},
            {"$set": {"status": ConversionStatus.PROCESSING.value}}
        )
        
        print(f"🔄 Starting conversion for {conversion_id}")
        
        # Validate PDF file
        if not PDFService.validate_pdf_file(pdf_path):
            raise Exception("Invalid or corrupted PDF file")
        
        # Generate output file path
        output_path = os.path.join(output_dir, f"{conversion_id}.docx")
        
        # Perform conversion with automatic fallback
        success, used_ocr = PDFService.convert_pdf_to_docx(pdf_path, output_path)
        
        if not success:
            raise Exception("Conversion failed - unable to process PDF")
        
        # Update status to COMPLETED
        from datetime import datetime
        collection.update_one(
            {"id": conversion_id},
            {
                "$set": {
                    "status": ConversionStatus.COMPLETED.value,
                    "converted_file_path": output_path,
                    "is_scanned_pdf": used_ocr,
                    "completed_at": datetime.utcnow().isoformat()
                }
            }
        )
        
        print(f"✅ Conversion completed for {conversion_id} (OCR: {used_ocr})")
        
        # Optional: Clean up original PDF after successful conversion
        # os.remove(pdf_path)
        
        return {
            "status": "success",
            "conversion_id": conversion_id,
            "output_path": output_path,
            "used_ocr": used_ocr
        }
        
    except Exception as e:
        error_message = str(e)
        print(f"❌ Conversion failed for {conversion_id}: {error_message}")
        
        # Update status to FAILED
        collection.update_one(
            {"id": conversion_id},
            {
                "$set": {
                    "status": ConversionStatus.FAILED.value,
                    "error_message": error_message
                }
            }
        )
        
        # Clean up uploaded file on failure
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception as cleanup_error:
                print(f"Failed to clean up file: {cleanup_error}")
        
        raise
