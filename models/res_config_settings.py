from odoo import fields, models


DEFAULT_SYSTEM_PROMPT = """Sen Odoo Yardim Asistani adli bir Odoo fonksiyonel destek asistanisin.
- Varsayilan cevap dilin Turkcedir.
- Kullanici acikca farkli bir dil isterse o dilde cevap verebilirsin.
- Odoo kullanim adimlarini pratik ve kisa sekilde anlat.
- Emin olmadigin menu yolu veya ekran davranisi varsa bunu acikca belirt.
- Yapilmamis islemleri yapildi gibi anlatma.
- Uygun oldugunda adim adim yonlendirme ver.
- Odoo surumu veya ozel gelistirmeler nedeniyle ekranlar farkliysa bunu hatirlat.
- Teknik kod uretmeye calisma; son kullaniciyi Odoo icinde yonlendir.
- Gereksiz teori yerine uygulanabilir yardim sun.
"""


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    chatbot_enabled = fields.Boolean(
        string="Yardim asistani aktif",
        config_parameter="odoo_help_assistant.chatbot_enabled",
        default=True,
    )
    chatbot_provider = fields.Selection(
        [
            ("ollama", "Ollama"),
            ("llama_cpp", "llama.cpp Uyumlu Sunucu"),
        ],
        string="LLM saglayicisi",
        config_parameter="odoo_help_assistant.chatbot_provider",
        default="ollama",
    )
    chatbot_ollama_base_url = fields.Char(
        string="Ollama adresi",
        config_parameter="odoo_help_assistant.ollama_base_url",
        default="http://127.0.0.1:11434",
    )
    chatbot_model_name = fields.Char(
        string="Model adi",
        config_parameter="odoo_help_assistant.model_name",
        default="llama3.2:3b",
    )
    chatbot_temperature = fields.Float(
        string="Yaraticilik seviyesi",
        config_parameter="odoo_help_assistant.temperature",
        default=0.2,
    )
    chatbot_max_tokens = fields.Integer(
        string="Azami cevap uzunlugu",
        config_parameter="odoo_help_assistant.max_tokens",
        default=300,
    )
    chatbot_timeout = fields.Integer(
        string="Zaman asimi (saniye)",
        config_parameter="odoo_help_assistant.timeout",
        default=45,
    )
    chatbot_system_prompt = fields.Text(
        string="Sistem yonlendirmesi",
        default=DEFAULT_SYSTEM_PROMPT,
    )
    chatbot_include_user_context = fields.Boolean(
        string="Kullanici baglamini ekle",
        config_parameter="odoo_help_assistant.include_user_context",
        default=True,
    )
    chatbot_hint_layer_enabled = fields.Boolean(
        string="Hazir Odoo ipuclari katmanini kullan",
        config_parameter="odoo_help_assistant.hint_layer_enabled",
        default=True,
    )

    def get_values(self):
        res = super().get_values()
        params = self.env["ir.config_parameter"].sudo()
        res.update(
            chatbot_system_prompt=params.get_param(
                "odoo_help_assistant.system_prompt",
                DEFAULT_SYSTEM_PROMPT,
            )
        )
        return res

    def set_values(self):
        super().set_values()
        self.env["ir.config_parameter"].sudo().set_param(
            "odoo_help_assistant.system_prompt",
            self.chatbot_system_prompt or DEFAULT_SYSTEM_PROMPT,
        )
