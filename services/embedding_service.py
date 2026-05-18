import logging

import requests

from .exceptions import ChatbotServiceError

_logger = logging.getLogger(__name__)

# nomic-embed-text produces 768-dimensional vectors
DEFAULT_EMBED_MODEL = "nomic-embed-text"


class EmbeddingService:
    def __init__(self, base_url: str, model: str = DEFAULT_EMBED_MODEL, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, text: str) -> list[float]:
        url = f"{self.base_url}/api/embed"
        try:
            response = requests.post(
                url,
                json={"model": self.model, "input": text},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings") or data.get("embedding")
            if not embeddings:
                raise ChatbotServiceError("Ollama embed API boş yanıt döndürdü.")
            # /api/embed returns {"embeddings": [[...]]}
            if isinstance(embeddings[0], list):
                return embeddings[0]
            return embeddings
        except ChatbotServiceError:
            raise
        except requests.exceptions.Timeout as exc:
            raise ChatbotServiceError("Embedding isteği zaman aşımına uğradı.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise ChatbotServiceError("Ollama servisine bağlanılamadı.") from exc
        except Exception as exc:
            _logger.exception("Embedding error")
            raise ChatbotServiceError(f"Embedding hatası: {exc}") from exc
