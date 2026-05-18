import logging

from odoo import _

from .exceptions import ChatbotServiceError
from .intent_detector import INTENT_ODOO, detect_intent
from .llama_cpp_provider import LlamaCppProvider
from .odoo_hints import build_hint_block
from .ollama_provider import OllamaProvider
from .prompt_templates import PROMPT_TEMPLATES
from .rag_retriever import RagRetriever

_logger = logging.getLogger(__name__)

_FALLBACK_REPLY = (
    "Üzgünüm, şu anda bir yanıt üretemiyorum. "
    "Lütfen sorunuzu farklı bir şekilde sormayı deneyin veya daha sonra tekrar deneyin."
)


class ChatbotService:
    def __init__(self, env):
        self.env = env
        self.params = env["ir.config_parameter"].sudo()

    def _get_bool(self, key, default=False):
        raw = self.params.get_param(key, default)
        if isinstance(raw, bool):
            return raw
        if raw is None:
            return default
        return str(raw).lower() in {"1", "true", "yes", "on"}

    def _get_int(self, key, default):
        try:
            return int(self.params.get_param(key, default))
        except (TypeError, ValueError):
            return default

    def _get_float(self, key, default):
        try:
            return float(self.params.get_param(key, default))
        except (TypeError, ValueError):
            return default

    def is_enabled(self):
        return self._get_bool("odoo_help_assistant.chatbot_enabled", True)

    def get_config(self):
        return {
            "enabled": self.is_enabled(),
            "provider": self.params.get_param("odoo_help_assistant.chatbot_provider", "ollama"),
            "base_url": self.params.get_param("odoo_help_assistant.ollama_base_url", "http://127.0.0.1:11434"),
            "model_name": self.params.get_param("odoo_help_assistant.model_name", "llama3.2:3b"),
            "temperature": self._get_float("odoo_help_assistant.temperature", 0.2),
            "max_tokens": self._get_int("odoo_help_assistant.max_tokens", 300),
            "timeout": self._get_int("odoo_help_assistant.timeout", 120),
            "system_prompt": self.params.get_param("odoo_help_assistant.system_prompt", ""),
            "include_user_context": self._get_bool("odoo_help_assistant.include_user_context", True),
            "hint_layer_enabled": self._get_bool("odoo_help_assistant.hint_layer_enabled", True),
        }

    def _get_provider(self, config):
        provider_map = {
            "ollama": OllamaProvider,
            "llama_cpp": LlamaCppProvider,
        }
        provider_class = provider_map.get(config["provider"])
        if not provider_class:
            raise ChatbotServiceError(_("Desteklenmeyen yapay zeka saglayicisi secildi."))
        return provider_class(config)

    def _build_system_message(self, question, user_context):
        intent = detect_intent(question)
        config = self.get_config()

        # Pick the intent-specific template; fall back to the admin-configured prompt
        base_prompt = PROMPT_TEMPLATES.get(intent) or config["system_prompt"].strip()
        prompt_parts = [base_prompt]

        # User context, RAG retrieval and domain hints only for Odoo questions
        if intent == INTENT_ODOO:
            if config["include_user_context"]:
                user = self.env.user
                ctx_lines = [
                    "Bağlam bilgileri:",
                    f"- Kullanıcı adı: {user.name}",
                    f"- Kullanıcı dili: {user.lang or 'tr_TR'}",
                    f"- Şirket: {self.env.company.name}",
                ]
                if user_context.get("active_menu"):
                    ctx_lines.append(
                        f"- Kullanıcı şu anda şu menüyle ilgili yardım istiyor olabilir: {user_context['active_menu']}"
                    )
                if user_context.get("active_model"):
                    ctx_lines.append(f"- İlgili model veya ekran: {user_context['active_model']}")
                prompt_parts.append("\n".join(ctx_lines))

            # RAG: inject relevant documentation passages
            try:
                retriever = RagRetriever(self.env, config["base_url"])
                rag_block = retriever.build_context_block(question)
                if rag_block:
                    prompt_parts.append(rag_block)
            except Exception:
                _logger.warning("RAG retrieval failed, continuing without context")

            if config["hint_layer_enabled"]:
                hints = build_hint_block(question)
                if hints:
                    prompt_parts.append(
                        "Odoo için hazır ipuçları:\n" + "\n".join(f"- {hint}" for hint in hints)
                    )

        return {"role": "system", "content": "\n\n".join(p for p in prompt_parts if p)}

    def generate_reply(self, session, message, user_context, history):
        config = self.get_config()
        if not config["enabled"]:
            raise ChatbotServiceError(_("Yardim asistani ayarlardan pasif durumdadir."))
        if not config["model_name"]:
            raise ChatbotServiceError(_("Model adi tanimli degil. Lutfen ayarlari kontrol edin."))
        if config["provider"] == "ollama" and not config["base_url"]:
            raise ChatbotServiceError(_("Ollama adresi bos birakilamaz."))

        messages = [self._build_system_message(message, user_context)]
        messages.extend(history or [])
        if not history or history[-1]["role"] != "user" or history[-1]["content"] != message:
            messages.append({"role": "user", "content": message})

        provider = self._get_provider(config)

        try:
            raw_reply = provider.generate(messages)
        except ChatbotServiceError:
            raise
        except Exception as exc:
            _logger.exception("Unexpected provider error")
            raise ChatbotServiceError(_FALLBACK_REPLY) from exc

        if not (raw_reply or "").strip():
            _logger.warning("Provider returned empty reply for session %s", session.id)
            return _FALLBACK_REPLY

        return raw_reply
