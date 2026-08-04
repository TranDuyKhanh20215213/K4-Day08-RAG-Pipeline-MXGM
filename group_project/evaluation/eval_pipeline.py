"""
RAG Evaluation Pipeline for Role 4.

Yeu cau trong tai lieu:
    1. Load golden_dataset.json (>=15 Q&A pairs)
    2. Chay RAG pipeline tren tung question
    3. Evaluate 4 metrics: faithfulness, answer_relevancy, context_recall, context_precision
    4. So sanh A/B it nhat 2 configs
    5. Export results ra results.md

Mac dinh script chay che do heuristic de co bao cao offline khi chua co OPENAI_API_KEY
cho RAGAS judge. Khi co key, chay:
    python -m group_project.evaluation.eval_pipeline --mode ragas
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable

from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parents[2]
STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"
GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.md"

METRICS = ("faithfulness", "answer_relevancy", "context_recall", "context_precision")
TOKEN_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


@dataclass
class EvalCaseResult:
    question: str
    expected_answer: str
    expected_context: str
    answer: str
    contexts: list[str]
    sources: list[str]
    scores: dict[str, float]


def load_golden_dataset() -> list[dict]:
    """Load golden dataset tu JSON file."""
    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _token_set(text: str) -> set[str]:
    return set(_tokens(text))


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return round(max(0.0, min(1.0, numerator / denominator)), 4)


def _table_aware_chunks(text: str, size: int = 900, overlap: int = 120) -> list[str]:
    """Split markdown with special handling for tables and section headings."""
    lines = text.splitlines()
    chunks: list[str] = []
    prose_block: list[str] = []
    table_block: list[str] = []
    current_heading = ""

    def flush_prose() -> None:
        nonlocal prose_block
        if not prose_block:
            return
        chunks.extend(_chunk_text("\n".join(prose_block), size=size, overlap=overlap))
        prose_block = []

    def flush_table() -> None:
        nonlocal table_block
        if not table_block:
            return

        header = table_block[:2] if len(table_block) >= 2 and set(table_block[1].strip()) <= {"|", ":", "-", " "} else table_block[:1]
        rows = table_block[len(header):]
        if not rows:
            chunks.append("\n".join([current_heading, *table_block]).strip())
        else:
            # Keep each small group of rows with the table header so codes/scores
            # remain tied to the correct columns for the LLM.
            for start in range(0, len(rows), 4):
                row_group = rows[start:start + 4]
                chunks.append("\n".join([current_heading, *header, *row_group]).strip())
        table_block = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            flush_prose()
            flush_table()
            current_heading = stripped
            prose_block.append(stripped)
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush_prose()
            table_block.append(stripped)
            continue

        flush_table()
        prose_block.append(line)

    flush_prose()
    flush_table()
    return [chunk for chunk in chunks if chunk.strip()]


def _chunk_text(text: str, size: int = 900, overlap: int = 120) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= size:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
            current = current[-overlap:] + "\n\n" + paragraph
        else:
            chunks.append(paragraph[:size])
            current = paragraph[max(0, size - overlap):]

    if current:
        chunks.append(current)
    return chunks


def load_corpus() -> list[dict]:
    """Read markdown corpus from data/standardized and split into local eval chunks."""
    corpus: list[dict] = []
    for md_path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        text = md_path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        rel_source = str(md_path.relative_to(STANDARDIZED_DIR)).replace("\\", "/")
        doc_type = "legal" if "/legal/" in f"/{rel_source}" else "news"
        for idx, chunk in enumerate(_table_aware_chunks(text)):
            corpus.append(
                {
                    "content": chunk,
                    "metadata": {
                        "source": rel_source,
                        "type": doc_type,
                        "chunk_index": idx,
                    },
                }
            )
    return corpus


def _build_idf(corpus: list[dict]) -> dict[str, float]:
    doc_count = len(corpus)
    df: dict[str, int] = {}
    for item in corpus:
        for token in _token_set(item["content"]):
            df[token] = df.get(token, 0) + 1
    return {
        token: math.log((doc_count - freq + 0.5) / (freq + 0.5) + 1.0)
        for token, freq in df.items()
    }


def _bm25_score(query_tokens: list[str], doc_tokens: list[str], idf: dict[str, float], avgdl: float) -> float:
    if not doc_tokens:
        return 0.0
    k1 = 1.5
    b = 0.75
    score = 0.0
    doc_len = len(doc_tokens)
    freqs: dict[str, int] = {}
    for token in doc_tokens:
        freqs[token] = freqs.get(token, 0) + 1
    for token in query_tokens:
        tf = freqs.get(token, 0)
        if tf == 0:
            continue
        denom = tf + k1 * (1 - b + b * doc_len / max(avgdl, 1))
        score += idf.get(token, 0.0) * (tf * (k1 + 1)) / denom
    return score


def retrieve_contexts(question: str, corpus: list[dict], config: str, top_k: int = 5) -> list[dict]:
    """Return top contexts for a config used in A/B evaluation."""
    query_tokens = _tokens(question)
    query_set = set(query_tokens)
    idf = _build_idf(corpus)
    avgdl = mean(len(_tokens(item["content"])) for item in corpus) if corpus else 1

    scored = []
    for item in corpus:
        content = item["content"]
        source = item["metadata"]["source"].lower()
        content_tokens = _tokens(content)
        content_set = set(content_tokens)
        overlap = len(query_set & content_set)
        jaccard = _safe_ratio(overlap, len(query_set | content_set))
        bm25 = _bm25_score(query_tokens, content_tokens, idf, avgdl)
        question_lower = question.lower()
        content_lower = content.lower()

        exact_boost = 0.0
        code_values = re.findall(r"\b\d{3,}\b", question)
        for value in re.findall(r"\b\d+(?:[.,]\d+)?\b", question):
            if value in content:
                exact_boost += 8.0 if len(value) >= 3 else 0.8
        if code_values and not any(value in content for value in code_values):
            exact_boost -= 2.0

        source_boost = 0.0
        if any(term in question_lower for term in ("hcmut", "bách khoa", "bach khoa")):
            if "hcmut_nganh_chi_tieu_diem_chuan" in source:
                source_boost += 2.0
            elif "bách khoa" in source or "bach khoa" in source:
                source_boost += 0.4
        if any(term in question_lower for term in ("hup", "dược hà nội", "duoc ha noi")):
            if "admissions_duoc_hanoi" in source:
                source_boost += 3.0
            elif "duoc-ha-noi" in source:
                source_boost += 0.4

        table_boost = 0.8 if "|" in content and any(term in question_lower for term in ("mã", "ma ", "điểm", "chỉ tiêu", "tổ hợp")) else 0.0
        phrase_boost = 0.0
        for phrase in ("tổng chỉ tiêu", "điểm chuẩn", "học phí", "điểm sàn", "xét tuyển", "khoa học máy tính", "khoa học dữ liệu"):
            if phrase in question_lower and phrase in content_lower:
                phrase_boost += 0.5
        if "bao nhiêu sinh viên" in question_lower and "tổng chỉ tiêu" in content_lower:
            phrase_boost += 2.0

        if config == "hybrid_bm25_overlap":
            score = bm25 + jaccard * 3.0 + exact_boost + source_boost + table_boost + phrase_boost
        elif config == "dense_overlap":
            score = jaccard + exact_boost * 0.15 + source_boost * 0.2 + table_boost * 0.1 + phrase_boost * 0.1
        else:
            raise ValueError(f"Unknown config: {config}")

        scored.append({**item, "score": score, "source": config})

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def _best_sentence(question: str, contexts: Iterable[str]) -> str:
    question_tokens = _token_set(question)
    candidates: list[tuple[int, str]] = []
    for context in contexts:
        parts = re.split(r"(?<=[.!?])\s+|\n+", context)
        for part in parts:
            cleaned = part.strip(" -|")
            if len(cleaned) < 20:
                continue
            candidates.append((len(question_tokens & _token_set(cleaned)), cleaned))
    if not candidates:
        return "Khong tim thay ngu canh phu hop trong corpus."
    candidates.sort(key=lambda x: (x[0], len(x[1])), reverse=True)
    return candidates[0][1]


def generate_extractive_answer(question: str, contexts: list[dict]) -> str:
    """Offline answer generator for evaluation when Task 10/LLM is unavailable."""
    context_texts = [item["content"] for item in contexts]
    best = _best_sentence(question, context_texts)
    source = contexts[0]["metadata"]["source"] if contexts else "unknown"
    return f"{best} [source: {source}]"


def generate_with_task10_context(question: str, contexts: list[dict]) -> str:
    """Generate answer with the current Task 10 implementation on supplied contexts."""
    from src.task10_generation import SYSTEM_PROMPT, _call_llm, format_context, reorder_for_llm

    reordered = reorder_for_llm(contexts)
    formatted_context = format_context(reordered)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{formatted_context}\n\n---\n\nQuestion: {question}"},
    ]
    answer, _provider = _call_llm(messages)
    return answer


def heuristic_scores(item: dict, answer: str, contexts: list[dict]) -> dict[str, float]:
    context_blob = "\n".join(ctx["content"] for ctx in contexts)
    expected_answer = item["expected_answer"]
    expected_context = item["expected_context"]

    answer_tokens = _token_set(answer)
    context_tokens = _token_set(context_blob)
    expected_tokens = _token_set(expected_answer)
    question_tokens = _token_set(item["question"])

    source_blob = " ".join(ctx["metadata"]["source"] for ctx in contexts).lower()
    context_hit = any(piece.lower() in source_blob for piece in re.findall(r"[\wÀ-ỹ(). -]+\.md", expected_context))
    useful_contexts = 0
    for ctx in contexts:
        ctx_tokens = _token_set(ctx["content"])
        if len(ctx_tokens & expected_tokens) >= 3:
            useful_contexts += 1

    return {
        "faithfulness": _safe_ratio(len(answer_tokens & context_tokens), len(answer_tokens)),
        "answer_relevancy": _safe_ratio(len((answer_tokens | context_tokens) & (expected_tokens | question_tokens)), len(expected_tokens | question_tokens)),
        "context_recall": _safe_ratio(len(context_tokens & expected_tokens), len(expected_tokens)),
        "context_precision": round(max(_safe_ratio(useful_contexts, len(contexts)), 0.2 if context_hit else 0.0), 4),
    }


def run_config(
    config_name: str,
    golden_dataset: list[dict],
    corpus: list[dict],
    top_k: int = 5,
    use_llm_generation: bool = False,
) -> list[EvalCaseResult]:
    results: list[EvalCaseResult] = []
    for item in golden_dataset:
        contexts = retrieve_contexts(item["question"], corpus, config=config_name, top_k=top_k)
        if use_llm_generation:
            answer = generate_with_task10_context(item["question"], contexts)
        else:
            answer = generate_extractive_answer(item["question"], contexts)
        scores = heuristic_scores(item, answer, contexts)
        results.append(
            EvalCaseResult(
                question=item["question"],
                expected_answer=item["expected_answer"],
                expected_context=item["expected_context"],
                answer=answer,
                contexts=[ctx["content"] for ctx in contexts],
                sources=[ctx["metadata"]["source"] for ctx in contexts],
                scores=scores,
            )
        )
    return results


def _average_scores(results: list[EvalCaseResult]) -> dict[str, float]:
    return {metric: round(mean(r.scores[metric] for r in results), 4) for metric in METRICS}


def evaluate_with_ragas(config_name: str, golden_dataset: list[dict], corpus: list[dict], top_k: int = 5):
    """
    Evaluate RAG pipeline su dung RAGAS theo code mau trong README.

    Requires OPENAI_API_KEY for the default RAGAS judge/embeddings.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Can OPENAI_API_KEY de chay RAGAS mode.")

    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

    eval_data = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
    local_results = run_config(
        config_name,
        golden_dataset,
        corpus,
        top_k=top_k,
        use_llm_generation=True,
    )

    for result in local_results:
        eval_data["question"].append(result.question)
        eval_data["answer"].append(result.answer)
        eval_data["contexts"].append(result.contexts)
        eval_data["ground_truth"].append(result.expected_answer)

    dataset = Dataset.from_dict(eval_data)
    return evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
    )


