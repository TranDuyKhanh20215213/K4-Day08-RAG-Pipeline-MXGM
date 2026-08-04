"""
Task 3: Convert all files from data/landing/ to Markdown format
Use MarkItDown (Microsoft) for PDF/DOCX conversion
Save to: data/standardized/ preserving directory structure
"""

import json
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime

try:
    from markitdown import MarkItDown
except ImportError:
    raise ImportError(
        "markitdown not installed. Please run:\n"
        "  pip install 'markitdown[pdf]'\n"
        "Note: [pdf] extra is needed for PDF support"
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"

def setup_output_directories():
    """Create output directory structure"""
    legal_dir = OUTPUT_DIR / "legal"
    news_dir = OUTPUT_DIR / "news"

    legal_dir.mkdir(parents=True, exist_ok=True)
    news_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"✓ Created output directory: {OUTPUT_DIR}")
    return legal_dir, news_dir

def convert_legal_docs(output_legal_dir: Path) -> List[Dict]:
    """
    Convert PDF/DOCX files from data/landing/legal/ to Markdown
    Returns: List of converted documents with metadata
    """
    legal_source_dir = LANDING_DIR / "legal"

    if not legal_source_dir.exists():
        logger.warning(f"⚠ Legal documents directory not found: {legal_source_dir}")
        return []

    md = MarkItDown()
    converted_docs = []

    # Get all document files (PDF, DOCX, TXT, JSON)
    doc_files = (
        list(legal_source_dir.glob("*.pdf")) +
        list(legal_source_dir.glob("*.docx")) +
        list(legal_source_dir.glob("*.doc")) +
        list(legal_source_dir.glob("*.txt"))
    )

    # Exclude metadata.json
    doc_files = [f for f in doc_files if f.name != "metadata.json"]

    logger.info(f"\nConverting {len(doc_files)} legal documents...")

    for idx, filepath in enumerate(doc_files, 1):
        try:
            logger.info(f"[{idx}/{len(doc_files)}] Converting: {filepath.name}")

            # Convert file
            result = md.convert(str(filepath))
            content = result.text_content if hasattr(result, 'text_content') else str(result)

            # Create output markdown file
            output_path = output_legal_dir / f"{filepath.stem}.md"

            # Prepend metadata header
            metadata_header = f"""---
title: {filepath.stem}
source_file: {filepath.name}
converted_at: {datetime.now().isoformat()}
---

"""
            full_content = metadata_header + content

            # Write to file
            output_path.write_text(full_content, encoding="utf-8")
            logger.info(f"  ✓ Saved: {output_path}")

            doc_record = {
                "source_filename": filepath.name,
                "output_filename": output_path.name,
                "source_path": str(filepath),
                "output_path": str(output_path),
                "content_length": len(content),
                "converted_at": datetime.now().isoformat()
            }
            converted_docs.append(doc_record)

        except Exception as e:
            logger.error(f"  ✗ Failed to convert {filepath.name}: {e}")

    return converted_docs

