from odoo.exceptions import UserError

from odoo import http
from odoo.http import request


class OdooHelpAssistantController(http.Controller):
    def _service(self):
        return request.env["odoo.chatbot.session"].with_user(request.env.user).get_chat_service()

    @http.route("/odoo_help_assistant/chat/bootstrap", type="jsonrpc", auth="user")
    def chatbot_bootstrap(self):
        service = self._service()
        can_use_chatbot = request.env["odoo.chatbot.session"].has_chat_access()
        return {
            "can_use_chatbot": can_use_chatbot,
            "sessions": request.env["odoo.chatbot.session"].get_user_session_payloads() if can_use_chatbot else [],
            "current_user": {
                "name": request.env.user.name,
                "lang": request.env.user.lang or "tr_TR",
            },
            "chatbot_enabled": service.is_enabled(),
        }

    @http.route("/odoo_help_assistant/chat/session/create", type="jsonrpc", auth="user")
    def create_session(self):
        session = request.env["odoo.chatbot.session"].create_user_session()
        return session.get_payload(include_messages=True)

    @http.route("/odoo_help_assistant/chat/session/load", type="jsonrpc", auth="user")
    def load_session(self, session_id):
        session = request.env["odoo.chatbot.session"].browse(int(session_id)).exists()
        if not session:
            raise UserError("Sohbet oturumu bulunamadi. Listeyi yenileyip tekrar deneyin.")
        session._check_session_access("read")
        return session.get_payload(include_messages=True)

    @http.route("/odoo_help_assistant/chat/send", type="jsonrpc", auth="user")
    def send_message(self, message, session_id=False, user_context=None):
        return request.env["odoo.chatbot.session"].send_chat_message(
            message=message,
            session_id=session_id,
            user_context=user_context or {},
        )
