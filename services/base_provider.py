from .exceptions import ChatbotServiceError


class BaseChatProvider:
    provider_code = None

    def __init__(self, config):
        self.config = config

    def generate(self, messages):
        raise NotImplementedError

    def _validate_response_text(self, content):
        if not (content or "").strip():
            raise ChatbotServiceError(
                "Model bos bir cevap dondurdu. Model adini ve servis kaydini kontrol edin."
            )
        return content.strip()

