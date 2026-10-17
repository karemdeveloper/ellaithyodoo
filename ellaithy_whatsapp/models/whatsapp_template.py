import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EllaithyWhatsAppTemplate(models.Model):
    _name = "ellaithy.whatsapp.template"
    _description = "WhatsApp Message Template"
    _order = "name"

    name = fields.Char(required=True, help="Friendly name used inside Odoo.")
    meta_name = fields.Char(string="Meta Template Name", required=True)
    account_id = fields.Many2one("ellaithy.whatsapp.account", required=True, ondelete="cascade")
    language_code = fields.Char(default="en", required=True)
    category = fields.Selection(
        [("marketing", "Marketing"), ("utility", "Utility"), ("authentication", "Authentication")],
        default="utility",
    )
    body_preview = fields.Text(string="Body Preview")
    variable_count = fields.Integer(default=0)
    active = fields.Boolean(default=True)
    notes = fields.Text()

    _sql_constraints = [
        ("template_account_name_unique", "unique(account_id, meta_name, language_code)", "Template name/language must be unique per account."),
    ]

    @api.constrains("variable_count")
    def _check_variable_count(self):
        for rec in self:
            if rec.variable_count < 0:
                raise ValidationError(_("Variable count cannot be negative."))

    def build_payload(self, to, values=None):
        self.ensure_one()
        values = values or []
        components = []
        if values:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": str(value)} for value in values],
            })
        return {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": self.meta_name,
                "language": {"code": self.language_code},
                "components": components,
            },
        }
