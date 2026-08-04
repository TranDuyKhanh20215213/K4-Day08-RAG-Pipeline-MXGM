"""
Task 10 — Generation Có Citation.

Chủ đề dữ liệu: tuyển sinh đại học / điểm chuẩn (trường, ngành, tổ hợp môn,
điểm chuẩn theo năm) — không phải ví dụ e-commerce Shopee trong README gốc.

Pipeline:
    1. retrieve() lấy top_k chunks từ Task 9 (hybrid + fallback PageIndex)
    2. reorder_for_llm() sắp lại thứ tự để tránh "lost in the middle"
    3. format_context() gắn nhãn nguồn cho từng chunk để LLM có thể cite
    4. Build prompt (system + context + query), gọi LLM
    5. Nếu không đủ evidence → LLM tự trả lời "không thể xác minh"

LLM provider: CHỈ dùng OpenAI (gọi thẳng OpenAI API bằng OPENAI_API_KEY, không
qua OpenRouter, không có fallback provider khác).
"""

import os

from dotenv import load_dotenv

load_dotenv()

from src.task9_retrieval_pipeline import retrieve


# =============================================================================
# CONFIGURATION — Giải thích lựa chọn
# =============================================================================

# top_k: Số chunks đưa vào context.
# Chọn 5 vì: dữ liệu điểm chuẩn mỗi chunk khá ngắn (1 mục trường/ngành), 5 chunks
# đủ để so sánh vài trường/ngành trong 1 câu trả lời mà không kéo prompt quá dài.
TOP_K = 5

# top_p (nucleus sampling): xác suất tích luỹ cho token generation.
# Chọn 0.9 vì: đủ tự nhiên về văn phong nhưng không lệch quá xa các token có xác suất cao.
TOP_P = 0.9

# temperature: độ ngẫu nhiên của output.
# Chọn 0.3 vì: đây là tác vụ tra cứu số liệu (điểm chuẩn) — cần chính xác, ít sáng tạo/bịa số.
TEMPERATURE = 0.3

# Model OpenAI dùng cho generation
OPENAI_MODEL = "gpt-4o-mini"


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """Bạn là trợ lý tư vấn tuyển sinh đại học, chuyên trả lời câu hỏi về điểm
chuẩn, tổ hợp môn xét tuyển, và quy định tuyển sinh của các trường đại học tại Việt Nam.

Quy tắc bắt buộc:
1. Chỉ sử dụng thông tin từ context được cung cấp — KHÔNG bịa đặt số liệu điểm chuẩn
2. Mỗi khẳng định/số liệu phải có trích dẫn ngay sau, ví dụ: [Tên trường, Năm]
3. Nếu context không đủ thông tin để trả lời → trả lời đúng nguyên văn:
   "Tôi không thể xác minh thông tin này từ nguồn hiện có"
4. Trả lời bằng tiếng Việt, có cấu trúc rõ ràng theo đoạn văn hoặc bảng nếu so sánh nhiều trường
5. Không suy luận hay ước tính điểm chuẩn ngoài những gì được nêu trong context"""


# =============================================================================
# DOCUMENT REORDERING (tránh lost in the middle)
# =============================================================================

def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """
    Sắp xếp chunks để tránh "lost in the middle" effect.

    LLM nhớ tốt thông tin ở ĐẦU và CUỐI prompt, quên thông tin ở GIỮA
    (Liu et al., 2023). Strategy: đặt chunks quan trọng nhất (score cao) ở đầu
    và cuối, kém quan trọng hơn ở giữa.

    Input order (by score):  [1, 2, 3, 4, 5]
    Output order:            [1, 3, 5, 4, 2]
    (best first, worst in middle, second-best last)

    Args:
        chunks: List sorted by score descending (from retrieval)

    Returns:
        List reordered để maximize LLM attention.
    """
    if len(chunks) <= 2:
        return chunks

    front = chunks[::2]    # index 0, 2, 4, ... -> đặt ở đầu, giữ nguyên thứ tự
    back = chunks[1::2]    # index 1, 3, ...     -> đặt ở cuối, đảo ngược
    return front + back[::-1]


# =============================================================================
# CONTEXT FORMATTING
# =============================================================================

def format_context(chunks: list[dict]) -> str:
    """
    Format chunks thành context string cho prompt.
    Mỗi chunk có label nguồn để LLM có thể cite đúng [Tên trường/Nguồn, Năm].

    Args:
        chunks: List of {'content': str, 'metadata': dict, 'score': float}

    Returns:
        Formatted context string.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        source = meta.get("source", f"Source {i}")
        doc_type = meta.get("type", "unknown")
        context_parts.append(
            f"[Document {i} | Source: {source} | Type: {doc_type}]\n"
            f"{chunk['content']}\n"
        )
    return "\n---\n".join(context_parts)


# =============================================================================
# LLM CALL — chỉ OpenAI
# =============================================================================

def _call_llm(messages: list[dict]) -> tuple[str, str]:
    """Gọi OpenAI API, trả về (answer, provider_name)."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Thiếu OPENAI_API_KEY trong .env — Task 10 chỉ dùng OpenAI, không có fallback provider khác."
        )

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=OPENAI_MODEL, messages=messages, temperature=TEMPERATURE, top_p=TOP_P
    )
    return response.choices[0].message.content, "openai"


# =============================================================================
# GENERATION
# =============================================================================

def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """
    End-to-end RAG generation có citation.

    Pipeline:
        1. Retrieve relevant chunks (Task 9)
        2. Reorder để tránh lost in the middle
        3. Format context với source labels
        4. Build prompt (system + context + query)
        5. Call LLM (OpenAI)
        6. Return answer + sources

    Args:
        query: Câu hỏi của user
        top_k: Số chunks tối đa lấy từ retrieval

    Returns:
        {
            'answer': str,           # Câu trả lời có citation
            'sources': list[dict],   # Các chunks đã dùng
            'retrieval_source': str, # 'hybrid' | 'pageindex' | 'none'
            'llm_provider': str,     # provider LLM thực sự được dùng
        }
    """
    chunks = retrieve(query, top_k=top_k)

    if not chunks:
        return {
            "answer": "Tôi không thể xác minh thông tin này từ nguồn hiện có",
            "sources": [],
            "retrieval_source": "none",
            "llm_provider": "none",
        }

    reordered = reorder_for_llm(chunks)
    context = format_context(reordered)

    user_message = f"Context:\n{context}\n\n---\n\nQuestion: {query}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    answer, provider = _call_llm(messages)

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0].get("source", "hybrid"),
        "llm_provider": provider,
    }


if __name__ == "__main__":
    test_queries = [
        "Điểm chuẩn ngành Y đa khoa của Đại học Y Hà Nội là bao nhiêu?",
        "Đại học Bách Khoa Hà Nội xét tuyển tổ hợp môn nào?",
        "So sánh điểm chuẩn năm nay với năm trước có tăng không?",
    ]

    for q in test_queries:
        print(f"\n{'=' * 70}")
        print(f"Q: {q}")
        print("=" * 70)
        result = generate_with_citation(q)
        print(f"\nA: {result['answer']}")
        print(
            f"\n[Sources: {len(result['sources'])} chunks | via {result['retrieval_source']} "
            f"| LLM: {result['llm_provider']}]"
        )