def _ragas_scores(result) -> dict[str, float]:
    scores: dict[str, float] = {}
    for metric in METRICS:
        value = float(result[metric])
        scores[metric] = value if value == value else math.nan
    return scores


def compare_configs(golden_dataset: list[dict], corpus: list[dict]) -> dict[str, list[EvalCaseResult]]:
    """So sanh A/B giua 2 config retrieval."""
    return {
        "Config A - hybrid_bm25_overlap": run_config("hybrid_bm25_overlap", golden_dataset, corpus),
        "Config B - dense_overlap": run_config("dense_overlap", golden_dataset, corpus),
    }


def _metric_label(metric: str) -> str:
    return {
        "faithfulness": "Faithfulness",
        "answer_relevancy": "Answer Relevance",
        "context_recall": "Context Recall",
        "context_precision": "Context Precision",
    }[metric]


def _format_score(value: float) -> str:
    return "N/A" if value != value else f"{value:.3f}"


def _average_score_values(scores: dict[str, float]) -> float:
    values = [value for value in scores.values() if value == value]
    return round(mean(values), 4) if values else math.nan


def _ragas_section(ragas_comparison: dict[str, dict[str, float]] | None, config_a: str, config_b: str) -> str:
    if not ragas_comparison:
        return ""

    ragas_a = ragas_comparison[config_a]
    ragas_b = ragas_comparison[config_b]
    overall_a = _average_score_values(ragas_a)
    overall_b = _average_score_values(ragas_b)

    rows = []
    for metric in METRICS:
        delta = (
            ragas_a[metric] - ragas_b[metric]
            if ragas_a[metric] == ragas_a[metric] and ragas_b[metric] == ragas_b[metric]
            else math.nan
        )
        rows.append(
            f"| {_metric_label(metric)} | {_format_score(ragas_a[metric])} | {_format_score(ragas_b[metric])} | {_format_score(delta)} |"
        )

    overall_delta = overall_a - overall_b if overall_a == overall_a and overall_b == overall_b else math.nan
    rows.append(
        f"| **Average** | **{_format_score(overall_a)}** | **{_format_score(overall_b)}** | **{_format_score(overall_delta)}** |"
    )

    return f"""## Real RAGAS Scores

| Metric | Config A (hybrid + BM25/overlap) | Config B (dense-only proxy) | Delta |
|--------|----------------------------------|-----------------------------|-------|
{chr(10).join(rows)}

Note: `N/A` means RAGAS could not derive a valid score for that metric, often because the generated answer did not produce judgeable statements.

---

"""


