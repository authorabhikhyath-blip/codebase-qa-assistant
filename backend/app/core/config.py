from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Codebase QA Assistant API"
    cors_origins: list[str] = ["http://localhost:3000"]
    chroma_data_dir: Path = BACKEND_ROOT / "data" / "chroma"
    embedding_cache_dir: Path = BACKEND_ROOT / "data" / "models"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5-coder:3b"
    retrieval_top_k: int = 5

    model_config = SettingsConfigDict(env_prefix="CODEQA_", env_file=".env", extra="ignore")


settings = Settings()
