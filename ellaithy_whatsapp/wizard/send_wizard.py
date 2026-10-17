import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EllaithyWhatsAppSendWizard(models.TransientModel):
    _name = "ellaithy.whatsapp.send.wizard"
    _description = "Send WhatsApp Message"

    conversation_id = fields.Many2one("ellaithy.whatsapp.conversation", required=True)
    mode = fields.Selection([("text", "Text"), ("template", "Template"), ("media", "Media")], default="text", required=True)
    body = fields.Text()
    template_id = fields.Many2one("ellaithy.whatsapp.template")
    template_values = fields.Char(
        string="Template Variables",
        help='Comma-separated values in order, e.g. "Ahmed,COMP/00123".',
    )
    attachment_id = fields.Many2one("ir.attachment")
    media_type = fields.Selection([("image", "Image"), ("document", "Document"), ("audio", "Audio"), ("video", "Video")], default="document")
    caption = fields.Text()

    @api.onchange("conversation_id")
    def _onchange_conversation(self):
        if self.conversation_id:
            return {"domain": {"template_id": [("account_id", "=", self.conversation_id.account_id.id), ("active", "=", True)]}}

    def action_send(self):
        self.ensure_one()
        conv = self.conversation_id
        account = conv.account_id
        to = account._normalize_phone(conv.phone)
        payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to}
        body_for_log = self.body or self.caption or ""
        attachment_id = False
        template_id = False
        msg_type = self.mode

        if self.mode == "text":
            if not self.body:
                raise ValidationError(_("Enter a message."))
            payload.update({"type": "text", "text": {"preview_url": True, "body": self.body}})
        elif self.mode == "template":
            if not self.template_id:
                raise ValidationError(_("Select a WhatsApp template."))
            values = [v.strip() for v in (self.template_values or "").split(",") if v.strip()]
            if len(values) != self.template_id.variable_count:
                raise ValidationError(_("This template expects %s variable(s).") % self.template_id.variable_count)
            payload = self.template_id.build_payload(to, values)
            body_for_log = self.template_id.body_preview or self.template_id.name
            template_id = self.template_id.id
            msg_type = "template"
        else:
            if not self.attachment_id:
                raise ValidationError(_("Select a file to send."))
            media_id = account._upload_attachment(self.attachment_id)
            if not media_id:
                raise UserError(_("Meta did not return a media ID."))
            media = {"id": media_id}
            if self.caption and self.media_type in ("image", "document", "video"):
                media["caption"] = self.caption
            if self.media_type == "document" and self.attachment_id.name:
                media["filename"] = self.attachment_id.name
            payload.update({"type": self.media_type, self.media_type: media})
            attachment_id = self.attachment_id.id
            msg_type = self.media_type

        response = account._send_payload(payload)
        messages = response.get("messages") or []
        meta_id = messages[0].get("id") if messages else False
        self.env["ellaithy.whatsapp.message"].create({
            "conversation_id": conv.id,
            "direction": "outbound",
            "message_type": msg_type,
            "body": body_for_log,
            "attachment_id": attachment_id,
            "meta_message_id": meta_id,
            "status": "sent" if meta_id else "queued",
            "sent_by_id": self.env.user.id,
            "template_id": template_id,
            "raw_payload": json.dumps(response, ensure_ascii=False),
        })
        if conv.state in ("new", "waiting_internal"):
            conv.state = "waiting_customer"
        return {"type": "ir.actions.act_window_close"}
