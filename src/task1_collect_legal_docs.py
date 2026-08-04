"""
Task 1: Thu thập văn bản chính sách thương mại điện tử từ Shopee Vietnam
Collect ≥3 legal documents (PDF/DOCX) about e-commerce policies
Download as actual PDF/DOCX files (not text)
Save to: data/landing/legal/
"""

import os
import json
import requests
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import logging

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.units import inch
except ImportError:
    raise ImportError("reportlab not installed. Please run: pip install reportlab")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Shopee Vietnam help center URLs (from policy.xlsx)
SHOPEE_HELP_URLS = [
    {
        "title": "CHÍNH SÁCH BẢO MẬT",
        "url": "https://help.shopee.vn/portal/4/article/77244?previousPage=other+articles",
        "filename": "01-privacy-policy-shopee.pdf",
        "customer_role": "both"
    },
    {
        "title": "ĐIỀU KHOẢN DỊCH VỤ",
        "url": "https://help.shopee.vn/portal/4/article/77243?previousPage=other+articles",
        "filename": "02-terms-of-service-shopee.pdf",
        "customer_role": "both"
    },
    {
        "title": "QUY CHẾ HOẠT ĐỘNG SÀN THƯƠNG MẠI ĐIỆN TỬ SHOPEE.VN",
        "url": "https://help.shopee.vn/portal/4/article/77245?previousPage=other+articles",
        "filename": "03-ecommerce-platform-regulations-shopee.pdf",
        "customer_role": "both"
    },
    {
        "title": "QUY ĐỊNH VỀ ĐĂNG BÁN SẢN PHẨM TRÊN SHOPEE",
        "url": "https://help.shopee.vn/portal/4/article/77246?previousPage=other+articles",
        "filename": "04-product-listing-regulations-shopee.pdf",
        "customer_role": "seller"
    },
    {
        "title": "CHÍNH SÁCH CẤM/HẠN CHẾ SẢN PHẨM",
        "url": "https://help.shopee.vn/portal/4/article/77247?previousPage=other+articles",
        "filename": "05-restricted-products-policy-shopee.pdf",
        "customer_role": "seller"
    },
    {
        "title": "CHÍNH SÁCH VẬN CHUYỂN SHOPEE",
        "url": "https://help.shopee.vn/portal/4/article/77250?previousPage=other+articles",
        "filename": "06-shipping-policy-shopee.pdf",
        "customer_role": "both"
    },
    {
        "title": "CHÍNH SÁCH TRẢ HÀNG VÀ HOÀN TIỀN",
        "url": "https://help.shopee.vn/portal/4/article/77251?previousPage=other+articles",
        "filename": "07-returns-refund-policy-shopee.pdf",
        "customer_role": "buyer"
    },
    {
        "title": "ĐIỀU KHOẢN SỬ DỤNG DỊCH VỤ HIỂN THỊ",
        "url": "https://help.shopee.vn/portal/4/article/77252?previousPage=other+articles",
        "filename": "08-display-service-terms-shopee.pdf",
        "customer_role": "seller"
    }
]

def create_directory_structure():
    """Create necessary directory structure"""
    landing_dir = Path("data/landing/legal")
    landing_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"✓ Created directory: {landing_dir}")
    return landing_dir

