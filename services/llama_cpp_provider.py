from .base_provider import BaseChatProvider
from .exceptions import ChatbotServiceError


class LlamaCppProvider(BaseChatProvider):
    provider_code = "llama_cpp"

    def generate(self, messages):
        raise ChatbotServiceError(
            "llama.cpp uyumlu sunucu destegi altyapida hazir ancak bu surumde etkinlestirilmedi."
        )

