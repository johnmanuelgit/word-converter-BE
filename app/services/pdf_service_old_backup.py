"""
Enhanced PDF to DOCX Conversion Service

This service provides intelligent PDF conversion with proper handling of:
- Text-only PDFs (pure text content)
- Image-only PDFs (scanned documents)
- Mixed-content PDFs (text + images like CVs with photos)
- Scanned PDFs requiring OCR
- Complex layouts with tables and formatting

Key Improvements:
1. Intelligent image extraction from PDFs
2. Proper text extraction as editable content
3. OCR for scanned pages while preserving layout
4. Combines pdf2docx, PyPDF2, pdfplumber for robust extraction
5. Handles edge cases (encrypted PDFs, corrupted files, etc.)
"""

import os
import io
import sys
import tempfile
from pathlib import Path
from typing import Tuple, List, Dict, Any
from dataclasses import dataclass

# PDF Processing Libraries
import PyPDF2
from pdf2docx import Converter
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import pdfplumber

# Document Creation
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Error Handling
from app.core.exceptions import (
    InvalidFileError,
    PasswordProtectedError,
    OCRDetectionError,
    ConversionError,
    PDFConverterException
)

# Auto-configure Tesseract and Poppler for Windows
if sys.platform.startswith('win'):
    # Configure Tesseract Path
    tesseract_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\User\AppData\Local\Tesseract-OCR\tesseract.exe"
    ]
    
    for path in tesseract_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            print(f"✅ Found Tesseract OCR at: {path}")
            break
    
    # Configure Poppler Path
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    poppler_glob = list(Path(program_files).glob("poppler-*/bin"))
    if poppler_glob:
        poppler_bin = str(poppler_glob[0])
        if poppler_bin not in os.environ["PATH"]:
            os.environ["PATH"] += os.pathsep + poppler_bin
            print(f"✅ Added Poppler to PATH: {poppler_bin}")


@dataclass
class PDFAnalysis:
    """Results from analyzing a PDF"""
    is_scanned: bool
    has_images: bool
    has_text: bool
    text_percentage: float  # 0-100% of content that is text
    page_count: int
    is_encrypted: bool


