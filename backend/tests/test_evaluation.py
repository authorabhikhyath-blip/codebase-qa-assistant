import json
from pathlib import Path
import pytest


def test_evaluation_dataset_loading():
    dataset_path = Path(__file__).resolve().parent.parent.parent / "data" / "evaluation" / "questions.json"
    assert dataset_path.exists(), f"Evaluation questions file not found at {dataset_path}"
    
    with dataset_path.open("r", encoding="utf-8") as f:
        questions = json.load(f)
    
    assert isinstance(questions, list)
    assert 10 <= len(questions) <= 20, f"Expected between 10 and 20 questions, got {len(questions)}"
    
    required_keys = {"id", "category", "question", "expected_files", "expected_symbols"}
    categories = set()
    
    for item in questions:
        assert required_keys.issubset(item.keys()), f"Missing keys in question {item.get('id')}"
        assert isinstance(item["expected_files"], list) and len(item["expected_files"]) > 0
        assert isinstance(item["expected_symbols"], list) and len(item["expected_symbols"]) > 0
        assert len(item["question"].strip()) > 5
        categories.add(item["category"])
    
    # Must cover: exact identifier, function, class, architecture, cross-component, implementation detail, location, explanation
    expected_categories = {
        "exact_identifier",
        "function",
        "class",
        "architecture",
        "cross_component",
        "implementation_detail",
        "location",
        "explanation",
    }
    assert expected_categories.issubset(categories), f"Missing categories: {expected_categories - categories}"


def test_evaluation_metrics_computation():
    import sys
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from scripts.evaluate_rag import calculate_metrics

    mock_results = [
        {
            "id": "q1",
            "file_found": True,
            "symbol_found": True,
            "evidence_found": True,
            "answer_generated": True,
            "grounded_answer": True,
        },
        {
            "id": "q2",
            "file_found": True,
            "symbol_found": False,
            "evidence_found": False,
            "answer_generated": True,
            "grounded_answer": False,
        },
        {
            "id": "q3",
            "file_found": False,
            "symbol_found": False,
            "evidence_found": False,
            "answer_generated": True,
            "grounded_answer": False,
        },
        {
            "id": "q4",
            "file_found": True,
            "symbol_found": True,
            "evidence_found": True,
            "answer_generated": True,
            "grounded_answer": True,
        },
    ]

    metrics = calculate_metrics(mock_results)
    assert metrics["total_questions"] == 4
    assert metrics["file_recall"] == 0.75  # 3 / 4
    assert metrics["symbol_recall"] == 0.50  # 2 / 4
    assert metrics["evidence_recall"] == 0.50  # 2 / 4
    assert metrics["grounded_rate"] == 0.50  # 2 / 4
