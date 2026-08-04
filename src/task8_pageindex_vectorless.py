"""
Task 8 — PageIndex Vectorless RAG.

Dùng REST API của PageIndex trực tiếp (https://docs.pageindex.ai/api-reference)
thay vì SDK, để kiểm soát rõ từng bước upload / poll / parse (SDK che giấu
phần polling nên khó debug khi cần).

Flow:
    1. Convert mỗi file markdown trong data/standardized/ sang 1 PDF đơn giản
       (PageIndex /doc/ chỉ nhận PDF, không nhận .md trực tiếp — endpoint
       /markdown/ có tồn tại nhưng chỉ trả về tree structure, KHÔNG trả doc_id
       dùng được cho /retrieval/, nên không dùng được cho vectorless query).
    2. POST /doc/ để upload, nhận doc_id.
    3. Poll GET /doc/{doc_id}/?type=tree cho đến khi retrieval_ready = true.
    4. Lưu mapping source -> doc_id vào data/pageindex_registry.json để không
       phải upload lại mỗi lần chạy.
    5. pageindex_search(): với mỗi doc_id đã sẵn sàng, POST /retrieval/ (legacy,
       nhưng vẫn hoạt động — xem cảnh báo "deprecation" trong response), poll
       GET /retrieval/{id}/ tới khi completed, rồi parse "retrieved_nodes".

Lưu ý về response schema (đã verify với docs.pageindex.ai/api-reference,
06/2026): mỗi node trong "retrieved_nodes" có dạng
    {"title": str, "node_id": str,
     "relevant_contents": [{"page_index": int, "relevant_content": str}, ...]}
tức "relevant_contents" là list phẳng of dict — KHÔNG phải list[list[...]] và
key nội dung là "relevant_content" (không phải "section_title"). Vì API này
là "legacy" và có thể đổi format bất cứ lúc nào, hàm _parse_retrieved_nodes()
bên dưới xử lý phòng thủ (defensive) cho cả 2 dạng lồng (flat list / list of
list) và cả 2 tên field cũ/mới — LUÔN in raw response ra khi chạy trực tiếp
file này để tự kiểm tra nếu PageIndex đổi schema.

PageIndex không trả điểm liên quan (relevance score) trực tiếp — thứ tự trong
"retrieved_nodes" đã là thứ tự do PageIndex reasoning xếp hạng, nên ta tự gán
score giảm dần theo rank (không so sánh được trực tiếp với cosine score của
Task 5, chỉ dùng để sort nội bộ và hiển thị).

Cài đặt:
    pip install requests python-dotenv reportlab
"""

import json
import os
import textwrap
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
PAGEINDEX_BASE_URL = "https://api.pageindex.ai"

PROJECT_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"
REGISTRY_PATH = PROJECT_DIR / "data" / "pageindex_registry.json"
TMP_PDF_DIR = PROJECT_DIR / "data" / "_pageindex_tmp_pdf"

POLL_INTERVAL_SECONDS = 5
UPLOAD_READY_TIMEOUT_SECONDS = 300
RETRIEVAL_READY_TIMEOUT_SECONDS = 90


def _headers() -> dict:
    if not PAGEINDEX_API_KEY:
        raise RuntimeError(
            "Thiếu PAGEINDEX_API_KEY trong .env. Đăng ký key tại "
            "https://dash.pageindex.ai/api-keys"
        )
    return {"api_key": PAGEINDEX_API_KEY}


# =============================================================================
# Registry (source markdown -> PageIndex doc_id) — tránh upload lại mỗi lần
# =============================================================================

def _load_registry() -> dict:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {}


def _save_registry(registry: dict):
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# =============================================================================
# Markdown -> PDF (PageIndex /doc/ chỉ nhận PDF)
# =============================================================================

