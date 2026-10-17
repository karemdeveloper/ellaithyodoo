import json
import logging

from werkzeug.wrappers import Response

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class EllaithyWhatsAppWebhook(http.Controller):

    @http.route("/ellaithy_whatsapp/webhook", type="http", auth="public", methods=["GET"], csrf=False)
    def verify_webhook(self, **kwargs):
        mode = request.httprequest.args.get("hub.mode")
        token = request.httprequest.args.get("hub.verify_token")
        challenge = request.httprequest.args.get("hub.challenge")
        if mode == "subscribe" and token:
            account = request.env["ellaithy.whatsapp.account"].sudo().search([
                ("active", "=", True), ("verify_token", "=", token)
            ], limit=1)
            if account:
                return Response(challenge or "", status=200, content_type="text/plain")
        return Response("Forbidden", status=403, content_type="text/plain")

    @http.route("/ellaithy_whatsapp/webhook", type="http", auth="public", methods=["POST"], csrf=False)
    def receive_webhook(self, **kwargs):
        raw_body = request.httprequest.get_data() or b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            return Response("Invalid JSON", status=400)

        entries = payload.get("entry") or []
        for entry in entries:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                metadata = value.get("metadata") or {}
                phone_number_id = metadata.get("phone_number_id")
                if not phone_number_id:
                    continue
                account = request.env["ellaithy.whatsapp.account"].sudo().search([
                    ("active", "=", True), ("phone_number_id", "=", str(phone_number_id))
                ], limit=1)
                if not account:
                    _logger.warning("WhatsApp webhook received for unknown phone_number_id %s", phone_number_id)
                    continue
                signature = request.httprequest.headers.get("X-Hub-Signature-256")
                if not account._verify_signature(raw_body, signature):
                    _logger.warning("Rejected WhatsApp webhook because signature validation failed for account %s", account.id)
                    return Response("Invalid signature", status=403)

                contacts = value.get("contacts") or []
                contact_map = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in contacts}
                for msg in value.get("messages") or []:
                    sender = msg.get("from")
                    if not sender:
                        continue
                    conversation = request.env["ellaithy.whatsapp.conversation"].sudo().get_or_create_for_incoming(
                        account, sender, contact_name=contact_map.get(sender), wa_id=sender
                    )
                    request.env["ellaithy.whatsapp.message"].sudo().create_from_webhook(
                        account, conversation, msg, contact_name=contact_map.get(sender)
                    )

                for status in value.get("statuses") or []:
                    request.env["ellaithy.whatsapp.message"].sudo().update_status_from_webhook(status)

        return Response("EVENT_RECEIVED", status=200, content_type="text/plain")
