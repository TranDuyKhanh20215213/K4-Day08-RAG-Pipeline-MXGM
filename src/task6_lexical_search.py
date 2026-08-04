"""
Task 6 — Lexical Search Module (BM25).

Sử dụng BM25 (rank-bm25) trên cùng corpus (chunks) đã được index ở Task 4.
Corpus được lấy trực tiếp từ ChromaDB collection (`get_collection().get(...)`)
thay vì re-chunk lại từ markdown — đảm bảo lexical search và semantic search
(Task 5) truy vấn trên đúng cùng 1 tập chunk, để Task 9 (hybrid fusion) hợp lý.

Cài đặt:
    pip install rank-bm25

BM25 hoạt động thế nào:
    - Term Frequency (TF): từ xuất hiện nhiều trong document → điểm cao
    - Inverse Document Frequency (IDF): từ hiếm → quan trọng hơn
    - Document length normalization: document dài không bị ưu tiên quá mức
    - Formula: score(q,d) = Σ IDF(qi) * (tf(qi,d) * (k1+1)) / (tf(qi,d) + k1*(1-b+b*|d|/avgdl))
    - k1=1.5 (term saturation, mặc định rank_bm25), b=0.75 (length normalization)
"""

import re

from src.task4_chunking_indexing import get_collection

# Cache module-level: tránh rebuild BM25 index mỗi lần gọi lexical_search()
_bm25_index = None
_bm25_corpus: list[dict] = []

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    """Tokenize đơn giản, hỗ trợ Unicode (bao gồm tiếng Việt có dấu)."""
    return _TOKEN_RE.findall(text.lower())


def _load_corpus_from_chroma() -> list[dict]:
    """Đọc toàn bộ chunks đã index ở Task 4 trực tiếp từ ChromaDB."""
    collection = get_collection()
    if collection.count() == 0:
        return []

    data = collection.get(include=["documents", "metadatas"])
    return [
        {"content": doc, "metadata": meta}
        for doc, meta in zip(data["documents"], data["metadatas"])
    ]


def build_bm25_index(corpus: list[dict]):
    """
    Xây dựng BM25 index từ corpus.

    Args:
        corpus: List of {'content': str, 'metadata': dict}

    Returns:
        BM25Okapi instance.
    """
    from rank_bm25 import BM25Okapi

    tokenized_corpus = [_tokenize(doc["content"]) for doc in corpus]
    return BM25Okapi(tokenized_corpus)


def _get_bm25(force_rebuild: bool = False):
    """Lazy-load + cache BM25 index từ ChromaDB corpus."""
    global _bm25_index, _bm25_corpus
    if _bm25_index is None or force_rebuild:
        _bm25_corpus = _load_corpus_from_chroma()
        if not _bm25_corpus:
            _bm25_index = None
            return None, []
        _bm25_index = build_bm25_index(_bm25_corpus)
    return _bm25_index, _bm25_corpus


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm từ khóa sử dụng BM25.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,      # BM25 score
            'metadata': dict
        }
        Sorted by score descending.
    """
    bm25, corpus = _get_bm25()
    if bm25 is None:
        return []

    tokenized_query = _tokenize(query)
    scores = bm25.get_scores(tokenized_query)

    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    results = []
    for idx in ranked_indices[:top_k]:
        if scores[idx] > 0:
            results.append({
                "content": corpus[idx]["content"],
                "score": float(scores[idx]),
                "metadata": corpus[idx]["metadata"],
            })
    return results


if __name__ == "__main__":
    results = lexical_search("phương thức thanh toán shopee", top_k=5)
    if not results:
        print("Không có kết quả — chạy Task 4 (run_pipeline) để index trước.")
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
