import logging

import requests

from .base_provider import BaseChatProvider
from .exceptions import ChatbotServiceError

_logger = logging.getLogger(__name__)


class OllamaProvider(BaseChatProvider):
    provider_code = "ollama"

    def generate(self, messages):
        url = f"{self.config['base_url'].rstrip('/')}/api/chat"
        payload = {
            "model": self.config["model_name"],
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config["temperature"],
                "num_predict": self.config["max_tokens"],
            },
        }
        try:
            response = requests.post(url, json=payload, timeout=self.config["timeout"])
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise ChatbotServiceError(
                "Ollama istegi zaman asimina ugradi. Zaman asimi degerini artirip yeniden deneyin."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise ChatbotServiceError(
                "Ollama servisine baglanilamadi. Ollama servisinin calistigini ve yapilandirilan adresin dogru oldugunu kontrol edin."
            ) from exc
        except requests.exceptions.HTTPError as exc:
            body = exc.response.text[:240] if exc.response is not None else ""
            _logger.warning("Ollama HTTP error: %s", body)
            raise ChatbotServiceError(
                "Ollama istegi basarisiz oldu. Model adini ve servis kaydini kontrol edin."
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise ChatbotServiceError(
                "Ollama servisine erisirken bir ag hatasi olustu."
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ChatbotServiceError(
                "Ollama gecersiz bir yanit dondurdu. JSON cevabi okunamadi."
            ) from exc

        return self._validate_response_text(data.get("message", {}).get("content"))

