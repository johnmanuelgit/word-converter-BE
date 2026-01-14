from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.routes import router
from app.core.exceptions import PDFConverterException


# Create FastAPI app
app = FastAPI(
    title="PDF to Word Converter API",
    description="Production-ready PDF to DOCX conversion service",
    version="1.0.0"
)

# Global Exception Handler
@app.exception_handler(PDFConverterException)
async def pdf_converter_exception_handler(request: Request, exc: PDFConverterException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.code,
            "message": exc.message,
            "detail": str(exc)
        },
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "online",
        "service": "PDF to Word Converter",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "storage": "in-memory",
        "mode": "no-db"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