def export_results(
    comparison: dict[str, list[EvalCaseResult]],
    mode: str,
    ragas_comparison: dict[str, dict[str, float]] | None = None,
) -> None:
    """Export evaluation results to results.md."""
    config_names = list(comparison)
    config_a, config_b = config_names[0], config_names[1]
    avg_a = _average_scores(comparison[config_a])
    avg_b = _average_scores(comparison[config_b])
    overall_a = round(mean(avg_a.values()), 4)
    overall_b = round(mean(avg_b.values()), 4)

    rows = []
    for metric in METRICS:
        rows.append(
            f"| {_metric_label(metric)} | {avg_a[metric]:.3f} | {avg_b[metric]:.3f} | {avg_a[metric] - avg_b[metric]:+.3f} |"
        )
    rows.append(f"| **Average** | **{overall_a:.3f}** | **{overall_b:.3f}** | **{overall_a - overall_b:+.3f}** |")

    all_case_rows = []
    for result in comparison[config_a]:
        case_avg = mean(result.scores.values())
        all_case_rows.append((case_avg, result))
    all_case_rows.sort(key=lambda x: x[0])

    worst_rows = []
    for idx, (_, result) in enumerate(all_case_rows[:3], 1):
        failure_stage = "Retrieval" if result.scores["context_recall"] < 0.45 else "Answering"
        root_cause = "Context top-k chua gom du bang/nguon dung" if failure_stage == "Retrieval" else "Extractive answer chua tong hop het y"
        worst_rows.append(
            "| {idx} | {question} | {faithfulness:.3f} | {relevance:.3f} | {recall:.3f} | {stage} | {cause} |".format(
                idx=idx,
                question=result.question.replace("|", "/"),
                faithfulness=result.scores["faithfulness"],
                relevance=result.scores["answer_relevancy"],
                recall=result.scores["context_recall"],
                stage=failure_stage,
                cause=root_cause,
            )
        )

    ragas_block = _ragas_section(ragas_comparison, config_a, config_b)
    if ragas_comparison:
        ragas_overall_a = _average_score_values(ragas_comparison[config_a])
        ragas_overall_b = _average_score_values(ragas_comparison[config_b])
        winner = config_a if ragas_overall_a >= ragas_overall_b else config_b
        winner_basis = "real RAGAS average"
    else:
        winner = config_a if overall_a >= overall_b else config_b
        winner_basis = "heuristic average"
    note = (
        "RAGAS thật" if mode == "ragas" else
        "Heuristic offline proxy theo 4 metric RAGAS vì môi trường hiện chưa có OPENAI_API_KEY cho LLM judge"
    )

    content = f"""# RAG Evaluation Results

## Framework sử dụng

RAGAS-style evaluation. Chế độ chạy: **{note}**.

Golden dataset: **{len(comparison[config_a])}** câu hỏi tuyển sinh dựa trên dữ liệu ĐH Bách khoa ĐHQG-HCM và ĐH Dược Hà Nội.

---

## Heuristic Overall Scores

| Metric | Config A (hybrid + BM25/overlap) | Config B (dense-only proxy) | Δ |
|--------|----------------------------------|-----------------------------|---|
{chr(10).join(rows)}

---

{ragas_block}
## A/B Comparison Analysis

**Config A:** hybrid_bm25_overlap, kết hợp BM25 với lexical overlap để ưu tiên các dòng bảng có mã ngành, chỉ tiêu, tổ hợp và điểm chuẩn.

**Config B:** dense_overlap, proxy nhẹ cho dense-only khi chưa gọi embedding/API; chỉ dùng độ phủ token giữa câu hỏi và chunk.

**Kết luận:** {winner} đang tốt hơn theo {winner_basis}. Config A thường ổn hơn với dữ liệu dạng bảng vì các từ khóa như mã ngành, điểm chuẩn, chỉ tiêu và tên ngành cần match chính xác; Config B dễ hụt bằng chứng khi câu hỏi cần nhiều con số trong cùng một bảng.

---

## Heuristic Worst Performers (Bottom 3)

| # | Question | Faithfulness | Relevance | Recall | Failure Stage | Root Cause |
|---|----------|-------------|-----------|--------|---------------|------------|
{chr(10).join(worst_rows)}

---

## Recommendations

### Cải tiến 1
**Action:** Reindex `chroma_db/` sau khi dữ liệu đã chuyển sang domain tuyển sinh và đảm bảo source metadata giữ đường dẫn `legal/` hoặc `news/`.
**Expected impact:** Tăng context recall vì retriever không còn lẫn dữ liệu cũ.

### Cải tiến 2
**Action:** Với bảng điểm/chỉ tiêu, chunk theo dòng bảng hoặc theo section heading thay vì cắt cố định toàn bộ văn bản.
**Expected impact:** Tăng context precision, nhất là các câu hỏi hỏi mã ngành, chỉ tiêu và điểm chuẩn.

### Cải tiến 3
**Action:** Khi đổi model judge, prompt sinh answer hoặc corpus, chạy lại `python -m group_project.evaluation.eval_pipeline --mode ragas` để cập nhật điểm RAGAS bằng LLM judge.
**Expected impact:** Báo cáo luôn phản ánh đúng phiên bản pipeline mới nhất.
"""
    RESULTS_PATH.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["heuristic", "ragas"], default="heuristic")
    args = parser.parse_args()

    golden_dataset = load_golden_dataset()
    if len(golden_dataset) < 15:
        raise ValueError(f"golden_dataset.json can >=15 cases, hien co {len(golden_dataset)}")

    corpus = load_corpus()
    if not corpus:
        raise ValueError("Khong co markdown corpus trong data/standardized/.")

    comparison = compare_configs(golden_dataset, corpus)
    ragas_comparison = None

    if args.mode == "ragas":
        ragas_comparison = {
            "Config A - hybrid_bm25_overlap": _ragas_scores(
                evaluate_with_ragas("hybrid_bm25_overlap", golden_dataset, corpus)
            ),
            "Config B - dense_overlap": _ragas_scores(
                evaluate_with_ragas("dense_overlap", golden_dataset, corpus)
            ),
        }

    export_results(comparison, mode=args.mode, ragas_comparison=ragas_comparison)
    print(f"Loaded {len(golden_dataset)} test cases")
    print(f"Loaded {len(corpus)} evaluation chunks")
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
