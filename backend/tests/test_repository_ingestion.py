from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.repository_ingestion import RepositoryScanError, scan_repository


client = TestClient(app)


def test_scan_valid_repository_returns_python_statistics(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("project\n", encoding="utf-8")

    response = client.post("/api/repositories/scan", json={"path": str(tmp_path)})

    assert response.status_code == 200
    result = response.json()
    assert result["repository_name"] == tmp_path.name
    assert result["python_file_count"] == 1
    assert result["total_line_count"] == 2
    assert result["total_discovered_files"] == 2
    assert result["scan_status"] == "completed"
    assert result["discovered_files"] == [{"path": "src/main.py", "line_count": 2}]


def test_scan_rejects_missing_path() -> None:
    response = client.post("/api/repositories/scan", json={"path": "Z:/path/that/does/not/exist"})

    assert response.status_code == 400
    assert "cannot be accessed" in response.json()["detail"]


def test_scan_rejects_malformed_path() -> None:
    response = client.post("/api/repositories/scan", json={"path": "bad\u0000path"})

    assert response.status_code == 400
    assert "cannot be accessed" in response.json()["detail"]


def test_scan_rejects_file_path(tmp_path: Path) -> None:
    source = tmp_path / "script.py"
    source.write_text("pass\n", encoding="utf-8")

    with pytest.raises(RepositoryScanError, match="must point to a directory") as error:
        scan_repository(str(source))

    assert error.value.status_code == 400


@pytest.mark.parametrize("ignored", [".git", ".pnpm-store", ".npm", ".yarn", "node_modules", "__pycache__", ".venv", "venv", "env", "dist", "build", ".next", "coverage"])
def test_scan_ignores_generated_directories(tmp_path: Path, ignored: str) -> None:
    hidden = tmp_path / ignored
    hidden.mkdir()
    (hidden / "ignored.py").write_text("ignored = True\n", encoding="utf-8")

    result = scan_repository(str(tmp_path))

    assert result["python_file_count"] == 0
    assert result["total_discovered_files"] == 0


def test_scan_counts_blank_and_final_unterminated_lines(tmp_path: Path) -> None:
    (tmp_path / "lines.py").write_text("first = 1\n\nlast = 3", encoding="utf-8")

    result = scan_repository(str(tmp_path))

    assert result["total_line_count"] == 3
    assert result["discovered_files"] == [{"path": "lines.py", "line_count": 3}]


def test_scan_counts_nested_non_python_files(tmp_path: Path) -> None:
    nested = tmp_path / "assets"
    nested.mkdir()
    (nested / "data.txt").write_text("data", encoding="utf-8")

    result = scan_repository(str(tmp_path))

    assert result["python_file_count"] == 0
    assert result["total_discovered_files"] == 1
