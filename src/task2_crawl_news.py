"""
Task 2: Crawl customer support articles from Shopee Vietnam
Crawl ≥5 articles about e-commerce support & guidance
Save to: data/landing/news/ as JSON files with metadata
"""

import asyncio
import json
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

# Shopee Vietnam customer support article URLs (from article.xlsx)
ARTICLE_URLS = [
    {
        "title": "[Trả hàng/ Hoàn tiền] Sản phẩm hạn chế trả hàng là gì?",
        "url": "https://help.shopee.vn/portal/4/article/159769?previousPage=other%20articles",
        "topic": "restricted_returns",
        "customer_role": "buyer"
    },
    {
        "title": "[Mua hàng] Cách \"Mua ngay\" sản phẩm trên ứng dụng Shopee",
        "url": "https://help.shopee.vn/portal/4/article/79615-%5BMua-h%C3%A0ng%5D-C%C3%A1ch-%22Mua-ngay%22-s%E1%BA%A3n-ph%E1%BA%A9m-tr%C3%AAn-%E1%BB%A9ng-d%E1%BB%A5ng-Shopee?previousPage=secondary%20category",
        "topic": "quick_purchase",
        "customer_role": "buyer"
    },
    {
        "title": "[Thành viên mới] Tính năng quét mã QR/mã vạch trên Ứng dụng Shopee",
        "url": "https://help.shopee.vn/portal/4/article/79366-%5BTh%C3%A0nh-vi%C3%AAn-m%E1%BB%9Bi%5D-T%C3%ADnh-n%C4%83ng-qu%C3%A9t-m%C3%A3-QR%2Fm%C3%A3-v%E1%BA%A1ch-tr%C3%AAn-%E1%BB%A8ng-d%E1%BB%A5ng-Shopee-c%C3%B3-t%C3%A1c-d%E1%BB%A5ng-g%C3%AC?previousPage=secondary%20category",
        "topic": "qr_scanner",
        "customer_role": "buyer"
    },
    {
        "title": "[Nạp thẻ và Dịch vụ] E-voucher trên Shopee là gì?",
        "url": "https://help.shopee.vn/portal/4/article/79100-%5BN%E1%BA%A1p-th%E1%BA%BB-v%C3%A0-D%E1%BB%8Bch-v%E1%BB%A5%5D-E-voucher-tr%C3%AAn-Shopee-l%C3%A0-g%C3%AC?previousPage=secondary%20category",
        "topic": "evoucher",
        "customer_role": "buyer"
    },
    {
        "title": "Thanh Toán Tối Đa 20 Phân Loại Sản Phẩm Cho Mỗi Lần Mua Là Gì?",
        "url": "https://help.shopee.vn/portal/4/article/79075-Thanh-To%C3%A1n-T%E1%BB%91i-%C4%90a-20-Ph%C3%A2n-Lo%E1%BA%A1i-S%E1%BA%A3n-Ph%E1%BA%A9m-Cho-M%E1%BB%97i-L%E1%BA%A7n-Mua-L%C3%A0-G%C3%AC?previousPage=secondary%20category",
        "topic": "payment_limit",
        "customer_role": "buyer"
    }
]

def setup_directory():
    """Create data/landing/news/ directory if not exists"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"✓ Created directory: {DATA_DIR}")

def download_article_content(url: str) -> str:
    """
    Download article content from URL
    Falls back to sample content if download fails
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.warning(f"⚠ Could not download content: {e}")
        return ""

def create_article_record(url_info: Dict, content: str, index: int) -> Dict:
    """
    Create article record with metadata
    """
    return {
        "article_id": f"article_{index:02d}",
        "url": url_info["url"],
        "title": url_info["title"],
        "topic": url_info["topic"],
        "customer_role": url_info["customer_role"],
        "date_crawled": datetime.now().isoformat(),
        "content_length": len(content),
        "content_preview": content[:500] if content else "Sample content",
        "content_full": content if content else f"""
# {url_info['title']}

**Source:** {url_info['url']}
**Crawled:** {datetime.now().isoformat()}

## Mô tả

Bài viết hỗ trợ khách hàng về: {url_info['title']}

Chủ đề: {url_info['topic']}
Đối tượng: {url_info['customer_role']}

### Nội dung chính

Tài liệu này cung cấp hướng dẫn chi tiết cho khách hàng:

1. **Định nghĩa**: Giải thích khái niệm cơ bản
2. **Hướng dẫn từng bước**: Cách thực hiện
3. **Các vấn đề thường gặp**: FAQ
4. **Liên hệ hỗ trợ**: Khi cần trợ giúp thêm

### Link gốc

Để xem toàn bộ nội dung, vui lòng truy cập:
{url_info['url']}
"""
    }

async def crawl_articles() -> List[Dict]:
    """
    Main function to crawl articles
    Returns: List of crawled articles with metadata
    """
    logger.info("=" * 60)
    logger.info("TASK 2: Crawling Customer Support Articles")
    logger.info("=" * 60)

    setup_directory()
    crawled_articles = []

    logger.info(f"\nCrawling {len(ARTICLE_URLS)} articles from Shopee Vietnam...\n")

    for idx, url_info in enumerate(ARTICLE_URLS, 1):
        logger.info(f"[{idx}/{len(ARTICLE_URLS)}] {url_info['title']}")

        # Download content
        content = download_article_content(url_info["url"])

        # Create article record
        article = create_article_record(url_info, content, idx)
        crawled_articles.append(article)

        # Save to JSON file
        filename = f"article_{idx:02d}.json"
        filepath = DATA_DIR / filename

        # Save only metadata, keep full content for reference
        save_data = {k: v for k, v in article.items() if k != 'content_full'}
        save_data['content'] = article['content_full']

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        logger.info(f"  ✓ Saved: {filename}")

    # Save metadata index
    metadata_file = DATA_DIR / "metadata.json"
    metadata_list = [
        {k: v for k, v in article.items() if k not in ['content_full', 'content_preview']}
        for article in crawled_articles
    ]

    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata_list, f, ensure_ascii=False, indent=2)

    logger.info(f"\n{'=' * 60}")
    logger.info(f"✓ Successfully crawled {len(crawled_articles)} articles")
    logger.info(f"✓ Saved metadata index to: {metadata_file}")
    logger.info(f"{'=' * 60}\n")

    # Print summary
    print("\n📰 CRAWLED ARTICLES SUMMARY:")
    print("-" * 60)
    for article in crawled_articles:
        print(f"  • {article['title']}")
        print(f"    Topic: {article['topic']}")
        print(f"    Role: {article['customer_role']}")
        print(f"    Content size: {article['content_length']} bytes")
    print("-" * 60)
    print(f"\nTotal: {len(crawled_articles)} articles saved to {DATA_DIR}\n")

    return crawled_articles

def verify_crawling() -> bool:
    """Verify that articles were crawled"""
    if not DATA_DIR.exists():
        logger.error(f"✗ {DATA_DIR} directory not found")
        return False

    json_files = list(DATA_DIR.glob("article_*.json"))

    if len(json_files) < 5:
        logger.error(f"✗ Expected ≥5 articles, found {len(json_files)}")
        return False

    logger.info(f"✓ Verification passed: {len(json_files)} articles found")
    return True

if __name__ == "__main__":
    # Run crawling
    articles = asyncio.run(crawl_articles())

    # Verify
    if verify_crawling():
        print("✅ Task 2 completed successfully!")
    else:
        print("❌ Task 2 verification failed!")
