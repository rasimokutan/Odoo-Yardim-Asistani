{
    "name": "Odoo Yardim Asistani",
    "version": "19.0.1.3.0",
    "category": "Services",
    "summary": "Odoo kullanim rehberligi icin yerel yapay zeka destekli sohbet asistani",
    "author": "OpenAI",
    "license": "LGPL-3",
    "depends": ["base", "web", "mail"],
    "data": [
        "security/chatbot_security.xml",
        "security/ir.model.access.csv",
        "views/chatbot_views.xml",
        "views/res_config_settings_views.xml",
        "views/rag_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "odoo_help_assistant/static/src/js/chatbot_action.js",
            "odoo_help_assistant/static/src/xml/chatbot_templates.xml",
            "odoo_help_assistant/static/src/scss/chatbot.scss",
        ],
    },
    "application": True,
    "installable": True,
}

