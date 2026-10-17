import base64
import json

from odoo import _, api, fields, models


class EllaithyWhatsAppMessage(models.Model):
    _name = "ellaithy.whatsapp.message"
    _description = "WhatsApp Message"
    _order = "message_date desc, id desc"

    conversation_id = fields.Many2one("ellaithy.whatsapp.conversation", required=True, ondelete="cascade", index=True)
    account_id = fields.Many2one(related="conversation_id.account_id", store=True, index=True)
    direction = fields.Selection([("inbound", "Inbound"), ("outbound", "Outbound")], required=True, index=True)
    message_type = fields.Selection(
        [("text", "Text"), ("image", "Image"), ("document", "Document"), ("audio", "Audio"), ("video", "Video"), ("location", "Location"), ("template", "Template"), ("interactive", "Interactive"), ("unknown", "Unknown")],
        default="text",
        required=True,
    )
    body = fields.Text()
    attachment_id = fields.Many2one("ir.attachment", ondelete="set null")
    meta_message_id = fields.Char(index=True, copy=False)
    status = fields.Selection(
        [("received", "Received"), ("queued", "Queued"), ("sent", "Sent"), ("delivered", "Delivered"), ("read", "Read"), ("failed", "Failed")],
        default="received",
        required=True,
        index=True,
    )
    error_message = fields.Text()
    message_date = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    sent_by_id = fields.Many2one("res.users")
    raw_payload = fields.Text(groups="ellaithy_whatsapp.group_whatsapp_admin")
    template_id = fields.Many2one("ellaithy.whatsapp.template")
    report_count = fields.Integer(string="Messages", default=1, readonly=True)

    _sql_constraints = [
        ("meta_message_id_unique", "unique(meta_message_id)", "Meta message ID must be unique."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            preview = (rec.body or rec.message_type or "")[:160]
            values = {"last_message_at": rec.message_date, "last_message_preview": preview}
            if rec.direction == "inbound":
                values["unread_count"] = rec.conversation_id.unread_count + 1
                if rec.conversation_id.state == "new":
                    values["state"] = "open"
            elif rec.direction == "outbound" and not rec.conversation_id.first_response_at:
                values["first_response_at"] = rec.message_date
            rec.conversation_id.sudo().write(values)
            rec._post_to_linked_records()
            if rec.direction == "inbound" and rec.conversation_id.account_id.notify_assignee and rec.conversation_id.assigned_user_id:
                rec.conversation_id.sudo().message_post(
                    body=_("New WhatsApp message from %s: %s") % (rec.conversation_id.contact_name or rec.conversation_id.phone, preview),
                    partner_ids=[rec.conversation_id.assigned_user_id.partner_id.id],
                )
        return records

    def _post_to_linked_records(self):
        for rec in self:
            conv = rec.conversation_id
            direction = _("Incoming") if rec.direction == "inbound" else _("Outgoing")
            body = _("<b>WhatsApp %s</b><br/>%s") % (direction, rec.body or _("Media message"))
            attachment_ids = [rec.attachment_id.id] if rec.attachment_id else []
            for target in (conv.crm_lead_id, conv.complaint_id, conv.helpdesk_ticket_id):
                if target and hasattr(target, "message_post"):
                    target.sudo().message_post(body=body, attachment_ids=attachment_ids)

    @api.model
    def create_from_webhook(self, account, conversation, msg, contact_name=None):
        meta_id = msg.get("id")
        existing = self.sudo().search([("meta_message_id", "=", meta_id)], limit=1) if meta_id else self.env[self._name]
        if existing:
            return existing
        msg_type = msg.get("type") or "unknown"
        body = False
        attachment_id = False
        if msg_type == "text":
            body = (msg.get("text") or {}).get("body")
        elif msg_type in ("image", "document", "audio", "video"):
            media = msg.get(msg_type) or {}
            body = media.get("caption") or media.get("filename") or _("%s attachment") % msg_type.title()
            media_id = media.get("id")
            if media_id:
                content, mimetype = account._download_media(media_id)
                if content:
                    attachment = self.env["ir.attachment"].sudo().create({
                        "name": media.get("filename") or f"whatsapp_{media_id}",
                        "datas": base64.b64encode(content),
                        "mimetype": mimetype,
                        "res_model": "ellaithy.whatsapp.conversation",
                        "res_id": conversation.id,
                    })
                    attachment_id = attachment.id
        elif msg_type == "location":
            loc = msg.get("location") or {}
            body = _("Location: %(lat)s, %(lng)s %(name)s") % {
                "lat": loc.get("latitude", ""),
                "lng": loc.get("longitude", ""),
                "name": loc.get("name") or "",
            }
        elif msg_type == "interactive":
            interactive = msg.get("interactive") or {}
            reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
            body = reply.get("title") or reply.get("id") or json.dumps(interactive)
        else:
            body = json.dumps(msg, ensure_ascii=False)

        timestamp = msg.get("timestamp")
        date = fields.Datetime.now()
        if timestamp:
            try:
                from datetime import datetime, timezone
                date = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).replace(tzinfo=None)
            except Exception:
                pass
        return self.sudo().create({
            "conversation_id": conversation.id,
            "direction": "inbound",
            "message_type": msg_type if msg_type in dict(self._fields["message_type"].selection) else "unknown",
            "body": body,
            "attachment_id": attachment_id,
            "meta_message_id": meta_id,
            "status": "received",
            "message_date": date,
            "raw_payload": json.dumps(msg, ensure_ascii=False),
        })

    @api.model
    def update_status_from_webhook(self, status_data):
        meta_id = status_data.get("id")
        if not meta_id:
            return False
        rec = self.sudo().search([("meta_message_id", "=", meta_id)], limit=1)
        if not rec:
            return False
        status = status_data.get("status")
        vals = {}
        if status in ("sent", "delivered", "read", "failed"):
            vals["status"] = status
        errors = status_data.get("errors") or []
        if errors:
            vals["error_message"] = "; ".join(e.get("title") or e.get("message") or str(e) for e in errors)
        if vals:
            rec.write(vals)
        return rec
