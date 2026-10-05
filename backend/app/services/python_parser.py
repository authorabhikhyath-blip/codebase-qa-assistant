from __future__ import annotations

from pathlib import Path

import tree_sitter_python
from tree_sitter import Language, Parser

from app.models.rag import CodeChunk


class PythonTreeSitterParser:
    """Tree-sitter-backed Python parser; other languages can provide sibling adapters."""

    def __init__(self) -> None:
        self._language = Language(tree_sitter_python.language())

    def parse(self, source: str, *, repository_id: str, repository_name: str,
              repository_path: str, file_path: str) -> tuple[list[CodeChunk], bool]:
        parser = Parser(self._language)
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)
        if tree is None:
            return [], True

        root = tree.root_node
        syntax_error = root.has_error
        final_line = max(1, source.count("\n") + (1 if source and not source.endswith("\n") else 0))
        chunks: list[CodeChunk] = []

        def make_chunk(node, chunk_type: str, symbol: str = "") -> None:
            code = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            if code.strip():
                chunks.append(CodeChunk(
                    repository_id=repository_id,
                    repository_name=repository_name,
                    repository_path=repository_path,
                    file_path=file_path,
                    symbol=symbol,
                    chunk_type=chunk_type,
                    start_line=node.start_point.row + 1,
                    end_line=max(node.start_point.row + 1, node.end_point.row + (1 if node.end_point.column else 0)),
                    source_code=code,
                ))

        def text_of_name(node) -> str:
            name_node = node.child_by_field_name("name")
            return source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace") if name_node else ""

        def function_chunks(node, *, is_method: bool) -> None:
            target = node
            if node.type == "decorated_definition":
                target = next((child for child in node.named_children if child.type in {"function_definition", "class_definition"}), node)
            if target.type == "class_definition":
                make_chunk(node, "method" if is_method else "class", text_of_name(target))
                for child in target.named_children:
                    members = child.named_children if child.type == "block" else [child]
                    for member in members:
                        if member.type in {"function_definition", "class_definition", "decorated_definition"}:
                            function_chunks(member, is_method=True)
            else:
                make_chunk(node, "method" if is_method else "function", text_of_name(target))

        top_level = root.named_children
        if source.strip() and len(source) <= 2500:
            module_end = final_line
            chunks.append(CodeChunk(
                repository_id=repository_id,
                repository_name=repository_name,
                repository_path=repository_path,
                file_path=file_path,
                symbol=Path(file_path).stem,
                chunk_type="module",
                start_line=1,
                end_line=module_end,
                source_code=source,
            ))

        for node in top_level:
            if node.type in {"import_statement", "import_from_statement"}:
                make_chunk(node, "import")
            elif node.type in {"function_definition", "class_definition", "decorated_definition"}:
                function_chunks(node, is_method=False)
            elif node.type in {"expression_statement", "assignment", "augmented_assignment", "annotated_assignment", "type_alias_statement"}:
                make_chunk(node, "definition", text_of_name(node))

        return chunks, syntax_error
