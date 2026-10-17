import hashlib
import hmac
import json
import logging
import re

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EllaithyWhatsAppAccount(models.Model):
    _name = "ellaithy.whatsapp.account"
    _description = "WhatsApp Business Account"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)

    business_account_id = fields.Char(string="WhatsApp Business Account ID")
    phone_number_id = fields.Char(string="Phone Number ID", required=True, index=True)
    business_phone = fields.Char(string="Business Phone Number")
    graph_api_version = fields.Char(default="v24.0", required=True)
    default_country_code = fields.Char(
        string="Default Country Code",
        default="20",
        help="Digits only, e.g. 20 for Egypt. Used when a local number starts with 0.",
    )

    access_token = fields.Char(
        string="Access Token",
        groups="ellaithy_whatsapp.group_whatsapp_admin",
        copy=False,
    )
    verify_token = fields.Char(
        string="Webhook Verify Token",
        groups="ellaithy_whatsapp.group_whatsapp_admin",
        copy=False,
    )
    app_secret = fields.Char(
        string="Meta App Secret",
        groups="ellaithy_whatsapp.group_whatsapp_admin",
        copy=False,
    )

    default_team_id = fields.Many2one("ellaithy.whatsapp.team", string="Default Team")
    auto_create_contact = fields.Boolean(default=True)
    auto_create_lead = fields.Boolean(
        string="Create CRM Lead for Unknown Numbers",
        help="When an incoming number cannot be matched to an existing CRM lead, create one automatically.",
    )
    notify_assignee = fields.Boolean(default=True)

    webhook_url = fields.Char(compute="_compute_webhook_url")
    last_test_at = fields.Datetime(readonly=True)
    last_test_status = fields.Char(readonly=True)

    _sql_constraints = [
        ("phone_number_id_unique", "unique(phone_number_id)", "Phone Number ID must be unique."),
    ]

    @api.depends_context("uid")
    def _compute_webhook_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        for rec in self:
            rec.webhook_url = f"{base_url.rstrip('/')}/ellaithy_whatsapp/webhook" if base_url else False

    @api.constrains("default_country_code")
    def _check_country_code(self):
        for rec in self:
            if rec.default_country_code and not rec.default_country_code.isdigit():
                raise ValidationError(_("Default country code must contain digits only."))

    def _graph_url(self, path):
        self.ensure_one()
        version = (self.graph_api_version or "v24.0").strip("/")
        return f"https://graph.facebook.com/{version}/{path.lstrip('/')}"

    def _headers(self, json_content=True):
        self.ensure_one()
        if not self.sudo().access_token:
            raise UserError(_("Configure the Meta access token first."))
        headers = {"Authorization": f"Bearer {self.sudo().access_token}"}
        if json_content:
            headers["Content-Type"] = "application/json"
        return headers

    def _normalize_phone(self, phone):
        self.ensure_one()
        digits = re.sub(r"\D", "", phone or "")
        if not digits:
            return False
        if digits.startswith("00"):
            digits = digits[2:]
        elif digits.startswith("0") and self.default_country_code:
            digits = f"{self.default_country_code}{digits[1:]}"
        return digits

    def _request(self, method, path, **kwargs):
        self.ensure_one()
        timeout = kwargs.pop("timeout", 30)
        headers = kwargs.pop("headers", None) or self._headers(json_content="files" not in kwargs)
        response = requests.request(method, self._graph_url(path), headers=headers, timeout=timeout, **kwargs)
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}
        if not response.ok:
            message = data.get("error", {}).get("message") if isinstance(data, dict) else False
            raise UserError(_("Meta WhatsApp API error: %s") % (message or response.text or response.status_code))
        return data

    def action_test_connection(self):
        for rec in self:
            try:
                data = rec._request("GET", rec.phone_number_id)
                rec.write({
                    "last_test_at": fields.Datetime.now(),
                    "last_test_status": _("Connected: %s") % (data.get("display_phone_number") or data.get("verified_name") or rec.phone_number_id),
                })
            except Exception as exc:
                rec.write({"last_test_at": fields.Datetime.now(), "last_test_status": str(exc)})
                raise
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("WhatsApp"), "message": _("Connection test completed successfully."), "type": "success"},
        }

    def _send_payload(self, payload):
        self.ensure_one()
        return self._request("POST", f"{self.phone_number_id}/messages", data=json.dumps(payload))

    def _upload_attachment(self, attachment):
        self.ensure_one()
        attachment.ensure_one()
        if not attachment.raw:
            raise UserError(_("Attachment has no file content."))
        files = {
            "file": (
                attachment.name or "file",
                attachment.raw,
                attachment.mimetype or "application/octet-stream",
            )
        }
        data = {"messaging_product": "whatsapp"}
        return self._request(
            "POST",
            f"{self.phone_number_id}/media",
            files=files,
            data=data,
            headers=self._headers(json_content=False),
        ).get("id")

    def _download_media(self, media_id):
        self.ensure_one()
        meta = self._request("GET", str(media_id))
        url = meta.get("url")
        if not url:
            return False, False
        response = requests.get(url, headers=self._headers(json_content=False), timeout=30)
        if not response.ok:
            _logger.warning("Unable to download WhatsApp media %s: %s", media_id, response.text)
            return False, False
        return response.content, meta.get("mime_type") or response.headers.get("Content-Type")

    def _verify_signature(self, raw_body, signature_header):
        self.ensure_one()
        secret = self.sudo().app_secret
        if not secret:
            return True
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        supplied = signature_header.split("=", 1)[1]
        return hmac.compare_digest(expected, supplied)
