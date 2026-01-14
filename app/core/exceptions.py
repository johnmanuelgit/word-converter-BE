class PDFConverterException(Exception):
    """Base exception for PDF converter application"""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)

class InvalidFileError(PDFConverterException):
    """Raised when file is not a valid PDF or is corrupted"""
    def __init__(self, message: str = "Invalid PDF file"):
        super().__init__(message, code="INVALID_FILE", status_code=400)

class PasswordProtectedError(PDFConverterException):
    """Raised when PDF is encrypted"""
    def __init__(self, message: str = "PDF is password protected"):
        super().__init__(message, code="PASSWORD_PROTECTED", status_code=400)

class OCRDetectionError(PDFConverterException):
    """Raised when OCR detection fails"""
    def __init__(self, message: str = "Failed to process scanned PDF"):
        super().__init__(message, code="OCR_ERROR", status_code=422)

class ConversionError(PDFConverterException):
    """Raised when conversion process fails"""
    def __init__(self, message: str = "Conversion failed"):
        super().__init__(message, code="CONVERSION_FAILED", status_code=500)

class StorageError(PDFConverterException):
    """Raised when file storage operations fail"""
    def __init__(self, message: str = "Storage operation failed"):
        super().__init__(message, code="STORAGE_ERROR", status_code=500)
