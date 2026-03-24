from odoo import fields, models


class OdooChatbotMessage(models.Model):
    _name = "odoo.chatbot.message"
    _description = "Odoo Yardim Asistani Mesaji"
    _order = "create_date asc, id asc"

    session_id = fields.Many2one(
        "odoo.chatbot.session",
        string="Sohbet Oturumu",
        required=True,
        ondelete="cascade",
        index=True,
    )
    role = fields.Selection(
        [
            ("system", "Sistem"),
            ("user", "Kullanici"),
            ("assistant", "Asistan"),
        ],
        string="Rol",
        required=True,
        index=True,
    )
    content = fields.Text(string="Icerik", required=True)
    user_id = fields.Many2one("res.users", string="Kullanici", required=True, index=True)
    company_id = fields.Many2one(
        related="session_id.company_id",
        string="Sirket",
        store=True,
        index=True,
    )

    def get_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": fields.Datetime.to_string(self.create_date),
            "user_name": self.user_id.name,
        }

