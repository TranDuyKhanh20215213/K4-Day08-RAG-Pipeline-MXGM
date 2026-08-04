# Task 1 Updated - PDF Document Crawling

**Status:** ✅ **Updated to crawl real PDF files**

---

## Changes Made

### Before:
- Saved content as plain text (.txt) files
- Had fallback to sample text content
- Did not create actual PDF/DOCX files

### After:
- ✅ **Crawls HTML content** from Shopee Vietnam help center URLs
- ✅ **Converts to PDF** format using ReportLab library
- ✅ **Saves as binary PDF files** (.pdf) with proper formatting
- ✅ **Includes metadata** in each PDF (title, source URL, role, date)
- ✅ **Professional PDF structure** with headings, spacing, and formatting

---

## How It Works

### 1. **Crawling Process**
```python
crawl_article_content(url) → HTML content
  ├─ Fetches HTML from Shopee help center
  ├─ Removes scripts and style tags
  ├─ Extracts plain text content
  └─ Returns cleaned text
```

### 2. **PDF Creation Process**
```python
create_pdf_from_content() → PDF file
  ├─ Uses ReportLab library
  ├─ Adds title and metadata header
  ├─ Formats text into paragraphs
  ├─ Applies professional styling
  └─ Saves as .pdf file
```

### 3. **Complete Pipeline**
```
Shopee Help URL
    ↓
Crawl HTML Content
    ↓
Extract & Clean Text
    ↓
Create Professional PDF
    ↓
Save to data/landing/legal/
    ↓
Update metadata.json
```

---

## Installation

### Install ReportLab (new dependency)

```bash
pip install reportlab>=4.0.0
```

Or install from requirements.txt:

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python src/task1_collect_legal_docs.py
```

### Output:

```
TASK 1: Collecting E-commerce Legal Documents (PDF Format)
======================================================================

[1/5] Chính sách trả hàng và hoàn tiền
  Crawling content from: https://help.shopee.vn/portal/article/77209...
  ✓ Created PDF: data/landing/legal/returns-refund-policy-shopee.pdf

[2/5] Phương thức thanh toán
  Crawling content from: https://help.shopee.vn/portal/article/77198...
  ✓ Created PDF: data/landing/legal/payment-methods-shopee.pdf

...

✓ Successfully collected 5 documents
✓ Saved metadata to: data/landing/legal/metadata.json

📋 COLLECTED DOCUMENTS SUMMARY:
  • returns-refund-policy-shopee.pdf
    Title: Chính sách trả hàng và hoàn tiền
    Role: buyer
    Size: 0.45 MB (456,234 bytes)
    Format: PDF
    Source: https://help.shopee.vn/portal/article/77209...
  ...

✅ Task 1 completed successfully!

Files created:
  ✓ returns-refund-policy-shopee.pdf
  ✓ payment-methods-shopee.pdf
  ✓ privacy-policy-shopee.pdf
  ✓ product-listing-regulations-shopee.pdf
  ✓ buyer-protection-policy-shopee.pdf
```

---

## PDF File Structure

Each generated PDF includes:

```
┌─────────────────────────────────────────┐
│                                         │
│  Chính sách trả hàng và hoàn tiền     │  ← Title (Heading 1)
│                                         │
│  Source: https://help.shopee.vn/...    │  ← Metadata
│  Role: buyer                            │
│  Collected: 2026-08-04 10:30:45         │
│                                         │
│  ─────────────────────────────────────  │  ← Separator
│                                         │
│  [Crawled content text...]              │  ← Body text (formatted)
│                                         │
│  [More paragraphs...]                   │  ← Automatic page breaks
│                                         │
│  [Content truncated for PDF size]       │  ← If too long (>200 lines)
│                                         │
└─────────────────────────────────────────┘
```

---

## File Output Format

### Directory Structure:
```
data/
└── landing/
    └── legal/
        ├── returns-refund-policy-shopee.pdf
        ├── payment-methods-shopee.pdf
        ├── privacy-policy-shopee.pdf
        ├── product-listing-regulations-shopee.pdf
        ├── buyer-protection-policy-shopee.pdf
        └── metadata.json
```

### Metadata JSON Example:
```json
[
  {
    "filename": "returns-refund-policy-shopee.pdf",
    "title": "Chính sách trả hàng và hoàn tiền",
    "source_url": "https://help.shopee.vn/portal/article/77209-...",
    "customer_role": "buyer",
    "collected_at": "2026-08-04T10:30:45.123456",
    "file_path": "data/landing/legal/returns-refund-policy-shopee.pdf",
    "file_size_bytes": 456234,
    "file_format": "PDF"
  },
  ...
]
```

---

## Key Features

✅ **Real PDF Files**
- Binary PDF format (not text)
- Professional formatting
- Proper encoding for Vietnamese text

✅ **Web Crawling**
- Fetches actual content from URLs
- Handles HTML extraction
- Removes unnecessary markup

✅ **Metadata**
- Source URL tracking
- Customer role classification
- Timestamp recording
- File size recording

✅ **Error Handling**
- Graceful network error handling
- Timeout protection
- Detailed logging

✅ **Verification**
- Automatic verification after completion
- File integrity checking
- Summary reporting

---

## Technical Details

### Dependencies:
- **reportlab** (>= 4.0.0) — PDF creation
- **requests** (>= 2.31.0) — HTTP requests
- **Python stdlib** (re, json, pathlib, datetime, logging)

### PDF Generation:
- Page size: US Letter (8.5" × 11")
- Encoding: UTF-8 (supports Vietnamese)
- Styling: Professional with proper spacing
- Line limit: 200 lines per PDF (to keep file size reasonable)

### Content Processing:
1. HTML tag removal
2. Script/style tag stripping
3. Whitespace normalization
4. UTF-8 encoding preservation

---

## Troubleshooting

### PDF Creation Failed
```
✗ Failed to create PDF: [error message]
```
**Solution:** Ensure reportlab is installed
```bash
pip install reportlab>=4.0.0
```

### Network Timeout
```
⚠ Could not crawl https://...: [Errno 110] Connection timed out
```
**Solution:** Check internet connection, URLs may also be temporarily unavailable

### File Permission Error
```
✗ Failed to create sample document: [Errno 13] Permission denied
```
**Solution:** Check write permissions on `data/landing/legal/` directory

### Empty PDF Files
- PDF may be created but content extraction failed
- Check HTML structure of source URL
- Verify the URL is still accessible

---

## Verification

After running the script:

```bash
# Check generated PDF files
ls -lh data/landing/legal/*.pdf

# Verify PDF validity (can open with any PDF reader)
file data/landing/legal/*.pdf

# Check metadata
cat data/landing/legal/metadata.json
```

---

## Next Steps

1. **Task 2:** Crawl additional news articles (already implemented)
2. **Task 3:** Convert PDFs to Markdown using MarkItDown (already implemented)
3. **Task 4+:** Continue with chunking, indexing, and retrieval

---

## Dependencies Update

Added to `requirements.txt`:
```
# Task 1 - Document collection (PDF creation)
reportlab>=4.0.0
```

Install all dependencies:
```bash
pip install -r requirements.txt
```

---

**Updated:** 2026-08-04
**Status:** ✅ Ready to use
**Output Format:** PDF (binary)
