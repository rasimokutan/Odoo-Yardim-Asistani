from unittest.mock import Mock, patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOdooHelpAssistant(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user_group = cls.env.ref("odoo_help_assistant.group_chatbot_user")
        manager_group = cls.env.ref("odoo_help_assistant.group_chatbot_manager")

        cls.chat_user = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Chat Kullanici",
                "login": "chat_user",
                "email": "chat_user@example.com",
                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id, user_group.id])],
            }
        )
        cls.chat_manager = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Chat Yonetici",
                "login": "chat_manager",
                "email": "chat_manager@example.com",
                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id, manager_group.id])],
            }
        )
        cls.other_chat_user = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Diger Chat Kullanici",
                "login": "other_chat_user",
                "email": "other_chat_user@example.com",
                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id, user_group.id])],
            }
        )

    def test_session_creation_and_message_storage(self):
        session_model = self.env["odoo.chatbot.session"].with_user(self.chat_user)
        session = session_model.create_user_session("Stok Yardimi")
        session._create_message("user", "Stok transferi nasil onaylanir?")
        session._create_message("assistant", "Transfer kaydini acip Dogrula dugmesini kullanin.")

        self.assertEqual(session.user_id, self.chat_user)
        self.assertEqual(session.message_count, 2)
        self.assertEqual(session.message_ids[0].role, "user")
        self.assertEqual(session.message_ids[1].role, "assistant")

    def test_record_rule_blocks_other_user_access(self):
        session = self.env["odoo.chatbot.session"].with_user(self.chat_user).create_user_session("Muhasebe")
        with self.assertRaises(AccessError):
            self.env["odoo.chatbot.session"].with_user(self.other_chat_user).browse(session.id).check_access_rule("read")

    def test_manager_can_read_sessions(self):
        session = self.env["odoo.chatbot.session"].with_user(self.chat_user).create_user_session("Satis")
        manager_session = self.env["odoo.chatbot.session"].with_user(self.chat_manager).browse(session.id)
        manager_session.check_access_rule("read")

    def test_service_reads_configuration(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("odoo_help_assistant.model_name", "test-model")
        params.set_param("odoo_help_assistant.timeout", 99)

        service = self.env["odoo.chatbot.session"].get_chat_service()
        config = service.get_config()

        self.assertEqual(config["model_name"], "test-model")
        self.assertEqual(config["timeout"], 99)

    def test_ollama_provider_success(self):
        response = Mock()
        response.json.return_value = {"message": {"content": "Merhaba, nasil yardimci olabilirim?"}}
        response.raise_for_status.return_value = None

        service = self.env["odoo.chatbot.session"].get_chat_service()
        with patch("odoo.addons.odoo_help_assistant.services.ollama_provider.requests.post", return_value=response):
            answer = service.generate_reply(
                session=self.env["odoo.chatbot.session"],
                message="Satis teklifi nasil onaylanir?",
                user_context={},
                history=[],
            )
        self.assertIn("yardimci", answer.lower())
