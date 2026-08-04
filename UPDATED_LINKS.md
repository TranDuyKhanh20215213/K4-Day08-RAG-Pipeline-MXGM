# Task 1 & Task 2 - Updated with Correct Links

**Status:** ✅ **Updated with links from Excel files**

---

## Changes Made

### Task 1: Collect Legal Documents
**File:** `src/task1_collect_legal_docs.py`

Updated with 8 correct policy links from `policy.xlsx`:

| # | Title | URL |
|---|-------|-----|
| 1 | CHÍNH SÁCH BẢO MẬT | https://help.shopee.vn/portal/4/article/77244 |
| 2 | ĐIỀU KHOẢN DỊCH VỤ | https://help.shopee.vn/portal/4/article/77243 |
| 3 | QUY CHẾ HOẠT ĐỘNG SÀN THƯƠNG MẠI ĐIỆN TỬ | https://help.shopee.vn/portal/4/article/77245 |
| 4 | QUY ĐỊNH VỀ ĐĂNG BÁN SẢN PHẨM | https://help.shopee.vn/portal/4/article/77246 |
| 5 | CHÍNH SÁCH CẤM/HẠN CHẾ SẢN PHẨM | https://help.shopee.vn/portal/4/article/77247 |
| 6 | CHÍNH SÁCH VẬN CHUYỂN | https://help.shopee.vn/portal/4/article/77250 |
| 7 | CHÍNH SÁCH TRẢ HÀNG VÀ HOÀN TIỀN | https://help.shopee.vn/portal/4/article/77251 |
| 8 | ĐIỀU KHOẢN SỬ DỤNG DỊCH VỤ HIỂN THỊ | https://help.shopee.vn/portal/4/article/77252 |

**Output Files (PDF):**
- `01-privacy-policy-shopee.pdf`
- `02-terms-of-service-shopee.pdf`
- `03-ecommerce-platform-regulations-shopee.pdf`
- `04-product-listing-regulations-shopee.pdf`
- `05-restricted-products-policy-shopee.pdf`
- `06-shipping-policy-shopee.pdf`
- `07-returns-refund-policy-shopee.pdf`
- `08-display-service-terms-shopee.pdf`

**Customer Roles:**
- `buyer` (3): Privacy, Terms, Returns/Refund, Shipping
- `seller` (2): Product Listing, Restricted Products, Display Service
- `both` (3): Terms, Platform Regulations, Shipping

---

### Task 2: Crawl News Articles
**File:** `src/task2_crawl_news.py`

Updated with 5 correct article links from `article.xlsx`:

| # | Title | URL | Topic |
|---|-------|-----|-------|
| 1 | [Trả hàng/ Hoàn tiền] Sản phẩm hạn chế trả hàng | https://help.shopee.vn/portal/4/article/159769 | restricted_returns |
| 2 | [Mua hàng] Cách "Mua ngay" sản phẩm | https://help.shopee.vn/portal/4/article/79615 | quick_purchase |
| 3 | [Thành viên mới] Tính năng quét mã QR | https://help.shopee.vn/portal/4/article/79366 | qr_scanner |
| 4 | [Nạp thẻ và Dịch vụ] E-voucher | https://help.shopee.vn/portal/4/article/79100 | evoucher |
| 5 | Thanh Toán Tối Đa 20 Phân Loại Sản Phẩm | https://help.shopee.vn/portal/4/article/79075 | payment_limit |

**Output Files (JSON):**
- `article_01.json` - Restricted Returns Info
- `article_02.json` - Quick Purchase Guide
- `article_03.json` - QR Scanner Feature
- `article_04.json` - E-voucher Information
- `article_05.json` - Payment Limit Policy

**Customer Roles:**
- All articles: `buyer` (focused on buyer-side operations)

---

## Key Updates

### URL Format Changes
- **From:** `https://help.shopee.vn/portal/article/...`
- **To:** `https://help.shopee.vn/portal/4/article/...`

### File Naming Improvements
- Task 1: Added numeric prefix for ordering (01-, 02-, etc.)
- Task 2: Maintained sequential naming (article_01.json - article_05.json)

### Metadata Accuracy
- All titles now match exactly from Excel files
- All URLs verified from source Excel files
- Customer roles properly categorized

---

## How to Use

### Run Task 1:
```bash
python src/task1_collect_legal_docs.py
```

**Expected Output:**
```
TASK 1: Collecting E-commerce Legal Documents (PDF Format)
====================================================================
[1/8] CHÍNH SÁCH BẢO MẬT
  Crawling content from: https://help.shopee.vn/portal/4/article/77244...
  ✓ Created PDF: data/landing/legal/01-privacy-policy-shopee.pdf
[2/8] ĐIỀU KHOẢN DỊCH VỤ
  ...
✓ Successfully collected 8 documents
✓ Saved metadata to: data/landing/legal/metadata.json
```

### Run Task 2:
```bash
python src/task2_crawl_news.py
```

**Expected Output:**
```
TASK 2: Crawling Customer Support Articles
====================================================================
[1/5] [Trả hàng/ Hoàn tiền] Sản phẩm hạn chế trả hàng là gì?
  Crawling content from: https://help.shopee.vn/portal/4/article/159769...
  ✓ Saved: article_01.json
...
✓ Successfully crawled 5 articles
✓ Saved metadata index to: data/landing/news/metadata.json
```

---

## Files Structure

```
data/landing/
├── legal/
│   ├── 01-privacy-policy-shopee.pdf
│   ├── 02-terms-of-service-shopee.pdf
│   ├── 03-ecommerce-platform-regulations-shopee.pdf
│   ├── 04-product-listing-regulations-shopee.pdf
│   ├── 05-restricted-products-policy-shopee.pdf
│   ├── 06-shipping-policy-shopee.pdf
│   ├── 07-returns-refund-policy-shopee.pdf
│   ├── 08-display-service-terms-shopee.pdf
│   └── metadata.json
├── news/
│   ├── article_01.json
│   ├── article_02.json
│   ├── article_03.json
│   ├── article_04.json
│   ├── article_05.json
│   └── metadata.json
└── standardized/
    ├── legal/        ← Task 3 output
    └── news/         ← Task 3 output
```

---

## Verification

After running both tasks:

```bash
# Check Task 1 output
ls -lh data/landing/legal/*.pdf
cat data/landing/legal/metadata.json

# Check Task 2 output
ls -lh data/landing/news/*.json
cat data/landing/news/metadata.json
```

---

## Next Steps

1. **Task 3:** Convert all PDFs and JSONs to Markdown (already implemented)
2. **Task 4:** Chunking & Indexing (split into chunks, create vector store)
3. **Task 5+:** Semantic Search, Lexical Search, Reranking, etc.

---

## Data Source Attribution

- **Policy URLs:** From `policy.xlsx` (15 policies, using first 8)
- **Article URLs:** From `article.xlsx` (5 customer support articles)
- **Source:** Shopee Vietnam Help Center (help.shopee.vn)

All URLs are from publicly accessible help documentation.

---

**Updated:** 2026-08-04
**Status:** ✅ Ready to Execute
**Next Command:** `python src/task1_collect_legal_docs.py && python src/task2_crawl_news.py`
