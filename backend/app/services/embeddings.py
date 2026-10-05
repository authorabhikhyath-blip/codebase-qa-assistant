from __future__ import annotations

from functools import lru_cache
from threading import Lock

from app.core.config import settings


class EmbeddingServiceError(RuntimeError):
    pass


class LocalEmbeddingService:
    """Lazy, cached FastEmbed model. Model weights are downloaded once to local disk."""

    def __init__(self, model_name: str, cache_dir: str) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model = None
        self._lock = Lock()

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from fastembed import TextEmbedding

                        self._model = TextEmbedding(model_name=self.model_name, cache_dir=self.cache_dir)
                    except Exception as error:
                        raise EmbeddingServiceError(
                            f"Could not load local embedding model '{self.model_name}'. "
                            f"Check model name and local model download access: {error}"
                        ) from error
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            return [vector.tolist() for vector in self._get_model().embed(texts, batch_size=32)]
        except EmbeddingServiceError:
            raise
        except Exception as error:
            raise EmbeddingServiceError(f"Local document embedding failed: {error}") from error

    def embed_query(self, text: str) -> list[float]:
        try:
            model = self._get_model()
            query_method = getattr(model, "query_embed", None)
            vector = next(query_method([text])) if query_method else next(model.embed([text]))
            return vector.tolist()
        except EmbeddingServiceError:
            raise
        except Exception as error:
            raise EmbeddingServiceError(f"Local query embedding failed: {error}") from error


@lru_cache(maxsize=4)
def get_embedding_service(model_name: str | None = None, cache_dir: str | None = None) -> LocalEmbeddingService:
    return LocalEmbeddingService(model_name or settings.embedding_model, cache_dir or str(settings.embedding_cache_dir))
