"""
Task 4 — Chunking & Indexing vào Vector Store.

Lựa chọn cho bài này:
    - Chunking: SemanticChunker (langchain_experimental) — tách đoạn dựa trên
      độ tương đồng embedding giữa các câu liền kề, thay vì cắt cứng theo số
      ký tự. Phù hợp với văn bản chính sách/pháp lý vì giữ trọn vẹn từng
      điều khoản/ý nghĩa thay vì cắt giữa câu.
    - Embedding: OpenAI text-embedding-3-small (1536 dim) — dùng chung 1 model
      cho cả bước chunking (SemanticChunker cần embedding để đo similarity)
      và bước embed_chunks/semantic_search, tránh lệch không gian vector.
    - Vector Store: ChromaDB, persistent local tại chroma_db/.

CHUNK_SIZE / CHUNK_OVERLAP ở đây KHÔNG điều khiển SemanticChunker trực tiếp
(SemanticChunker tự quyết định điểm cắt theo ngữ nghĩa, không theo độ dài cố
định). Hai giá trị này đóng vai trò "safety net": nếu 1 semantic chunk vượt
quá CHUNK_SIZE (đoạn văn quá dài không có breakpoint ngữ nghĩa rõ ràng), nó
sẽ được cắt tiếp bằng RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE,
chunk_overlap=CHUNK_OVERLAP) để đảm bảo không có chunk nào quá lớn so với
context window của embedding/LLM.

Cài đặt:
    pip install langchain-text-splitters langchain-experimental langchain-openai chromadb openai python-dotenv

Lưu ý quan trọng: nếu sau này đổi corpus (đổi chủ đề, thêm/bớt tài liệu), phải XÓA
chroma_db/ cũ trước khi reindex — nếu không, chunk cũ và mới sẽ tồn tại lẫn lộn
trong cùng collection, retrieval sẽ trả về kết quả rác từ dữ liệu cũ.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"


# =============================================================================
# CONFIGURATION
# =============================================================================

CHUNKING_METHOD = "semantic"  # "recursive" | "markdown_header" | "semantic"

# Safety-net cho SemanticChunker (xem giải thích ở docstring đầu file).
CHUNK_SIZE = 800        # Ngưỡng tối đa (ký tự) trước khi fallback-split 1 semantic chunk quá dài
CHUNK_OVERLAP = 100     # Overlap dùng khi fallback-split, giữ ngữ cảnh giữa các mảnh bị cắt cứng

# SemanticChunker breakpoint config
BREAKPOINT_THRESHOLD_TYPE = "percentile"  # "percentile" | "standard_deviation" | "interquartile"
BREAKPOINT_THRESHOLD_AMOUNT = 95          # Càng cao → càng ít breakpoint → chunk càng to

EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI — 1536 dim, chất lượng tốt, chi phí thấp
EMBEDDING_DIM = 1536

VECTOR_STORE = "chromadb"  # "chromadb" | "weaviate" | "faiss"
COLLECTION_NAME = "ecommerce_support_docs"


# =============================================================================
# SHARED HELPERS (dùng lại ở Task 5)
# =============================================================================

_embeddings_instance = None
_chroma_client = None
_chroma_collection = None


def get_embedding_model():
    """
    Trả về instance OpenAIEmbeddings dùng chung cho chunking (SemanticChunker),
    embed_chunks(), và semantic_search() ở Task 5 — đảm bảo cùng 1 không gian
    vector.
    """
    global _embeddings_instance
    if _embeddings_instance is None:
        from langchain_openai import OpenAIEmbeddings

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Thiếu OPENAI_API_KEY trong .env — cần key OpenAI thật để dùng "
                "text-embedding-3-small (OpenRouter không phục vụ embeddings)."
            )
        _embeddings_instance = OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=api_key)
    return _embeddings_instance


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        import chromadb

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _chroma_client


def get_collection():
    """Lấy (hoặc tạo) collection ChromaDB, dùng cosine similarity."""
    global _chroma_collection
    if _chroma_collection is None:
        client = get_chroma_client()
        _chroma_collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _chroma_collection


# =============================================================================
# IMPLEMENTATION
# =============================================================================

def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown files từ data/standardized/.

    Returns:
        List of {'content': str, 'metadata': {'source': str, 'type': str}}
    """
    documents = []
    if not STANDARDIZED_DIR.exists():
        return documents

    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8").strip()
        if not content:
            continue
        doc_type = "legal" if "legal" in md_file.parts else (
            "news" if "news" in md_file.parts else "other"
        )
        documents.append({
            "content": content,
            "metadata": {"source": md_file.name, "type": doc_type},
        })
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents bằng SemanticChunker (ngữ nghĩa), với fallback cắt cứng
    (RecursiveCharacterTextSplitter) cho các đoạn vượt quá CHUNK_SIZE.

    Returns:
        List of {'content': str, 'metadata': dict} — mỗi item là 1 chunk
    """
    from langchain_experimental.text_splitter import SemanticChunker
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    embeddings = get_embedding_model()
    semantic_splitter = SemanticChunker(
        embeddings,
        breakpoint_threshold_type=BREAKPOINT_THRESHOLD_TYPE,
        breakpoint_threshold_amount=BREAKPOINT_THRESHOLD_AMOUNT,
    )
    fallback_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = []
    for doc in documents:
        raw_splits = semantic_splitter.split_text(doc["content"])

        final_splits = []
        for piece in raw_splits:
            if len(piece) > CHUNK_SIZE:
                final_splits.extend(fallback_splitter.split_text(piece))
            else:
                final_splits.append(piece)

        for i, chunk_text in enumerate(final_splits):
            chunks.append({
                "content": chunk_text,
                "metadata": {**doc["metadata"], "chunk_index": i},
            })
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toàn bộ chunks bằng text-embedding-3-small (batch qua OpenAIEmbeddings).

    Returns:
        Mỗi chunk dict được thêm key 'embedding': list[float]
    """
    embeddings = get_embedding_model()
    texts = [c["content"] for c in chunks]

    vectors = embeddings.embed_documents(texts)
    for chunk, vec in zip(chunks, vectors):
        chunk["embedding"] = vec
    return chunks


def index_to_vectorstore(chunks: list[dict]):
    """Upsert toàn bộ chunks (content + embedding + metadata) vào ChromaDB."""
    collection = get_collection()

    ids = [
        f"{c['metadata']['source']}_chunk_{c['metadata']['chunk_index']}"
        for c in chunks
    ]
    collection.upsert(
        ids=ids,
        documents=[c["content"] for c in chunks],
        embeddings=[c["embedding"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (safety-net size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE} -> {CHROMA_DIR}")
    print("=" * 50)

    docs = load_documents()
    print(f"\n✓ Loaded {len(docs)} documents")
    if not docs:
        print("⚠ Không có document nào trong data/standardized/ — chạy Task 1-3 trước.")
        return

    chunks = chunk_documents(docs)
    print(f"✓ Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"✓ Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print(f"✓ Indexed {len(chunks)} chunks vào collection '{COLLECTION_NAME}'")


if __name__ == "__main__":
    run_pipeline()
