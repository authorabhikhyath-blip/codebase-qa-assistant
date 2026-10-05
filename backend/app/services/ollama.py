from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import httpx

from app.core.config import settings


class OllamaUnavailable(RuntimeError):
    pass


class LocalOllamaService:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        if self.model.endswith(":cloud"):
            raise ValueError("Ollama cloud models are not allowed; configure a locally installed model instead.")
        host = urlparse(self.base_url).hostname
        try:
            is_loopback = bool(host and ipaddress.ip_address(host).is_loopback)
        except ValueError:
            is_loopback = host == "localhost"
        if not is_loopback:
            raise ValueError("Ollama must use a local loopback URL; remote model endpoints are not allowed.")

    def status(self) -> dict[str, object]:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
            response.raise_for_status()
            models = response.json().get("models", [])
            names = {
                str(item.get("name", ""))
                for item in models
                if not item.get("remote_model") and not item.get("remote_host")
                and not str(item.get("name", "")).endswith(":cloud")
            }
            model_available = self.model in names
            if model_available:
                detail = f"Ollama is ready with {self.model}."
            else:
                detail = f"Ollama is running, but {self.model} is not installed. Run: ollama pull {self.model}"
            return {"available": True, "model": self.model, "model_available": model_available, "detail": detail}
        except (httpx.HTTPError, ValueError) as error:
            return {
                "available": False,
                "model": self.model,
                "model_available": False,
                "detail": f"Ollama is unavailable at {self.base_url}. Install/start Ollama locally. {error}",
            }

    def generate(self, prompt: str) -> str:
        state = self.status()
        if not state["available"]:
            raise OllamaUnavailable(str(state["detail"]))
        if not state["model_available"]:
            raise OllamaUnavailable(str(state["detail"]))
        try:
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0.2}},
                timeout=180.0,
            )
            response.raise_for_status()
            answer = response.json().get("response", "").strip()
            if not answer:
                raise OllamaUnavailable("Ollama returned an empty answer.")
            return answer
        except httpx.HTTPError as error:
            raise OllamaUnavailable(f"Ollama answer generation failed: {error}") from error
