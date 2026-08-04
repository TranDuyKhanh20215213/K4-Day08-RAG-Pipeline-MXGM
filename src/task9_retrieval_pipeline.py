"""
Task 9 — Retrieval Pipeline Hoàn Chỉnh.

Kết hợp semantic search + lexical search + reranking + PageIndex fallback
thành một pipeline thống nhất.

Logic:
    1. Chạy semantic_search + lexical_search (lấy dư fetch_k > top_k để có đủ
       candidate cho bước merge/rerank)
    2. Merge kết quả bằng RRF (Task 7 — rerank_rrf)
    3. Rerank merged results bằng Jina cross-encoder (Task 7 — rerank_cross_encoder)
    4. Nếu điểm cosine GỐC tốt nhất (từ semantic_search, trước khi qua RRF) <
       score_threshold → fallback sang PageIndex
    5. Return top_k results

⚠️ BẪY THƯỜNG GẶP #1 — đọc kỹ trước khi code (đã có sẵn trong file gốc):
    Nếu bạn dùng điểm RRF đã fuse (Task 7) để so với score_threshold, bạn sẽ gặp bug
    thật: RRF max score luôn ≈ 1/(k+1) ≈ 0.0164 (k=60) BẤT KỂ nội dung có liên quan
    hay không. Nếu đặt threshold thấp (như 0.005) để "hợp" với thang điểm RRF, thực
    chất KHÔNG câu hỏi nào đủ thấp để trigger fallback nữa — kể cả query hoàn toàn vô
    nghĩa vẫn trả về kết quả "hybrid" (rác) thay vì fallback đúng như thiết kế.

    Cách sửa đúng (đã áp dụng bên dưới): giữ điểm cosine similarity GỐC của
    semantic_search (biến `dense_results`, đọc TRƯỚC khi merge/RRF) làm căn cứ
    quyết định fallback, tách biệt hoàn toàn khỏi điểm RRF/cross-encoder dùng để
    sắp xếp kết quả cuối cùng.

⚠️ BẪY THƯỜNG GẶP #2 — dễ nhầm giữa 2 tầng "rerank":
    File gốc có config `RERANK_METHOD = "rrf"`, nhưng nếu để nguyên giá trị đó
    và gọi `rerank(query, merged, method="rrf")` ở bước 3 thì sẽ crash/vô nghĩa:
    `rerank_rrf()` nhận `ranked_lists` (nhiều list kết quả), không nhận 1 list
    đã merge sẵn — RRF chỉ nên dùng đúng 1 lần ở bước 2 (merge dense+sparse).
    Bước 3 "rerank" thực sự (re-score theo mức độ liên quan) phải dùng
    `rerank_cross_encoder` (Jina reranker, Task 7) — đó mới là lý do Task 7 yêu
    cầu tích hợp cross-encoder. Vì vậy RERANK_METHOD ở dưới được đặt lại thành
    "cross_encoder", không phải "rrf".
"""

from src.task5_semantic_search import semantic_search
from src.task6_lexical_search import lexical_search
from src.task7_reranking import rerank, rerank_rrf
from src.task8_pageindex_vectorless import pageindex_search


# =============================================================================
# CONFIGURATION
# =============================================================================

# TODO: Calibrate threshold này bằng cách tự đo điểm cosine của semantic_search
# cho câu hỏi liên quan vs câu hỏi lạc đề (xem BẪY #1 ở trên) — ĐỪNG copy nguyên
# giá trị mẫu, mỗi corpus/embedding model sẽ cho khoảng điểm khác nhau.
SCORE_THRESHOLD = 0.3   # Nếu best score (cosine gốc, KHÔNG phải RRF) < threshold → fallback PageIndex
DEFAULT_TOP_K = 5
RERANK_METHOD = "cross_encoder"  # Jina reranker (Task 7) — xem BẪY #2 ở trên, KHÔNG dùng "rrf" ở bước này
FETCH_MULTIPLIER = 3   # Lấy top_k * FETCH_MULTIPLIER candidate từ mỗi nhánh trước khi merge/rerank


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """
    Retrieval pipeline hoàn chỉnh với fallback logic.

    Pipeline:
        Query
          ├→ Semantic Search → dense_results (giữ điểm cosine gốc)
          ├→ Lexical Search  → sparse_results
          │
          ├→ Merge (RRF, Task 7) → merged_results (source="hybrid")
          ├→ Rerank (Jina cross-encoder, Task 7) → reranked_results
          │
          └→ If dense_results[0]["score"] < threshold (cosine GỐC):
                └→ PageIndex Vectorless (Task 8) → fallback_results (source="pageindex")

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả cuối cùng
        score_threshold: Ngưỡng điểm cosine gốc tối thiểu (KHÔNG phải điểm RRF)
        use_reranking: Có áp dụng reranking (Jina) hay không

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': str  # 'hybrid' hoặc 'pageindex'
        }
    """
    fetch_k = max(top_k * FETCH_MULTIPLIER, top_k + 5)

    # Bước 1: Song song (về mặt logic) chạy semantic + lexical
    dense_results = semantic_search(query, top_k=fetch_k)
    sparse_results = lexical_search(query, top_k=fetch_k)

    # Giữ lại điểm cosine GỐC trước khi merge — đây là căn cứ fallback duy nhất
    # được phép dùng (xem BẪY #1). Không đọc lại "score" từ merged/reranked sau này.
    best_dense_score = dense_results[0]["score"] if dense_results else 0.0

    # Bước 2: Merge bằng RRF (đây là lần dùng RRF DUY NHẤT trong pipeline)
    merged = rerank_rrf([dense_results, sparse_results], top_k=fetch_k)
    for item in merged:
        item["source"] = "hybrid"

    # Bước 3: Rerank thật sự bằng Jina cross-encoder (xem BẪY #2)
    if use_reranking and merged:
        final_results = rerank(query, merged, top_k=top_k, method=RERANK_METHOD)
        for item in final_results:
            item.setdefault("source", "hybrid")
    else:
        final_results = merged[:top_k]

    # Bước 4: Fallback dựa trên cosine gốc, KHÔNG phải RRF/cross-encoder score
    if best_dense_score < score_threshold:
        print(f"  ⚠ Semantic best score ({best_dense_score:.3f}) < threshold ({score_threshold}) → fallback PageIndex")
        fallback = pageindex_search(query, top_k=top_k)
        if fallback:
            return fallback
        print("  ⚠ PageIndex fallback cũng không có kết quả — trả về hybrid results (có thể rỗng).")

    return final_results[:top_k]


if __name__ == "__main__":
    test_queries = [
        "What payment methods does Shopee support?",
        "How do I request a return or refund?",
        "What evidence do I need for a refund request?",
        "xyzabc123nonsense",  # Query không có kết quả → test fallback
    ]

    for q in test_queries:
        print(f"\nQuery: {q}")
        print("-" * 60)
        results = retrieve(q, top_k=3)
        if not results:
            print("  (không có kết quả)")
        for i, r in enumerate(results, 1):
            print(f"  {i}. [{r['score']:.3f}] [{r['source']}] {r['content'][:80]}...")