class EnhancedPDFService:
    """
    Enhanced PDF Service with intelligent content detection and conversion.
    
    This service improves upon the basic approach by:
    1. Analyzing PDF content type before conversion
    2. Extracting embedded images separately from text
    3. Using OCR only when necessary
    4. Combining multiple extraction methods for best results
    """
    
    # Class constants for configuration
    DPI_FOR_OCR = 300  # High DPI for better OCR accuracy
    DPI_FOR_IMAGES = 200  # Image extraction DPI
    MIN_TEXT_LENGTH = 50  # Minimum text length to consider page as "text-based"
    TEXT_THRESHOLD = 30  # If >30% of content is text, treat as mixed/text-based
    
    @staticmethod
    def analyze_pdf(pdf_path: str) -> PDFAnalysis:
        """
        Comprehensive PDF analysis to determine content type and characteristics.
        
        This method examines the PDF to understand:
        - Whether it's scanned (image-based) or digital (text-based)
        - If it contains embedded images
        - Text vs image content ratio
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            PDFAnalysis object with detailed information
            
        Raises:
            InvalidFileError: If file is not a valid PDF
            PasswordProtectedError: If PDF is encrypted
        """
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                # Check encryption
                if reader.is_encrypted:
                    raise PasswordProtectedError("Cannot process encrypted PDF. Please remove password.")
                
                page_count = len(reader.pages)
                if page_count == 0:
                    raise InvalidFileError("PDF file is empty")
                
                # Initialize counters
                pages_with_text = 0
                pages_with_images = 0
                total_text_length = 0
                
                # Analyze first 5 pages (or all if less than 5)
                pages_to_check = min(5, page_count)
                
                for i in range(pages_to_check):
                    page = reader.pages[i]
                    
                    # Extract text
                    text = page.extract_text() or ""
                    total_text_length += len(text.strip())
                    
                    if len(text.strip()) > EnhancedPDFService.MIN_TEXT_LENGTH:
                        pages_with_text += 1
                    
                    # Check for images in page
                    if '/XObject' in page['/Resources']:
                        xobjects = page['/Resources']['/XObject'].get_object()
                        for obj in xobjects:
                            if xobjects[obj]['/Subtype'] == '/Image':
                                pages_with_images += 1
                                break
                
                # Calculate text percentage
                # Heuristic: average page should have ~2000 chars if fully text-based
                expected_text_if_full = pages_to_check * 2000
                text_percentage = min(100, (total_text_length / expected_text_if_full) * 100)
                
                # Determine if scanned
                is_scanned = pages_with_text == 0 or text_percentage < 10
                
                return PDFAnalysis(
                    is_scanned=is_scanned,
                    has_images=pages_with_images > 0,
                    has_text=pages_with_text > 0,
                    text_percentage=text_percentage,
                    page_count=page_count,
                    is_encrypted=False
                )
                
        except (PasswordProtectedError, InvalidFileError):
            raise
        except PyPDF2.errors.PdfReadError:
            raise InvalidFileError("File is corrupted or not a valid PDF")
        except Exception as e:
            raise InvalidFileError(f"Could not analyze PDF: {str(e)}")
    
    @staticmethod
    def extract_images_from_page(pdf_path: str, page_num: int) -> List[Image.Image]:
        """
        Extract embedded images from a specific PDF page.
        
        This is crucial for properly handling CVs and documents with photos.
        Instead of converting the whole page to an image, we extract only
        the actual embedded images.
        
        Args:
            pdf_path: Path to PDF file
            page_num: Page number (0-indexed)
            
        Returns:
            List of PIL Image objects extracted from the page
        """
        images = []
        
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                page = reader.pages[page_num]
                
                if '/XObject' not in page['/Resources']:
                    return images
                
                xobjects = page['/Resources']['/XObject'].get_object()
                
                for obj_name in xobjects:
                    obj = xobjects[obj_name]
                    
                    if obj['/Subtype'] == '/Image':
                        # Extract image data
                        try:
                            size = (obj['/Width'], obj['/Height'])
                            data = obj.get_data()
                            
                            # Handle different image formats
                            if obj['/ColorSpace'] == '/DeviceRGB':
                                mode = "RGB"
                            elif obj['/ColorSpace'] == '/DeviceGray':
                                mode = "L"
                            else:
                                mode = "RGB"
                            
                            # Create PIL Image
                            img = Image.frombytes(mode, size, data)
                            images.append(img)
                            
                        except Exception as e:
                            print(f"Warning: Could not extract image from page {page_num}: {e}")
                            continue
                            
        except Exception as e:
            print(f"Error extracting images from page {page_num}: {e}")
        
        return images
    
    @staticmethod
    def convert_text_based_pdf(pdf_path: str, output_path: str) -> None:
        """
        Convert text-based PDF using pdf2docx library.
        
        This method is best for pure text PDFs as it preserves:
        - Formatting (fonts, sizes, colors)
        - Layout (columns, spacing)
        - Tables and lists
        - Embedded images
        
        Args:
            pdf_path: Input PDF path
            output_path: Output DOCX path
            
        Raises:
            ConversionError: If conversion fails
        """
        try:
            print("Converting text-based PDF using pdf2docx...")
            cv = Converter(pdf_path)
            cv.convert(output_path)
            cv.close()
            print("✅ Text-based conversion completed successfully")
        except Exception as e:
            msg = str(e).lower()
            if "encrypted" in msg or "password" in msg:
                raise PasswordProtectedError()
            raise ConversionError(f"Text conversion failed: {str(e)}")
    
    @staticmethod
    def convert_mixed_content_pdf(pdf_path: str, output_path: str) -> None:
        """
        Convert PDF with mixed content (text + images) using pdfplumber.
        
        This is the CRITICAL method for handling CVs with photos properly.
        Instead of converting the whole page to an image:
        1. Extract text as editable text
        2. Extract images separately and insert them
        3. Maintain proper layout and formatting
        
        Args:
            pdf_path: Input PDF path
            output_path: Output DOCX path
            
        Raises:
            ConversionError: If conversion fails
        """
        try:
            print("Converting mixed-content PDF (text + images)...")
            doc = Document()
            
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    print(f"Processing page {page_num + 1}/{len(pdf.pages)}...")
                    
                    # Extract text from the page
                    text = page.extract_text()
                    
                    # Extract images using PyPDF2 (pdfplumber doesn't extract well)
                    images = EnhancedPDFService.extract_images_from_page(pdf_path, page_num)
                    
                    # Add page heading
                    if page_num > 0:
                        doc.add_page_break()
                    
                    # Insert images first (typically header images like profile photos)
                    for idx, img in enumerate(images):
                        try:
                            # Save image temporarily
                            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_img:
                                img.save(tmp_img.name, 'PNG')
                                
                                # Add to document with reasonable size
                                # Limit width to 3 inches for profile photos, 6 for full-width
                                img_width = min(img.width, img.height) < 500
                                width = Inches(3.0) if img_width else Inches(6.0)
                                
                                doc.add_picture(tmp_img.name, width=width)
                                last_paragraph = doc.paragraphs[-1]
                                last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                
                                # Clean up temp file
                                os.unlink(tmp_img.name)
                        except Exception as e:
                            print(f"Warning: Failed to insert image {idx}: {e}")
                    
                    # Add extracted text as editable content
                    if text and text.strip():
                        # Split into paragraphs
                        paragraphs = text.split('\n')
                        for para_text in paragraphs:
                            if para_text.strip():
                                doc.add_paragraph(para_text.strip())
                    else:
                        # No text found - might need OCR
                        doc.add_paragraph(
                            "[Note: No text content detected on this page]",
                        ).italic = True
            
            doc.save(output_path)
            print("✅ Mixed-content conversion completed successfully")
            
        except Exception as e:
            raise ConversionError(f"Mixed content conversion failed: {str(e)}")
    
    @staticmethod
    def convert_scanned_pdf_with_ocr(pdf_path: str, output_path: str) -> None:
        """
        Convert scanned (image-based) PDF using OCR.
        
        For purely scanned documents (no embedded text), we:
        1. Convert each page to high-resolution image
        2. Run OCR to extract text
        3. Create DOCX with extracted text (NOT the image itself)
        
        This ensures the output is editable text, not just images.
        
        Args:
            pdf_path: Input PDF path
            output_path: Output DOCX path
            
        Raises:
            OCRDetectionError: If OCR processing fails
        """
        try:
            print("Converting scanned PDF using OCR...")
            
            # Convert PDF to images
            try:
                images = convert_from_path(pdf_path, dpi=EnhancedPDFService.DPI_FOR_OCR)
            except Exception as e:
                raise OCRDetectionError(f"Failed to convert PDF to images: {str(e)}")
            
            if not images:
                raise InvalidFileError("No pages found in PDF")
            
            doc = Document()
            
            for i, image in enumerate(images):
                print(f"OCR processing page {i+1}/{len(images)}...")
                
                try:
                    # Convert to grayscale for better OCR
                    gray_image = image.convert('L')
                    
                    # Perform OCR
                    text = pytesseract.image_to_string(gray_image, config='--psm 1')
                    
                    # If no text found, try different PSM mode
                    if not text.strip():
                        print(f"  Retrying with alternative OCR settings...")
                        text = pytesseract.image_to_string(gray_image, config='--psm 3')
                    
                    # Add to document
                    if i > 0:
                        doc.add_page_break()
                    
                    if text.strip():
                        # Add extracted text
                        paragraphs = text.strip().split('\n\n')
                        for para in paragraphs:
                            if para.strip():
                                doc.add_paragraph(para.strip())
                    else:
                        # No text extracted
                        p = doc.add_paragraph(
                            f"[Note: Page {i+1} - No text could be extracted. "
                            "The page may be blank or the image quality too low for OCR.]"
                        )
                        p.italic = True
                        
                except Exception as e:
                    print(f"OCR failed for page {i+1}: {e}")
                    # Add error note
                    if i > 0:
                        doc.add_page_break()
                    p = doc.add_paragraph(
                        f"[Error on page {i+1}: OCR processing failed. "
                        f"Details: {str(e)}]"
                    )
                    p.italic = True
            
            doc.save(output_path)
            print("✅ OCR conversion completed successfully")
            
        except (OCRDetectionError, InvalidFileError):
            raise
        except Exception as e:
            raise OCRDetectionError(f"OCR process failed: {str(e)}")
    
    @staticmethod
    def convert_pdf_to_docx(pdf_path: str, output_path: str) -> Tuple[bool, bool]:
        """
        Main intelligent conversion method with automatic detection and fallback.
        
        This is the entry point that:
        1. Analyzes the PDF to understand its content
        2. Chooses the best conversion method
        3. Falls back to alternative methods if primary fails
        4. Returns success status and whether OCR was used
        
        Conversion Strategy:
        - Text-only PDFs (>30% text): Use pdf2docx for best formatting
        - Mixed PDFs (text + images): Use pdfplumber + PyPDF2 for proper separation
        - Scanned PDFs (<10% text): Use OCR for text extraction
        
        Args:
            pdf_path: Input PDF file path
            output_path: Output DOCX file path
            
        Returns:
            Tuple of (success: bool, used_ocr: bool)
            
        Raises:
            PDFConverterException: For various error conditions
        """
        try:
            # Step 1: Validate the PDF file
            EnhancedPDFService.validate_pdf_file(pdf_path)
            
            # Step 2: Analyze PDF content
            print("📊 Analyzing PDF content...")
            analysis = EnhancedPDFService.analyze_pdf(pdf_path)
            
            print(f"Analysis Results:")
            print(f"  - Pages: {analysis.page_count}")
            print(f"  - Text Content: {analysis.text_percentage:.1f}%")
            print(f"  - Has Images: {analysis.has_images}")
            print(f"  - Is Scanned: {analysis.is_scanned}")
            
            # Step 3: Choose conversion strategy based on analysis
            
            if analysis.is_scanned:
                # Scanned PDF - use OCR
                print("🔍 Strategy: Scanned PDF detected → Using OCR")
                EnhancedPDFService.convert_scanned_pdf_with_ocr(pdf_path, output_path)
                return True, True
            
            elif analysis.has_images and analysis.has_text:
                # Mixed content - use pdfplumber for intelligent extraction
                print("🎨 Strategy: Mixed content detected → Using intelligent extraction")
                try:
                    EnhancedPDFService.convert_mixed_content_pdf(pdf_path, output_path)
                    return True, False
                except Exception as e:
                    print(f"Mixed content conversion failed: {e}")
                    print("Falling back to text-based conversion...")
                    EnhancedPDFService.convert_text_based_pdf(pdf_path, output_path)
                    return True, False
            
            else:
                # Text-based PDF - use pdf2docx
                print("📄 Strategy: Text-based PDF → Using pdf2docx")
                try:
                    EnhancedPDFService.convert_text_based_pdf(pdf_path, output_path)
                    return True, False
                except Exception as e:
                    print(f"Text conversion failed: {e}")
                    print("Falling back to OCR...")
                    EnhancedPDFService.convert_scanned_pdf_with_ocr(pdf_path, output_path)
                    return True, True
        
        except PDFConverterException:
            raise
        except Exception as e:
            raise ConversionError(f"Unexpected error during conversion: {str(e)}")
    
    @staticmethod
    def validate_pdf_file(file_path: str) -> bool:
        """
        Comprehensive PDF validation.
        
        Checks:
        1. File exists
        2. File is not empty
        3. Has valid PDF header
        4. Can be opened by PyPDF2
        5. Is not encrypted
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            True if valid
            
        Raises:
            InvalidFileError: If validation fails
            PasswordProtectedError: If PDF is encrypted
        """
        if not os.path.exists(file_path):
            raise InvalidFileError("File does not exist")
        
        try:
            # Check file size
            if os.path.getsize(file_path) == 0:
                raise InvalidFileError("File is empty (0 bytes)")
            
            # Check PDF header
            with open(file_path, 'rb') as f:
                header = f.read(5)
                if header != b'%PDF-':
                    raise InvalidFileError("Invalid PDF header - file may be corrupted")
            
            # Try parsing with PyPDF2
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                if reader.is_encrypted:
                    raise PasswordProtectedError("PDF is password protected")
                
                # Try accessing pages
                page_count = len(reader.pages)
                if page_count == 0:
                    raise InvalidFileError("PDF has no pages")
            
            return True
            
        except (InvalidFileError, PasswordProtectedError):
            raise
        except PyPDF2.errors.PdfReadError:
            raise InvalidFileError("PDF is corrupted or malformed")
        except Exception as e:
            raise InvalidFileError(f"PDF validation failed: {str(e)}")


# Backward compatibility - alias for existing code
PDFService = EnhancedPDFService
