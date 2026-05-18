import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services.chatbot_service import ChatbotService
from ..services.exceptions import ChatbotServiceError

_logger = logging.getLogger(__name__)


class OdooChatbotSession(models.Model):
    _name = "odoo.chatbot.session"
    _description = "Odoo Yardim Asistani Oturumu"
    _order = "last_message_at desc, id desc"

    name = fields.Char(string="Oturum Basligi", required=True)
    user_id = fields.Many2one(
        "res.users",
        string="Olusturan Kullanici",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Sirket",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(string="Aktif", default=True)
    message_ids = fields.One2many(
        "odoo.chatbot.message",
        "session_id",
        string="Mesajlar",
        copy=False,
    )
    last_message_at = fields.Datetime(string="Son Mesaj Zamani", default=fields.Datetime.now, index=True)
    message_count = fields.Integer(string="Mesaj Sayisi", compute="_compute_message_count")
    last_message_preview = fields.Char(
        string="Son Mesaj Onizlemesi",
        compute="_compute_last_message_preview",
    )

    @api.depends("message_ids")
    def _compute_message_count(self):
        counts = {}
        if self.ids:
            counts = {
                session.id: count
                for session, count in self.env["odoo.chatbot.message"]._read_group(
                    domain=[("session_id", "in", self.ids)],
                    groupby=["session_id"],
                    aggregates=["__count"],
                )
            }
        for session in self:
            session.message_count = counts.get(session.id, 0)

    @api.depends("message_ids.content", "message_ids.create_date")
    def _compute_last_message_preview(self):
        for session in self:
            last_message = session.message_ids[-1:] if session.message_ids else self.env["odoo.chatbot.message"]
            preview = (last_message.content or "")[:90] if last_message else ""
            session.last_message_preview = preview

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = _("Yeni Yardim Sohbeti")
            vals.setdefault("user_id", self.env.user.id)
            vals.setdefault("company_id", self.env.company.id)
        return super().create(vals_list)

    @api.constrains("user_id", "company_id")
    def _check_user_company_consistency(self):
        for session in self:
            if (
                session.user_id
                and session.company_id
                and session.company_id not in session.user_id.company_ids
            ):
                raise ValidationError(
                    _("Sohbet oturumu, kullanicinin yetkili oldugu sirketlerden birine bagli olmalidir.")
                )

    def _check_session_access(self, operation):
        if not self:
            return True
        self.check_access(operation)
        return True

    @api.model
    def get_chat_service(self):
        return ChatbotService(self.env)

    @api.model
    def has_chat_access(self):
        return self.env.user.has_group("odoo_help_assistant.group_chatbot_user")

    @api.model
    def _check_chat_access(self):
        if not self.has_chat_access():
            raise AccessError(_("Bu yardim asistanini kullanma yetkiniz bulunmuyor."))

    @api.model
    def create_user_session(self, title=False):
        self._check_chat_access()
        return self.create(
            {
                "name": title or _("Yeni Yardim Sohbeti"),
                "user_id": self.env.user.id,
                "company_id": self.env.company.id,
            }
        )

    @api.model
    def get_user_session_payloads(self, limit=20):
        self._check_chat_access()
        try:
            limit = int(limit or 20)
        except (TypeError, ValueError):
            limit = 20
        limit = min(max(limit, 1), 100)
        domain = [("company_id", "in", self.env.companies.ids)]
        if not self.env.user.has_group("odoo_help_assistant.group_chatbot_manager"):
            domain.append(("user_id", "=", self.env.user.id))
        sessions = self.search(domain, limit=limit, order="last_message_at desc, id desc")
        return [session.get_payload() for session in sessions]

    def get_payload(self, include_messages=False):
        if not self:
            raise UserError(_("Istenen sohbet oturumu bulunamadi veya artik erisilemiyor."))
        self.ensure_one()
        self._check_session_access("read")
        payload = {
            "id": self.id,
            "name": self.name,
            "user_name": self.user_id.name,
            "last_message_at": fields.Datetime.to_string(self.last_message_at),
            "message_count": self.message_count,
            "last_message_preview": self.last_message_preview or "",
        }
        if include_messages:
            payload["messages"] = [message.get_payload() for message in self.message_ids]
        return payload

    def _build_session_title(self, message):
        normalized = " ".join((message or "").split())
        if not normalized:
            return _("Yeni Yardim Sohbeti")
        return normalized[:60]

    def _create_message(self, role, content):
        self.ensure_one()
        if not (content or "").strip():
            raise ValidationError(_("Bos mesaj kaydedilemez."))
        return self.env["odoo.chatbot.message"].create(
            {
                "session_id": self.id,
                "role": role,
                "content": content.strip(),
                "user_id": self.user_id.id,
            }
        )

    def _get_history_for_llm(self, limit=10):
        self.ensure_one()
        # Keep the last `limit` user+assistant messages (5 exchanges).
        # Content stored in DB is plain text, so it feeds cleanly into the LLM context.
        history = self.message_ids.sorted("create_date")[-limit:]
        return [{"role": item.role, "content": item.content} for item in history if item.role in {"user", "assistant"}]

    @api.model
    def send_chat_message(self, message, session_id=False, user_context=None):
        self._check_chat_access()
        cleaned_message = (message or "").strip()
        if not cleaned_message:
            raise UserError(_("Lutfen gondermeden once bir soru yazin."))

        session = self.browse(int(session_id)).exists() if session_id else self.create_user_session()
        if not session:
            raise UserError(_("Sohbet oturumu bulunamadi. Lutfen yeni bir sohbet baslatin."))
        session._check_session_access("write")
        if not session.message_ids:
            session.name = session._build_session_title(cleaned_message)

        session._create_message("user", cleaned_message)
        session.last_message_at = fields.Datetime.now()

        try:
            assistant_reply = self.get_chat_service().generate_reply(
                session=session,
                message=cleaned_message,
                user_context=user_context or {},
                history=session._get_history_for_llm(),
            )
        except ChatbotServiceError as exc:
            _logger.warning("Chatbot service error for session %s: %s", session.id, exc)
            raise UserError(str(exc)) from exc
        except Exception as exc:
            _logger.exception("Unexpected chatbot error on session %s", session.id)
            raise UserError(
                _("Beklenmeyen bir hata olustu. Daha sonra tekrar deneyin.")
            ) from exc

        session._create_message("assistant", assistant_reply)
        session.last_message_at = fields.Datetime.now()
        return session.get_payload(include_messages=True)
