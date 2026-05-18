import json
import logging
import math

from .embedding_service import EmbeddingService
from .exceptions import ChatbotServiceError

_logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


try:
    import numpy as np

    def _cosine_similarity(a, b):  # noqa: F811 — faster numpy version
        va, vb = np.array(a, dtype="float32"), np.array(b, dtype="float32")
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        return float(np.dot(va, vb) / denom) if denom else 0.0

except ImportError:
    pass  # pure-Python fallback stays active


class RagRetriever:
    def __init__(self, env, base_url: str, top_k: int = 3):
        self.env = env
        self.top_k = top_k
        self.embedder = EmbeddingService(base_url)

    def retrieve(self, question: str) -> list[str]:
        """Return top_k chunk contents most similar to the question."""
        try:
            q_vec = self.embedder.embed(question)
        except ChatbotServiceError as exc:
            _logger.warning("RAG embedding failed, skipping retrieval: %s", exc)
            return []

        chunks = self.env["odoo.rag.chunk"].sudo().search(
            [("embedding_json", "!=", False)], limit=0
        )
        if not chunks:
            _logger.info("RAG: no chunks indexed yet")
            return []

        scored = []
        for chunk in chunks:
            try:
                vec = json.loads(chunk.embedding_json)
                sim = _cosine_similarity(q_vec, vec)
                scored.append((sim, chunk.title, chunk.content))
            except Exception:
                continue

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: self.top_k]
        _logger.debug("RAG top scores: %s", [round(s, 3) for s, _, _ in top])

        # Only return chunks above a minimum relevance threshold
        return [content for sim, _, content in top if sim >= 0.30]

    def build_context_block(self, question: str) -> str:
        """Build the context string to inject into the system prompt."""
        passages = self.retrieve(question)
        if not passages:
            return ""
        parts = ["Aşağıda bu soruyla ilgili Odoo dokümantasyonundan alınan bilgiler var:"]
        for i, passage in enumerate(passages, 1):
            parts.append(f"[{i}] {passage.strip()}")
        parts.append(
            "Yukarıdaki bilgileri kullanarak cevap ver. "
            "Eğer bilgi yetersizse bunu belirt."
        )
        return "\n\n".join(parts)