def convert_news_articles(output_news_dir: Path) -> List[Dict]:
    """
    Convert JSON news articles from data/landing/news/ to Markdown
    Returns: List of converted articles with metadata
    """
    news_source_dir = LANDING_DIR / "news"

    if not news_source_dir.exists():
        logger.warning(f"⚠ News articles directory not found: {news_source_dir}")
        return []

    json_files = [f for f in news_source_dir.glob("*.json") if f.name != "metadata.json"]

    logger.info(f"\nConverting {len(json_files)} news articles...")

    converted_articles = []

    for idx, filepath in enumerate(json_files, 1):
        try:
            logger.info(f"[{idx}/{len(json_files)}] Converting: {filepath.name}")

            # Read JSON
            data = json.loads(filepath.read_text(encoding="utf-8"))

            # Create markdown content
            title = data.get("title", "Unknown")
            url = data.get("url", "N/A")
            date_crawled = data.get("date_crawled", "N/A")
            topic = data.get("topic", "N/A")
            customer_role = data.get("customer_role", "N/A")
            content = data.get("content", "")

            markdown_content = f"""---
title: {title}
url: {url}
topic: {topic}
customer_role: {customer_role}
date_crawled: {date_crawled}
---

# {title}

**Source:** [{url}]({url})
**Topic:** {topic}
**Target Audience:** {customer_role}
**Crawled:** {date_crawled}

---

## Content

{content}
"""

            # Save to markdown file
            output_path = output_news_dir / f"{filepath.stem}.md"
            output_path.write_text(markdown_content, encoding="utf-8")
            logger.info(f"  ✓ Saved: {output_path}")

            article_record = {
                "source_filename": filepath.name,
                "output_filename": output_path.name,
                "title": title,
                "topic": topic,
                "customer_role": customer_role,
                "source_path": str(filepath),
                "output_path": str(output_path),
                "content_length": len(content),
                "converted_at": datetime.now().isoformat()
            }
            converted_articles.append(article_record)

        except Exception as e:
            logger.error(f"  ✗ Failed to convert {filepath.name}: {e}")

    return converted_articles

def save_conversion_manifest(
    legal_docs: List[Dict],
    news_articles: List[Dict]
) -> None:
    """Save conversion manifest to metadata file"""
    manifest = {
        "conversion_timestamp": datetime.now().isoformat(),
        "source_directory": str(LANDING_DIR),
        "output_directory": str(OUTPUT_DIR),
        "legal_documents": {
            "total_converted": len(legal_docs),
            "documents": legal_docs
        },
        "news_articles": {
            "total_converted": len(news_articles),
            "articles": news_articles
        }
    }

    manifest_file = OUTPUT_DIR / "CONVERSION_MANIFEST.json"
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    logger.info(f"✓ Conversion manifest saved: {manifest_file}")

def convert_all() -> bool:
    """
    Main function to convert all files
    Returns: True if successful, False otherwise
    """
    logger.info("=" * 60)
    logger.info("TASK 3: Converting Files to Markdown (MarkItDown)")
    logger.info("=" * 60)

    try:
        # Setup output directories
        legal_output, news_output = setup_output_directories()

        # Convert legal documents
        logger.info("\n--- Converting Legal Documents ---")
        legal_docs = convert_legal_docs(legal_output)

        # Convert news articles
        logger.info("\n--- Converting News Articles ---")
        news_articles = convert_news_articles(news_output)

        # Save manifest
        save_conversion_manifest(legal_docs, news_articles)

        # Print summary
        logger.info(f"\n{'=' * 60}")
        logger.info("CONVERSION SUMMARY")
        logger.info(f"{'=' * 60}")
        print(f"\n📄 CONVERTED FILES:")
        print(f"  Legal Documents: {len(legal_docs)}")
        print(f"  News Articles: {len(news_articles)}")
        print(f"  Total: {len(legal_docs) + len(news_articles)}")
        print(f"\nOutput directory: {OUTPUT_DIR}\n")

        return True

    except Exception as e:
        logger.error(f"✗ Conversion failed: {e}")
        return False

def verify_conversion() -> bool:
    """Verify that all files were converted"""
    legal_dir = OUTPUT_DIR / "legal"
    news_dir = OUTPUT_DIR / "news"

    legal_files = list(legal_dir.glob("*.md")) if legal_dir.exists() else []
    news_files = list(news_dir.glob("*.md")) if news_dir.exists() else []

    total_files = len(legal_files) + len(news_files)

    if total_files == 0:
        logger.error("✗ No markdown files found in output directory")
        return False

    logger.info(f"✓ Verification passed: {total_files} markdown files found")
    return True

if __name__ == "__main__":
    # Run conversion
    success = convert_all()

    # Verify
    if success and verify_conversion():
        print("✅ Task 3 completed successfully!")
    else:
        print("❌ Task 3 verification failed!")
