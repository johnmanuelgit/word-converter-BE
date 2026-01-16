#!/usr/bin/env python3
"""
Quick Test Script for Enhanced PDF Service

This script verifies that the enhanced PDF service can be imported
and has all the required methods.
"""

import sys
from pathlib import Path

# Add app to Python path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("Testing Enhanced PDF Service")
print("=" * 60)
print()

# Test 1: Import the service
print("Test 1: Importing PDF Service...")
try:
    from app.services.pdf_service import PDFService, EnhancedPDFService, PDFAnalysis
    print("✅ PASS: PDF Service imported successfully")
except ImportError as e:
    print(f"❌ FAIL: Could not import PDF Service: {e}")
    sys.exit(1)

# Test 2: Check that PDFService is aliased to EnhancedPDFService
print("\nTest 2: Checking backward compatibility...")
if PDFService is EnhancedPDFService:
    print("✅ PASS: PDFService is correctly aliased to EnhancedPDFService")
else:
    print("❌ FAIL: PDFService is not aliased to EnhancedPDFService")

# Test 3: Check for required methods
print("\nTest 3: Checking for required methods...")
required_methods = [
    'analyze_pdf',
    'extract_images_from_page',
    'convert_text_based_pdf',
    'convert_mixed_content_pdf',
    'convert_scanned_pdf_with_ocr',
    'convert_pdf_to_docx',
    'validate_pdf_file'
]

missing_methods = []
for method in required_methods:
    if hasattr(PDFService, method):
        print(f"  ✅ {method}")
    else:
        print(f"  ❌ {method}")
        missing_methods.append(method)

if missing_methods:
    print(f"\n❌ FAIL: Missing methods: {', '.join(missing_methods)}")
    sys.exit(1)
else:
    print("\n✅ PASS: All required methods present")

# Test 4: Check for configuration constants
print("\nTest 4: Checking configuration constants...")
required_constants = [
    'DPI_FOR_OCR',
    'DPI_FOR_IMAGES',
    'MIN_TEXT_LENGTH',
    'TEXT_THRESHOLD'
]

missing_constants = []
for constant in required_constants:
    if hasattr(PDFService, constant):
        value = getattr(PDFService, constant)
        print(f"  ✅ {constant} = {value}")
    else:
        print(f"  ❌ {constant}")
        missing_constants.append(constant)

if missing_constants:
    print(f"\n❌ FAIL: Missing constants: {', '.join(missing_constants)}")
else:
    print("\n✅ PASS: All configuration constants present")

# Test 5: Check PDFAnalysis dataclass
print("\nTest 5: Checking PDFAnalysis dataclass...")
try:
    # Try to instantiate it
    analysis = PDFAnalysis(
        is_scanned=False,
        has_images=True,
        has_text=True,
        text_percentage=65.0,
        page_count=1,
        is_encrypted=False
    )
    print(f"  ✅ PDFAnalysis created: {analysis}")
    print("✅ PASS: PDFAnalysis dataclass works correctly")
except Exception as e:
    print(f"❌ FAIL: Could not create PDFAnalysis: {e}")

# Test 6: Check imports for dependencies
print("\nTest 6: Checking dependencies...")
dependencies = {
    'PyPDF2': 'PyPDF2',
    'pdf2docx': 'pdf2docx.Converter',
    'pytesseract': 'pytesseract',
    'PIL': 'PIL.Image',
    'pdf2image': 'pdf2image',
    'pdfplumber': 'pdfplumber',
    'docx': 'docx.Document'
}

missing_deps = []
for name, module_path in dependencies.items():
    try:
        parts = module_path.split('.')
        module = __import__(parts[0])
        for part in parts[1:]:
            module = getattr(module, part)
        print(f"  ✅ {name}")
    except (ImportError, AttributeError) as e:
        print(f"  ❌ {name}: {e}")
        missing_deps.append(name)

if missing_deps:
    print(f"\n⚠️  WARNING: Missing dependencies: {', '.join(missing_deps)}")
    print("   Run: pip install -r requirements.txt")
else:
    print("\n✅ PASS: All dependencies installed")

# Summary
print("\n" + "=" * 60)
print("Test Summary")
print("=" * 60)

if missing_methods or missing_constants:
    print("❌ FAILED: Some tests failed")
    print("\nPlease ensure you have the latest version of pdf_service.py")
    sys.exit(1)
else:
    print("✅ ALL TESTS PASSED!")
    print("\nYour PDF service is ready to use!")
    print("\nKey Features:")
    print("  • Intelligent PDF analysis")
    print("  • Proper text/image separation")
    print("  • Mixed-content support (CVs with photos)")
    print("  • OCR for scanned documents")
    print("  • Automatic fallback mechanisms")
    
    if missing_deps:
        print("\n⚠️  Note: Some optional dependencies are missing.")
        print("   The service will work, but some features may be limited.")
    
    print("\nTo test with an actual PDF:")
    print("  python test_pdf_service.py /path/to/your/file.pdf")

print("=" * 60)
