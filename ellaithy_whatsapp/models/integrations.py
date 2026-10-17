from odoo import _, models
from odoo.exceptions import UserError


def _open_whatsapp_conversation(record, phone, partner=False):
    """Open/create a WhatsApp conversation for an arbitrary business record.

    Kept as a plain helper instead of a Python mixin. Odoo dynamically rebuilds
    model inheritance during registry setup, and combining an Odoo model with a
    normal Python mixin can trigger CPython __bases__ layout errors.
    """
    record.ensure_one()
    if not phone:
        raise UserError(_("No phone number is available for WhatsApp."))

    account = record.env["ellaithy.whatsapp.account"].sudo().search(
        [("active", "=", True)], order="sequence, id", limit=1
    )
    if not account:
        raise UserError(_("No active WhatsApp account is configured."))

    normalized = account._normalize_phone(phone)
    Conversation = record.env["ellaithy.whatsapp.conversation"].sudo()
    conversation = Conversation.search(
        [("account_id", "=", account.id), ("phone", "=", normalized)],
        limit=1,
    )

    link_field = {
        "crm.lead": "crm_lead_id",
        "res.complaint": "complaint_id",
        "helpdesk.ticket": "helpdesk_ticket_id",
    }.get(record._name)

    if not conversation:
        vals = {
            "account_id": account.id,
            "phone": normalized,
            "contact_name": partner.name if partner else False,
            "partner_id": partner.id if partner else False,
        }
        if link_field:
            vals[link_field] = record.id
        conversation = Conversation.create(vals)
    else:
        vals = {}
        if partner and not conversation.partner_id:
            vals.update({"partner_id": partner.id, "contact_name": partner.name})
        if link_field and not conversation[link_field]:
            vals[link_field] = record.id
        if vals:
            conversation.write(vals)

    return {
        "type": "ir.actions.act_window",
        "res_model": "ellaithy.whatsapp.conversation",
        "res_id": conversation.id,
        "view_mode": "form",
        "target": "current",
    }


class CrmLead(models.Model):
    _inherit = "crm.lead"

    def action_open_whatsapp(self):
        self.ensure_one()
        partner = self.partner_id
        phone = (
            self.mobile
            or self.phone
            or (partner.mobile if partner else False)
            or (partner.phone if partner else False)
        )
        return _open_whatsapp_conversation(self, phone, partner)


class ResComplaint(models.Model):
    _inherit = "res.complaint"

    def action_open_whatsapp(self):
        self.ensure_one()
        partner = self.customer_id
        phone = self.primary_phone or (partner.mobile if partner else False)
        return _open_whatsapp_conversation(self, phone, partner)


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    def action_open_whatsapp(self):
        self.ensure_one()
        partner = self.partner_id
        phone = (
            self.partner_phone
            or (partner.mobile if partner else False)
            or (partner.phone if partner else False)
        )
        return _open_whatsapp_conversation(self, phone, partner)
