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

        def _row_col(point) -> tuple[int, int]:
            try:
                return int(point[0]), int(point[1])
            except (TypeError, IndexError):
                return int(getattr(point, "row", 0)), int(getattr(point, "column", 0))

        def make_chunk(node, chunk_type: str, symbol: str = "", parent_symbol: str = "") -> None:
            code = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            if code.strip():
                start_row, _ = _row_col(node.start_point)
                end_row, end_col = _row_col(node.end_point)
                chunks.append(CodeChunk(
                    repository_id=repository_id,
                    repository_name=repository_name,
                    repository_path=repository_path,
                    file_path=file_path,
                    symbol=symbol,
                    parent_symbol=parent_symbol,
                    chunk_type=chunk_type,
                    start_line=start_row + 1,
                    end_line=max(start_row + 1, end_row + (1 if end_col else 0)),
                    source_code=code,
                ))

        def text_of_name(node) -> str:
            name_node = node.child_by_field_name("name")
            return source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace") if name_node else ""

        def function_chunks(node, *, parent_symbol: str = "") -> None:
            target = node
            if node.type == "decorated_definition":
                target = next((child for child in node.named_children if child.type in {"function_definition", "class_definition"}), node)
            name = text_of_name(target)
            if target.type == "class_definition":
                make_chunk(node, "class", symbol=name, parent_symbol=parent_symbol)
                current_class = f"{parent_symbol}.{name}" if parent_symbol else name
                for child in target.named_children:
                    members = child.named_children if child.type == "block" else [child]
                    for member in members:
                        if member.type in {"function_definition", "class_definition", "decorated_definition"}:
                            function_chunks(member, parent_symbol=current_class)
            else:
                chunk_type = "method" if parent_symbol else "function"
                make_chunk(node, chunk_type, symbol=name, parent_symbol=parent_symbol)

        top_level = root.named_children

        # 1. Group module-level imports and preamble
        import_node_types = {"import_statement", "import_from_statement", "future_import_statement"}
        import_nodes = [node for node in top_level if node.type in import_node_types]
        if import_nodes:
            first_import = import_nodes[0]
            first_named = top_level[0]
            if first_named.type == "expression_statement" and first_named.start_byte < first_import.start_byte:
                start_byte = first_named.start_byte
                start_line = _row_col(first_named.start_point)[0] + 1
            else:
                start_byte = first_import.start_byte
                start_line = _row_col(first_import.start_point)[0] + 1

            last_import = import_nodes[-1]
            end_byte = last_import.end_byte
            last_end_row, last_end_col = _row_col(last_import.end_point)
            end_line = max(start_line, last_end_row + (1 if last_end_col else 0))

            preamble_code = source_bytes[start_byte:end_byte].decode("utf-8", errors="replace")
            if preamble_code.strip():
                chunks.append(CodeChunk(
                    repository_id=repository_id,
                    repository_name=repository_name,
                    repository_path=repository_path,
                    file_path=file_path,
                    symbol=Path(file_path).stem,
                    parent_symbol="",
                    chunk_type="module_preamble",
                    start_line=start_line,
                    end_line=end_line,
                    source_code=preamble_code,
                ))

        # 2. Extract classes, functions, and definitions
        has_function_or_class = False
        for node in top_level:
            if node.type in {"function_definition", "class_definition", "decorated_definition"}:
                has_function_or_class = True
                function_chunks(node, parent_symbol="")
            elif node.type in {"expression_statement", "assignment", "augmented_assignment", "annotated_assignment", "type_alias_statement"}:
                name = text_of_name(node)
                if name:
                    make_chunk(node, "definition", symbol=name, parent_symbol="")

        # 3. Whole-file chunk: only emit for small files that have no functions or classes (e.g. flat scripts/constants)
        if not has_function_or_class and source.strip() and len(source) <= 2500:
            if not chunks or (len(chunks) == 1 and chunks[0].chunk_type == "module_preamble" and chunks[0].end_line < final_line):
                chunks.append(CodeChunk(
                    repository_id=repository_id,
                    repository_name=repository_name,
                    repository_path=repository_path,
                    file_path=file_path,
                    symbol=Path(file_path).stem,
                    parent_symbol="",
                    chunk_type="module",
                    start_line=1,
                    end_line=final_line,
                    source_code=source,
                ))

        return chunks, syntax_error
