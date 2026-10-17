from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WhatsAppLinkMixin:
    def _whatsapp_phone(self):
        return False

    def _whatsapp_partner(self):
        return self.env["res.partner"]

    def _whatsapp_conversation_domain(self):
        self.ensure_one()
        return []

    def action_open_whatsapp(self):
        self.ensure_one()
        phone = self._whatsapp_phone()
        partner = self._whatsapp_partner()
        if not phone:
            raise UserError(_("No phone number is available for WhatsApp."))
        account = self.env["ellaithy.whatsapp.account"].sudo().search([("active", "=", True)], order="sequence, id", limit=1)
        if not account:
            raise UserError(_("No active WhatsApp account is configured."))
        normalized = account._normalize_phone(phone)
        conversation = self.env["ellaithy.whatsapp.conversation"].sudo().search([
            ("account_id", "=", account.id), ("phone", "=", normalized)
        ], limit=1)
        if not conversation:
            vals = {
                "account_id": account.id,
                "phone": normalized,
                "contact_name": partner.name if partner else False,
                "partner_id": partner.id if partner else False,
            }
            if self._name == "crm.lead":
                vals["crm_lead_id"] = self.id
            elif self._name == "res.complaint":
                vals["complaint_id"] = self.id
            elif self._name == "helpdesk.ticket":
                vals["helpdesk_ticket_id"] = self.id
            conversation = self.env["ellaithy.whatsapp.conversation"].sudo().create(vals)
        else:
            vals = {}
            if self._name == "crm.lead" and not conversation.crm_lead_id:
                vals["crm_lead_id"] = self.id
            elif self._name == "res.complaint" and not conversation.complaint_id:
                vals["complaint_id"] = self.id
            elif self._name == "helpdesk.ticket" and not conversation.helpdesk_ticket_id:
                vals["helpdesk_ticket_id"] = self.id
            if vals:
                conversation.write(vals)
        return {
            "type": "ir.actions.act_window",
            "res_model": "ellaithy.whatsapp.conversation",
            "res_id": conversation.id,
            "view_mode": "form",
            "target": "current",
        }


class CrmLead(models.Model, WhatsAppLinkMixin):
    _inherit = "crm.lead"

    def _whatsapp_phone(self):
        self.ensure_one()
        return self.mobile or self.phone or (self.partner_id.mobile if self.partner_id else False) or (self.partner_id.phone if self.partner_id else False)

    def _whatsapp_partner(self):
        self.ensure_one()
        return self.partner_id


class ResComplaint(models.Model, WhatsAppLinkMixin):
    _inherit = "res.complaint"

    def _whatsapp_phone(self):
        self.ensure_one()
        return self.primary_phone or (self.customer_id.mobile if self.customer_id else False)

    def _whatsapp_partner(self):
        self.ensure_one()
        return self.customer_id


class HelpdeskTicket(models.Model, WhatsAppLinkMixin):
    _inherit = "helpdesk.ticket"

    def _whatsapp_phone(self):
        self.ensure_one()
        return self.partner_phone or (self.partner_id.mobile if self.partner_id else False) or (self.partner_id.phone if self.partner_id else False)

    def _whatsapp_partner(self):
        self.ensure_one()
        return self.partner_id
