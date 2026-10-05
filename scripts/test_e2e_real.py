import json
import sys
from pathlib import Path

# Setup paths
root = Path(__file__).resolve().parent.parent
backend_dir = root / "backend"
sys.path.insert(0, str(backend_dir))

from app.services.qa import LocalQAService
from app.services.overview import get_repository_source_snippet

repo_path = str(backend_dir / "app")
qa = LocalQAService()

questions = [
    {
        "category": "Exact Identifier",
        "question": "Where is rrf_k configured in settings and what is its default value?",
    },
    {
        "category": "Function Explanation",
        "question": "Explain what reciprocal_rank_fusion does in services/hybrid.py",
    },
    {
        "category": "Class Explanation",
        "question": "What is LocalReranker in services/reranker.py and what scoring weights does it use?",
    },
    {
        "category": "Architecture / Component Interaction",
        "question": "How does LocalQAService interact with ChromaDB and BM25 during retrieval?",
    },
    {
        "category": "Implementation & Security Detail",
        "question": "How does get_repository_source_snippet prevent directory traversal and symlink attacks?",
    },
]

print("=" * 80)
print("REAL END-TO-END CODEBASE QA ASSISTANT TEST WITH OLLAMA (qwen2.5-coder:3b)")
print("=" * 80)

for idx, q_item in enumerate(questions, 1):
    q = q_item["question"]
    cat = q_item["category"]
    print(f"\n[{idx}/5] {cat}: {q}")
    
    resp = qa.ask(path=repo_path, question=q, top_k=3, retrieval_mode="hybrid")
    answer = resp.get("answer", "")
    sources = resp.get("sources", [])
    
    print("\nANSWER:")
    print(answer)
    print("\nRETRIEVED SOURCES:")
    for s in sources:
        symbol_label = f"{s.get('parent_symbol', '')}.{s.get('symbol', '')}" if s.get('parent_symbol') else s.get('symbol', '')
        print(f"  - {s.get('file_path')}:{s.get('start_line')}-{s.get('end_line')} ({symbol_label or s.get('chunk_type')})")
        
    # Also verify source viewer endpoint for the first source snippet
    if sources:
        first_src = sources[0]
        snippet = get_repository_source_snippet(
            repository_id=resp["repository_id"],
            file_path=first_src["file_path"],
            start_line=first_src["start_line"],
            end_line=first_src["end_line"],
        )
        print(f"  [OK] Source snippet verified ({len(snippet['content'].splitlines())} lines retrieved safely)")

print("\n" + "=" * 80)
print("ALL 5 END-TO-END TESTS COMPLETED SUCCESSFULLY")
print("=" * 80)