def _markdown_to_pdf(md_path: Path, pdf_path: Path):
    """Convert 1 file markdown sang PDF đơn giản (text-only, giữ nguyên nội dung)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines() or [""]

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    margin_x, margin_top, margin_bottom = 50, 50, 50
    y = height - margin_top

    for raw_line in lines:
        is_heading = raw_line.strip().startswith("#")
        line_text = raw_line.strip().lstrip("#").strip() or " "
        font, size, leading = ("Helvetica-Bold", 13, 18) if is_heading else ("Helvetica", 10, 14)
        c.setFont(font, size)

        wrap_width = 100 if not is_heading else 80
        for wrapped in textwrap.wrap(line_text, width=wrap_width) or [" "]:
            if y < margin_bottom:
                c.showPage()
                y = height - margin_top
                c.setFont(font, size)
            c.drawString(margin_x, y, wrapped)
            y -= leading

    c.save()


# =============================================================================
# Upload + polling
# =============================================================================

def _submit_pdf(pdf_path: Path) -> str:
    with open(pdf_path, "rb") as f:
        resp = requests.post(
            f"{PAGEINDEX_BASE_URL}/doc/",
            headers=_headers(),
            files={"file": f},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()["doc_id"]


def _wait_until_ready(doc_id: str, timeout: int = UPLOAD_READY_TIMEOUT_SECONDS) -> bool:
    """Poll GET /doc/{doc_id}/?type=tree cho đến khi retrieval_ready=true."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{PAGEINDEX_BASE_URL}/doc/{doc_id}/",
            headers=_headers(),
            params={"type": "tree"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("retrieval_ready") or data.get("status") == "completed":
            return True
        if data.get("status") == "failed":
            return False
        time.sleep(POLL_INTERVAL_SECONDS)
    return False


def upload_documents(force_reupload: bool = False) -> dict:
    """
    Convert + upload toàn bộ markdown trong data/standardized/ lên PageIndex.

    Returns:
        Registry dict: {relative_source_path: {"doc_id": str, "ready": bool}}
    """
    registry = _load_registry()

    md_files = sorted(STANDARDIZED_DIR.rglob("*.md"))
    if not md_files:
        print("⚠ Không có file .md nào trong data/standardized/ — chạy Task 3 trước.")
        return registry

    for md_file in md_files:
        rel_key = str(md_file.relative_to(STANDARDIZED_DIR))

        if rel_key in registry and not force_reupload:
            print(f"  = Đã có trong registry, bỏ qua: {rel_key} -> {registry[rel_key]['doc_id']}")
            continue

        pdf_path = TMP_PDF_DIR / (md_file.stem + ".pdf")
        _markdown_to_pdf(md_file, pdf_path)

        doc_id = _submit_pdf(pdf_path)
        print(f"  ✓ Uploaded: {rel_key} -> {doc_id} (đang xử lý...)")

        ready = _wait_until_ready(doc_id)
        status_str = "ready" if ready else "timeout/failed"
        print(f"    -> {status_str}")

        registry[rel_key] = {"doc_id": doc_id, "ready": ready}
        _save_registry(registry)

    return registry


# =============================================================================
# Retrieval (legacy /retrieval/ endpoint)
# =============================================================================

def _submit_retrieval(doc_id: str, query: str, thinking: bool = False) -> str:
    resp = requests.post(
        f"{PAGEINDEX_BASE_URL}/retrieval/",
        headers=_headers(),
        json={"doc_id": doc_id, "query": query, "thinking": thinking},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["retrieval_id"]


def _poll_retrieval(retrieval_id: str, timeout: int = RETRIEVAL_READY_TIMEOUT_SECONDS) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{PAGEINDEX_BASE_URL}/retrieval/{retrieval_id}/",
            headers=_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "completed":
            return data
        if data.get("status") == "failed":
            return data
        time.sleep(2)
    return {"status": "timeout", "retrieved_nodes": []}


def _parse_retrieved_nodes(retrieval_result: dict, doc_id: str, source_name: str) -> list[dict]:
    """
    Parse "retrieved_nodes" một cách phòng thủ — hỗ trợ cả 2 dạng đã quan sát
    được của PageIndex API:
      A) relevant_contents: [{"page_index":.., "relevant_content":..}, ...]   (flat, hiện tại)
      B) relevant_contents: [[{"section_title":.., "relevant_content":..}], ..] (nested, bản cũ hơn)
    """
    parsed = []
    nodes = retrieval_result.get("retrieved_nodes", [])

    for node in nodes:
        title = node.get("title") or node.get("section_title") or ""
        node_id = node.get("node_id", "")
        contents = node.get("relevant_contents", [])

        # Chuẩn hoá về 1 list phẳng of dict, dù input là nested hay flat.
        flat_items = []
        for entry in contents:
            if isinstance(entry, list):
                flat_items.extend(entry)
            elif isinstance(entry, dict):
                flat_items.append(entry)

        if not flat_items:
            # Không có relevant_contents chi tiết -> fallback dùng "text" của node nếu có
            text = node.get("text", "")
            if text:
                flat_items = [{"relevant_content": text}]

        for item in flat_items:
            content = item.get("relevant_content") or item.get("text") or ""
            if not content.strip():
                continue
            parsed.append({
                "content": content.strip(),
                "metadata": {
                    "source": source_name,
                    "doc_id": doc_id,
                    "node_id": node_id,
                    "section": item.get("section_title") or title,
                    "page_index": item.get("page_index"),
                },
            })

    return parsed


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval sử dụng PageIndex.
    Dùng làm fallback khi hybrid search (Task 5+6) không có kết quả tốt.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,       # rank-based (PageIndex không trả score gốc)
            'metadata': dict,
            'source': 'pageindex'
        }
    """
    registry = _load_registry()
    ready_docs = {k: v for k, v in registry.items() if v.get("ready")}

    if not ready_docs:
        print("⚠ Chưa có document nào sẵn sàng trên PageIndex — chạy upload_documents() trước.")
        return []

    all_items = []
    for source_name, info in ready_docs.items():
        doc_id = info["doc_id"]
        try:
            retrieval_id = _submit_retrieval(doc_id, query)
            result = _poll_retrieval(retrieval_id)
            if result.get("status") != "completed":
                print(f"  ⚠ Retrieval không hoàn tất cho {source_name}: {result.get('status')}")
                continue
            all_items.extend(_parse_retrieved_nodes(result, doc_id, source_name))
        except requests.RequestException as e:
            print(f"  ⚠ Lỗi gọi PageIndex retrieval cho {source_name}: {e}")
            continue

    top_items = all_items[:top_k]
    results = []
    for rank, item in enumerate(top_items):
        score = round(max(0.0, 1.0 - rank * 0.1), 4)  # rank-based, chỉ để sort/hiển thị
        results.append({
            "content": item["content"],
            "score": score,
            "metadata": item["metadata"],
            "source": "pageindex",
        })
    return results


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        print("⚠ Hãy set PAGEINDEX_API_KEY trong file .env")
        print("  Đăng ký tại: https://dash.pageindex.ai/api-keys")
    else:
        print("Uploading documents...")
        upload_documents()

        print("\nTest query:")
        results = pageindex_search("danh sách sản phẩm cấm đăng bán", top_k=3)
        if not results:
            print("Không có kết quả.")
        for r in results:
            print(f"[{r['score']:.3f}] ({r['metadata'].get('source')}) {r['content'][:100]}...")
