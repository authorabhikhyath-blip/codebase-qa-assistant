import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure backend directory is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.qa import LocalQAService as QAService
from app.services.indexing import repository_identity
from app.core.config import settings


def calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate summary retrieval and grounding metrics from a list of question results."""
    total = len(results)
    if total == 0:
        return {
            "total_questions": 0,
            "file_recall": 0.0,
            "symbol_recall": 0.0,
            "evidence_recall": 0.0,
            "grounded_rate": 0.0,
        }

    file_hits = sum(1 for r in results if r.get("file_found", False))
    symbol_hits = sum(1 for r in results if r.get("symbol_found", False))
    evidence_hits = sum(1 for r in results if r.get("evidence_found", False))
    grounded_hits = sum(1 for r in results if r.get("grounded_answer", False))

    return {
        "total_questions": total,
        "file_recall": round(file_hits / total, 4),
        "symbol_recall": round(symbol_hits / total, 4),
        "evidence_recall": round(evidence_hits / total, 4),
        "grounded_rate": round(grounded_hits / total, 4),
    }


def normalize_path(path_str: str) -> str:
    return path_str.replace("\\", "/").lower()


def evaluate_question_for_mode(
    qa_service: QAService,
    repo_path: str,
    item: Dict[str, Any],
    mode: str,
    generate_answer: bool = False,
) -> Dict[str, Any]:
    question = item["question"]
    expected_files = [normalize_path(f) for f in item["expected_files"]]
    expected_symbols = [s.lower() for s in item["expected_symbols"]]

    answer = ""
    retrieved_files = []
    retrieved_symbols = []
    file_found = False
    symbol_found = False

    try:
        chunks = qa_service.retrieve(
            path=repo_path,
            question=question,
            top_k=5,
            retrieval_mode=mode,
        )
        for c in chunks:
            meta = c.get("metadata", {})
            code = str(c.get("source_code", "")).lower()
            ref_file = normalize_path(meta.get("file_path", ""))
            ref_symbol = str(meta.get("symbol", "")).lower()
            retrieved_files.append(meta.get("file_path", ""))
            retrieved_symbols.append(meta.get("symbol", ""))

            for exp_f in expected_files:
                if exp_f in ref_file or ref_file.endswith(exp_f):
                    file_found = True

            for exp_s in expected_symbols:
                if exp_s in ref_symbol or exp_s in code:
                    symbol_found = True

        if generate_answer:
            resp = qa_service.ask(
                path=repo_path,
                question=question,
                top_k=5,
                retrieval_mode=mode,
            )
            answer = resp.get("answer", "")

    except Exception as e:
        return {
            "id": item["id"],
            "question": question,
            "mode": mode,
            "error": str(e),
            "file_found": False,
            "symbol_found": False,
            "evidence_found": False,
            "answer_generated": False,
            "grounded_answer": False,
            "retrieved_files": [],
            "retrieved_symbols": [],
            "answer_preview": "",
        }

    evidence_found = file_found and symbol_found
    answer_generated = len(answer.strip()) > 0
    
    # Grounded if answer was generated, evidence was found, and not a refusal
    is_refusal = "insufficient" in answer.lower() or "no relevant" in answer.lower() or "cannot answer" in answer.lower()
    grounded_answer = (answer_generated and evidence_found and not is_refusal) or (not generate_answer and evidence_found)

    return {
        "id": item["id"],
        "category": item.get("category", "unknown"),
        "question": question,
        "mode": mode,
        "file_found": file_found,
        "symbol_found": symbol_found,
        "evidence_found": evidence_found,
        "answer_generated": answer_generated,
        "grounded_answer": grounded_answer,
        "retrieved_files": retrieved_files[:3],
        "retrieved_symbols": retrieved_symbols[:3],
        "answer_preview": (answer[:160] + "...") if len(answer) > 160 else answer,
    }


def generate_markdown_report(
    eval_matrix: Dict[str, Dict[str, Any]],
    modes: List[str],
    metrics_per_mode: Dict[str, Dict[str, Any]],
    questions: List[Dict[str, Any]],
    repo_name: str,
) -> str:
    lines = []
    lines.append("# Codebase QA Assistant — Internal Evaluation Report")
    lines.append("")
    lines.append("> [!NOTE]")
    lines.append("> **Disclaimer**: This is an internal project evaluation conducted on the Codebase QA Assistant codebase.")
    lines.append("> It does not claim industry-wide SWE-bench or HumanEval-RAG scores.")
    lines.append("")
    lines.append(f"- **Evaluated Corpus**: `{repo_name}`")
    lines.append(f"- **Total Questions**: {len(questions)}")
    lines.append(f"- **Timestamp**: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- **Evaluated Modes**: {', '.join(modes)}")
    lines.append("")
    lines.append("## 1. Summary Metrics Comparison")
    lines.append("")
    lines.append("| Mode | File Recall | Symbol Recall | Evidence Recall | Grounded Answer Rate |")
    lines.append("| :--- | :---: | :---: | :---: | :---: |")

    for mode in modes:
        m = metrics_per_mode[mode]
        f_rec = f"{m['file_recall'] * 100:.1f}%"
        s_rec = f"{m['symbol_recall'] * 100:.1f}%"
        e_rec = f"{m['evidence_recall'] * 100:.1f}%"
        g_rate = f"{m['grounded_rate'] * 100:.1f}%"
        lines.append(f"| **{mode}** | {f_rec} | {s_rec} | {e_rec} | {g_rate} |")

    lines.append("")
    lines.append("## 2. Per-Question Results Matrix")
    lines.append("")
    lines.append("| ID | Category | Question | Semantic | BM25 | Hybrid RRF | Hybrid+Rerank | Expected Evidence |")
    lines.append("| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |")

    for q in questions:
        qid = q["id"]
        cat = q["category"]
        q_text = q["question"]
        exp = f"`{','.join(q['expected_files'])}` / `{','.join(q['expected_symbols'])}`"

        res_cols = []
        for mode in modes:
            r = eval_matrix.get(qid, {}).get(mode, {})
            ev = r.get("evidence_found", False)
            sym = r.get("symbol_found", False)
            fil = r.get("file_found", False)
            if ev:
                res_cols.append("PASS (Full)")
            elif fil and not sym:
                res_cols.append("PARTIAL (File)")
            elif sym and not fil:
                res_cols.append("PARTIAL (Symbol)")
            else:
                res_cols.append("FAIL")

        lines.append(f"| `{qid}` | {cat} | {q_text} | {res_cols[0]} | {res_cols[1]} | {res_cols[2]} | {res_cols[3]} | {exp} |")

    lines.append("")
    lines.append("## 3. Failure & Evidence Inspection")
    lines.append("")
    lines.append("Detailed inspection of failure modes and retrieved chunks per question:")
    lines.append("")

    for q in questions:
        qid = q["id"]
        lines.append(f"### `{qid}`: {q['question']}")
        lines.append(f"- **Category**: `{q['category']}`")
        lines.append(f"- **Expected Files**: `{', '.join(q['expected_files'])}`")
        lines.append(f"- **Expected Symbols**: `{', '.join(q['expected_symbols'])}`")
        lines.append("")
        lines.append("| Mode | File Found | Symbol Found | Evidence Found | Retrieved Files / Symbols | Answer Preview |")
        lines.append("| :--- | :---: | :---: | :---: | :--- | :--- |")

        for mode in modes:
            r = eval_matrix.get(qid, {}).get(mode, {})
            files_str = ", ".join(r.get("retrieved_files", [])) or "None"
            syms_str = ", ".join([str(s) for s in r.get("retrieved_symbols", [])]) or "None"
            preview = (r.get("answer_preview", "") or "").replace("\n", " ")
            lines.append(f"| **{mode}** | {r.get('file_found')} | {r.get('symbol_found')} | {r.get('evidence_found')} | `{files_str}` / `{syms_str}` | {preview} |")
        lines.append("")

    return "\n".join(lines)


def run_evaluation(with_llm: bool = False):
    questions_file = PROJECT_ROOT / "data" / "evaluation" / "questions.json"
    if not questions_file.exists():
        print(f"Error: {questions_file} not found.")
        sys.exit(1)

    with questions_file.open("r", encoding="utf-8") as f:
        questions = json.load(f)

    # Path to repo to evaluate: backend/app
    repo_path = str(BACKEND_DIR / "app")
    repo_id, _ = repository_identity(repo_path)

    qa_service = QAService()

    modes = ["semantic", "bm25", "hybrid", "hybrid_rerank"]
    results_by_mode: Dict[str, List[Dict[str, Any]]] = {m: [] for m in modes}
    eval_matrix: Dict[str, Dict[str, Any]] = {}

    print(f"Running Codebase QA Assistant Evaluation on repo: {repo_path}")
    print(f"Total questions: {len(questions)}")
    print(f"Modes to test: {modes}")
    print(f"Generate LLM answers (Ollama): {with_llm}")

    for item in questions:
        qid = item["id"]
        eval_matrix[qid] = {}
        print(f"\nEvaluating [{item['category']}] {qid}: {item['question']}")

        for mode in modes:
            # If with_llm is enabled, generate answers on the primary hybrid_rerank mode or all modes
            gen_ans = with_llm and (mode == "hybrid_rerank")
            res = evaluate_question_for_mode(
                qa_service=qa_service,
                repo_path=repo_path,
                item=item,
                mode=mode,
                generate_answer=gen_ans,
            )
            results_by_mode[mode].append(res)
            eval_matrix[qid][mode] = res
            status = "PASS" if res["evidence_found"] else ("PARTIAL" if res["file_found"] or res["symbol_found"] else "FAIL")
            print(f"  - Mode '{mode:<14}': {status:<8} (File={res['file_found']}, Symbol={res['symbol_found']})")

    metrics_per_mode = {mode: calculate_metrics(results_by_mode[mode]) for mode in modes}

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY RESULTS")
    print("=" * 60)
    print(f"{'Mode':<15} | {'File Recall':<12} | {'Symbol Recall':<14} | {'Evidence Recall':<16} | {'Grounded Rate':<14}")
    print("-" * 75)
    for mode in modes:
        m = metrics_per_mode[mode]
        print(f"{mode:<15} | {m['file_recall']*100:>10.1f}% | {m['symbol_recall']*100:>12.1f}% | {m['evidence_recall']*100:>14.1f}% | {m['grounded_rate']*100:>12.1f}%")
    print("=" * 60)

    # Save machine-readable results
    output_data_dir = PROJECT_ROOT / "data" / "evaluation"
    output_data_dir.mkdir(parents=True, exist_ok=True)
    results_json_path = output_data_dir / "results.json"
    with results_json_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "repository_id": repo_id,
                "repository_path": str(repo_path),
                "metrics": metrics_per_mode,
                "results_by_mode": results_by_mode,
                "matrix": eval_matrix,
            },
            f,
            indent=2,
        )
    print(f"\nMachine-readable results saved to: {results_json_path}")

    # Generate and save markdown report
    docs_dir = PROJECT_ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_md_path = docs_dir / "evaluation.md"
    markdown_report = generate_markdown_report(
        eval_matrix=eval_matrix,
        modes=modes,
        metrics_per_mode=metrics_per_mode,
        questions=questions,
        repo_name="backend/app",
    )
    with report_md_path.open("w", encoding="utf-8") as f:
        f.write(markdown_report)
    print(f"Human-readable evaluation report saved to: {report_md_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run internal Codebase QA retrieval and RAG evaluation.")
    parser.add_argument("--with-llm", action="store_true", help="Generate full LLM answers with local Ollama")
    args = parser.parse_args()
    run_evaluation(with_llm=args.with_llm)
