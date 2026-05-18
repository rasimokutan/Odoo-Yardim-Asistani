import json

from odoo import fields, models


class OdooRagChunk(models.Model):
    _name = "odoo.rag.chunk"
    _description = "Odoo Dokümantasyon Vektör Chunk"
    _order = "id asc"

    title = fields.Char("Başlık", required=True)
    source_url = fields.Char("Kaynak URL")
    section = fields.Char("Bölüm")
    content = fields.Text("İçerik", required=True)
    # Embedding 768-dim float list stored as JSON string (nomic-embed-text)
    embedding_json = fields.Text("Embedding JSON")
    chunk_index = fields.Integer("Chunk Sırası", default=0)

    def set_embedding(self, vector: list):
        self.ensure_one()
        self.embedding_json = json.dumps(vector)

    def get_embedding(self) -> list | None:
        self.ensure_one()
        if self.embedding_json:
            try:
                return json.loads(self.embedding_json)
            except (ValueError, TypeError):
                return None
        return None
