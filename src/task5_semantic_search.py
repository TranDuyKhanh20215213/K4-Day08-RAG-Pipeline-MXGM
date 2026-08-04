"""
Task 5 — Semantic Search Module.

Dense retrieval trên ChromaDB, dùng chung embedding model (OpenAI
text-embedding-3-small) và collection đã index ở Task 4.

Yêu cầu:
    - Input: query string + top_k
    - Output: danh sách chunks có score, sorted descending
"""

from src.task4_chunking_indexing import get_collection, get_embedding_model


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa sử dụng vector similarity (cosine) trên ChromaDB.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,      # Nội dung chunk
            'score': float,      # Cosine similarity, càng cao càng liên quan
            'metadata': dict     # source, type, chunk_index
        }
        Sorted by score descending.
    """
    embeddings = get_embedding_model()
    query_vector = embeddings.embed_query(query)

    collection = get_collection()
    if collection.count() == 0:
        return []

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        # ChromaDB trả về cosine distance (0 = giống hệt); chuyển sang similarity [0,1]
        score = max(0.0, 1.0 - dist)
        output.append({"content": doc, "score": round(score, 4), "metadata": meta})

    output.sort(key=lambda x: x["score"], reverse=True)
    return output[:top_k]


if __name__ == "__main__":
    results = semantic_search("quy định trả hàng hoàn tiền shopee", top_k=5)
    if not results:
        print("Không có kết quả — collection rỗng hoặc chưa chạy Task 4 (run_pipeline).")
    for r in results:
        print(f"[{r['score']:.3f}] {r['metadata'].get('source')} -> {r['content'][:100]}...")