def crawl_article_content(url: str) -> str:
    """
    Crawl HTML content from URL and extract text
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Simple HTML content extraction
        html_content = response.text

        # Remove HTML tags and extract text (basic approach)
        import re
        # Remove script and style tags
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
        # Remove other HTML tags
        html_content = re.sub(r'<[^>]+>', '\n', html_content)
        # Clean up whitespace
        lines = [line.strip() for line in html_content.split('\n') if line.strip()]
        text_content = '\n'.join(lines)

        return text_content

    except Exception as e:
        logger.warning(f"⚠ Could not crawl {url}: {e}")
        return ""

def create_pdf_from_content(title: str, url: str, content: str, filepath: Path, customer_role: str) -> bool:
    """
    Create PDF file from crawled content using ReportLab
    """
    try:
        doc = SimpleDocTemplate(str(filepath), pagesize=letter)
        story = []
        styles = getSampleStyleSheet()

        # Title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor='#1f2937',
            spaceAfter=12,
            alignment=1  # center
        )

        # Heading style
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor='#374151',
            spaceAfter=6,
            spaceBefore=6
        )

        # Body style
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=10,
            leading=14
        )

        # Add title
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.2*inch))

        # Add metadata
        story.append(Paragraph(f"<b>Source:</b> {url}", body_style))
        story.append(Paragraph(f"<b>Role:</b> {customer_role}", body_style))
        story.append(Paragraph(f"<b>Collected:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body_style))
        story.append(Spacer(1, 0.3*inch))

        # Add separator
        story.append(Paragraph("─" * 80, body_style))
        story.append(Spacer(1, 0.2*inch))

        # Add content
        if content:
            # Split content into paragraphs
            paragraphs = content.split('\n')
            for para in paragraphs[:200]:  # Limit to first 200 lines to avoid huge PDFs
                if para.strip():
                    # Skip very long lines
                    if len(para) > 500:
                        para = para[:500] + "..."
                    story.append(Paragraph(para, body_style))

            if len(paragraphs) > 200:
                story.append(Spacer(1, 0.2*inch))
                story.append(Paragraph("<i>[Content truncated for PDF size]</i>", body_style))
        else:
            story.append(Paragraph("<i>No content available</i>", body_style))

        # Build PDF
        doc.build(story)
        logger.info(f"✓ Created PDF: {filepath}")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to create PDF: {e}")
        return False

def download_document(url: str, filename: str, landing_dir: Path, title: str, customer_role: str) -> bool:
    """
    Download document by crawling HTML content and converting to PDF
    """
    filepath = landing_dir / filename

    logger.info(f"  Crawling content from: {url}")
    content = crawl_article_content(url)

    if content:
        # Create PDF from crawled content
        success = create_pdf_from_content(title, url, content, filepath, customer_role)
        return success
    else:
        logger.warning(f"⚠ Could not crawl content for: {filename}")
        return False

def collect_legal_documents() -> List[Dict]:
    """
    Main function to collect legal documents
    Returns: List of collected documents with metadata
    """
    logger.info("=" * 70)
    logger.info("TASK 1: Collecting E-commerce Legal Documents (PDF Format)")
    logger.info("=" * 70)

    landing_dir = create_directory_structure()
    collected_docs = []

    logger.info(f"\nDownloading & Converting {len(SHOPEE_HELP_URLS)} legal documents to PDF...\n")

    for idx, doc_info in enumerate(SHOPEE_HELP_URLS, 1):
        logger.info(f"[{idx}/{len(SHOPEE_HELP_URLS)}] {doc_info['title']}")

        success = download_document(
            url=doc_info['url'],
            filename=doc_info['filename'],
            landing_dir=landing_dir,
            title=doc_info['title'],
            customer_role=doc_info['customer_role']
        )

        if success:
            filepath = landing_dir / doc_info['filename']
            file_size = filepath.stat().st_size

            doc_record = {
                "filename": doc_info['filename'],
                "title": doc_info['title'],
                "source_url": doc_info['url'],
                "customer_role": doc_info['customer_role'],
                "collected_at": datetime.now().isoformat(),
                "file_path": str(filepath),
                "file_size_bytes": file_size,
                "file_format": "PDF"
            }
            collected_docs.append(doc_record)

    # Save metadata
    metadata_file = landing_dir / "metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(collected_docs, f, ensure_ascii=False, indent=2)

    logger.info(f"\n{'=' * 70}")
    logger.info(f"✓ Successfully collected {len(collected_docs)} documents")
    logger.info(f"✓ Saved metadata to: {metadata_file}")
    logger.info(f"{'=' * 70}\n")

    # Print summary
    print("\n📋 COLLECTED DOCUMENTS SUMMARY:")
    print("-" * 70)
    for doc in collected_docs:
        size_mb = doc['file_size_bytes'] / (1024 * 1024)
        print(f"  • {doc['filename']}")
        print(f"    Title: {doc['title']}")
        print(f"    Role: {doc['customer_role']}")
        print(f"    Size: {size_mb:.2f} MB ({doc['file_size_bytes']} bytes)")
        print(f"    Format: {doc['file_format']}")
        print(f"    Source: {doc['source_url']}")
    print("-" * 70)
    print(f"\nTotal: {len(collected_docs)} documents saved to {landing_dir}\n")

    return collected_docs

def verify_collection() -> bool:
    """Verify that legal documents were collected"""
    landing_dir = Path("data/landing/legal")

    if not landing_dir.exists():
        logger.error("✗ data/landing/legal directory not found")
        return False

    files = list(landing_dir.glob("*.pdf")) + list(landing_dir.glob("*.docx"))

    if len(files) < 3:
        logger.error(f"✗ Expected ≥3 documents, found {len(files)}")
        return False

    logger.info(f"✓ Verification passed: {len(files)} PDF/DOCX files found")
    for f in files:
        logger.info(f"  - {f.name} ({f.stat().st_size} bytes)")
    return True

if __name__ == "__main__":
    # Run collection
    docs = collect_legal_documents()

    # Verify
    if verify_collection():
        print("✅ Task 1 completed successfully!")
        print("\nFiles created:")
        landing_dir = Path("data/landing/legal")
        for f in sorted(landing_dir.glob("*.pdf")):
            print(f"  ✓ {f.name}")
    else:
        print("❌ Task 1 verification failed!")
