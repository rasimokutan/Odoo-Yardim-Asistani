import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.doc_indexer import DocIndexer

_logger = logging.getLogger(__name__)


class IndexDocsWizard(models.TransientModel):
    _name = "odoo.rag.index.wizard"
    _description = "Odoo Dokümantasyonu İndeksleme Sihirbazı"

    branch = fields.Selection(
        [("19.0", "Odoo 19.0"), ("18.0", "Odoo 18.0"), ("17.0", "Odoo 17.0")],
        string="Odoo Sürümü",
        default="19.0",
        required=True,
    )
    max_files = fields.Integer(
        string="Maksimum Dosya Sayısı",
        default=150,
        help="Dokümantasyon repo'sundan işlenecek RST dosya sayısı. "
             "150 dosya ≈ 600-800 chunk ≈ 5-8 dakika sürer. "
             "İlk seferde repo lokale klonlanır (~50 MB).",
    )
    state = fields.Selection(
        [("draft", "Hazır"), ("done", "Tamamlandı")],
        default="draft",
    )
    result_summary = fields.Text(string="Sonuç", readonly=True)

    @api.model
    def _get_base_url(self):
        params = self.env["ir.config_parameter"].sudo()
        return params.get_param("odoo_help_assistant.ollama_base_url", "http://127.0.0.1:11434")

    def action_start_indexing(self):
        self.ensure_one()
        if self.max_files < 1 or self.max_files > 1000:
            raise UserError(_("Dosya sayısı 1 ile 1000 arasında olmalıdır."))

        base_url = self._get_base_url()
        indexer = DocIndexer(
            env=self.env,
            base_url=base_url,
            branch=self.branch,
            max_files=self.max_files,
        )

        try:
            result = indexer.run()
        except Exception as exc:
            _logger.exception("Indexing failed")
            raise UserError(_("İndeksleme sırasında hata oluştu: %s") % exc) from exc

        chunk_count = self.env["odoo.rag.chunk"].sudo().search_count([])
        summary = (
            f"İndeksleme tamamlandı.\n"
            f"Toplam chunk: {chunk_count}\n"
            f"Yeni eklenen: {result['indexed']}\n"
            f"Atlanan dosya: {result['skipped']}\n"
            f"Hata: {result['errors']}"
        )
        self.write({"state": "done", "result_summary": summary})

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_clear_index(self):
        count = self.env["odoo.rag.chunk"].sudo().search_count([])
        self.env["odoo.rag.chunk"].sudo().search([]).unlink()
        self.result_summary = f"{count} chunk silindi."
        self.state = "done"
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
