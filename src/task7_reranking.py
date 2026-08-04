"""
Task 7 — Reranking Module.

Phương pháp chính: Cross-encoder reranker `BAAI/bge-reranker-v2-m3`, chạy
LOCAL qua `sentence-transformers.CrossEncoder` — multilingual (tốt cho tiếng
Việt), không cần API key/gọi mạng ngoài (khác với Jina reranker trước đó).
Model được tải về từ HuggingFace ở lần chạy đầu tiên (~1.1GB) và cache lại.

MMR và RRF vẫn được implement đầy đủ bên dưới vì Task 9 (hybrid retrieval)
cần RRF để merge kết quả semantic_search + lexical_search trước khi đưa qua
rerank_cross_encoder.

Lưu ý quan trọng về RRF (dùng lại ở Task 9): điểm RRF fused CHỈ phụ thuộc thứ hạng,
không phải độ tương đồng thật. Top-1 sau khi fuse luôn xấp xỉ 1/(k+1) ≈ 0.0164 (k=60),
bất kể nội dung đó có thật sự liên quan đến câu hỏi hay không. Đừng dùng điểm RRF để
quyết định fallback ở Task 9 — dùng cosine score gốc từ Task 5.

Cài đặt:
    pip install sentence-transformers torch
"""

import math

_reranker_model = None


def _get_reranker_model():
    """Lazy-load + cache CrossEncoder BAAI/bge-reranker-v2-m3 (chỉ tải/load 1 lần)."""
    global _reranker_model
    if _reranker_model is None:
        from sentence_transformers import CrossEncoder

        _reranker_model = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512)
    return _reranker_model


def rerank_cross_encoder(
    query: str, candidates: list[dict], top_k: int = 5
) -> list[dict]:
    """
    Rerank candidates bằng BAAI/bge-reranker-v2-m3 (cross-encoder, multilingual, local).

    Args:
        query: Câu truy vấn
        candidates: List of {'content': str, 'score': float, 'metadata': dict}
        top_k: Số lượng kết quả sau rerank

    Returns:
        List of top_k candidates, re-scored bằng relevance score của model
        (sigmoid của raw logit, về khoảng [0,1]), sorted descending. Nếu
        model chưa cài được (thiếu sentence-transformers/torch, hoặc lỗi tải
        weights), fallback về thứ tự score gốc thay vì crash pipeline.
    """
    if not candidates:
        return []

    def _fallback(reason: str) -> list[dict]:
        print(f"⚠ rerank_cross_encoder fallback ({reason}) — giữ nguyên score gốc.")
        return sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)[:top_k]

    try:
        model = _get_reranker_model()
        pairs = [(query, c["content"]) for c in candidates]
        raw_scores = model.predict(pairs)
    except Exception as e:
        return _fallback(f"lỗi load/chạy bge-reranker-v2-m3: {e}")

    results = []
    for candidate, raw in zip(candidates, raw_scores):
        # bge-reranker-v2-m3 trả về raw logit -> sigmoid để chuẩn hoá về [0,1]
        score = 1.0 / (1.0 + math.exp(-float(raw)))
        results.append({**candidate, "score": score})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def _cosine_sim(a: list[float], b: list[float]) -> float:
    import math

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    """
    Maximal Marginal Relevance — chọn candidates vừa relevant vừa diverse.

    MMR = λ * sim(query, doc) - (1-λ) * max(sim(doc, selected_docs))

    Args:
        query_embedding: Vector embedding của query
        candidates: List of {'content': str, 'score': float, 'embedding': list, 'metadata': dict}
        top_k: Số lượng kết quả
        lambda_param: Trade-off giữa relevance (1.0) và diversity (0.0)

    Returns:
        List of top_k candidates selected by MMR.
    """
    selected: list[int] = []
    remaining = list(range(len(candidates)))

    for _ in range(min(top_k, len(candidates))):
        best_idx = None
        best_score = float("-inf")

        for idx in remaining:
            relevance = _cosine_sim(query_embedding, candidates[idx]["embedding"])

            max_sim_to_selected = 0.0
            for sel_idx in selected:
                sim = _cosine_sim(
                    candidates[idx]["embedding"], candidates[sel_idx]["embedding"]
                )
                max_sim_to_selected = max(max_sim_to_selected, sim)

            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        selected.append(best_idx)
        remaining.remove(best_idx)

    return [candidates[i] for i in selected]


def rerank_rrf(
    ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60
) -> list[dict]:
    """
    Reciprocal Rank Fusion — gộp kết quả từ nhiều ranker.

    RRF(d) = Σ 1 / (k + rank_r(d))

    Args:
        ranked_lists: List of ranked result lists (mỗi list từ 1 ranker)
        top_k: Số lượng kết quả cuối cùng
        k: Smoothing constant (default=60, từ paper Cormack et al. 2009)

    Returns:
        List of top_k candidates sorted by RRF score descending.
        Lưu ý: score ở đây là điểm RRF (chỉ phản ánh thứ hạng), không phải
        cosine similarity gốc — xem cảnh báo ở đầu file.
    """
    rrf_scores: dict[str, float] = {}
    content_map: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, 1):
            key = item["content"]
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            content_map[key] = item

    sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    for content, score in sorted_items[:top_k]:
        item = dict(content_map[content])
        item["score"] = score
        results.append(item)
    return results


# =============================================================================
# Main rerank interface
# =============================================================================

def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    method: str = "cross_encoder",  # "cross_encoder" | "mmr" | "rrf"
    **kwargs,
) -> list[dict]:
    """
    Unified reranking interface. Mặc định dùng bge-reranker-v2-m3 (cross-encoder, local).

    Args:
        query: Câu truy vấn
        candidates: Danh sách candidates từ retrieval
        top_k: Số lượng kết quả sau rerank
        method: Phương pháp reranking
        **kwargs: tham số bổ sung cho mmr (query_embedding, lambda_param)
                  hoặc rrf (ranked_lists, k) nếu không dùng cross_encoder

    Returns:
        List of top_k reranked candidates.
    """
    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)
    elif method == "mmr":
        query_embedding = kwargs.get("query_embedding")
        if query_embedding is None:
            raise ValueError("method='mmr' cần truyền query_embedding qua kwargs")
        return rerank_mmr(
            query_embedding, candidates, top_k, kwargs.get("lambda_param", 0.7)
        )
    elif method == "rrf":
        ranked_lists = kwargs.get("ranked_lists")
        if ranked_lists is None:
            raise ValueError("method='rrf' cần truyền ranked_lists qua kwargs")
        return rerank_rrf(ranked_lists, top_k, kwargs.get("k", 60))
    else:
        raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    dummy_candidates = [
        {"content": "Chính sách trả hàng và hoàn tiền Shopee trong 15 ngày", "score": 0.8, "metadata": {}},
        {"content": "Các phương thức thanh toán hỗ trợ trên Shopee Vietnam", "score": 0.6, "metadata": {}},
        {"content": "Quy định đăng bán sản phẩm dành cho người bán", "score": 0.5, "metadata": {}},
    ]
    results = rerank("chính sách trả hàng shopee", dummy_candidates, top_k=2)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content']}")
