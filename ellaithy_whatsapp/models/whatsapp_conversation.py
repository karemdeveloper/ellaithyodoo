import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EllaithyWhatsAppConversation(models.Model):
    _name = "ellaithy.whatsapp.conversation"
    _description = "WhatsApp Conversation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "last_message_at desc, id desc"

    name = fields.Char(default="New Conversation", required=True, tracking=True)
    account_id = fields.Many2one("ellaithy.whatsapp.account", required=True, ondelete="restrict", tracking=True)
    phone = fields.Char(required=True, index=True, tracking=True)
    wa_id = fields.Char(string="WhatsApp ID", index=True)
    contact_name = fields.Char(tracking=True)
    partner_id = fields.Many2one("res.partner", string="Contact", tracking=True)
    crm_lead_id = fields.Many2one("crm.lead", string="CRM Lead / Opportunity", tracking=True)
    complaint_id = fields.Many2one("res.complaint", string="Complaint", tracking=True)
    helpdesk_ticket_id = fields.Many2one("helpdesk.ticket", string="Helpdesk Ticket", tracking=True)

    team_id = fields.Many2one("ellaithy.whatsapp.team", tracking=True)
    assigned_user_id = fields.Many2one("res.users", string="Assigned Agent", tracking=True)
    state = fields.Selection(
        [
            ("new", "New"),
            ("open", "Open"),
            ("waiting_customer", "Waiting Customer"),
            ("waiting_internal", "Waiting Internal"),
            ("resolved", "Resolved"),
            ("closed", "Closed"),
        ],
        default="new",
        required=True,
        tracking=True,
        index=True,
    )
    message_ids = fields.One2many("ellaithy.whatsapp.message", "conversation_id", string="Messages")
    last_message_at = fields.Datetime(index=True)
    last_message_preview = fields.Char()
    unread_count = fields.Integer(default=0)
    first_response_at = fields.Datetime()
    first_response_minutes = fields.Float(compute="_compute_response_metrics", store=True)
    resolution_minutes = fields.Float(compute="_compute_response_metrics", store=True)
    resolved_at = fields.Datetime()
    company_id = fields.Many2one(related="account_id.company_id", store=True)
    report_count = fields.Integer(string="Conversations", default=1, readonly=True)

    _sql_constraints = [
        ("account_phone_unique", "unique(account_id, phone)", "A phone number can only have one conversation per WhatsApp account."),
    ]

    @api.depends("create_date", "first_response_at", "resolved_at")
    def _compute_response_metrics(self):
        for rec in self:
            rec.first_response_minutes = 0.0
            rec.resolution_minutes = 0.0
            if rec.create_date and rec.first_response_at:
                rec.first_response_minutes = (rec.first_response_at - rec.create_date).total_seconds() / 60.0
            if rec.create_date and rec.resolved_at:
                rec.resolution_minutes = (rec.resolved_at - rec.create_date).total_seconds() / 60.0

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.team_id and rec.account_id.default_team_id:
                rec.team_id = rec.account_id.default_team_id
            if not rec.assigned_user_id and rec.team_id:
                user = rec.team_id._next_user()
                if user:
                    rec.assigned_user_id = user
            if rec.name == "New Conversation":
                rec.name = rec.contact_name or rec.partner_id.name or rec.phone
        return records

    def write(self, vals):
        if vals.get("state") == "resolved" and "resolved_at" not in vals:
            vals["resolved_at"] = fields.Datetime.now()
        elif vals.get("state") not in (None, "resolved") and "resolved_at" not in vals:
            vals["resolved_at"] = False
        return super().write(vals)

    def action_open_send_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Send WhatsApp Message"),
            "res_model": "ellaithy.whatsapp.send.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_conversation_id": self.id},
        }

    def action_mark_read(self):
        self.write({"unread_count": 0, "state": "open" if self.state == "new" else self.state})
        return True

    def action_resolve(self):
        self.write({"state": "resolved", "unread_count": 0})
        return True

    def action_reopen(self):
        self.write({"state": "open", "resolved_at": False})
        return True

    def action_open_partner(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("No contact is linked to this conversation."))
        return {"type": "ir.actions.act_window", "res_model": "res.partner", "res_id": self.partner_id.id, "view_mode": "form", "target": "current"}

    def action_open_crm(self):
        self.ensure_one()
        if not self.crm_lead_id:
            raise UserError(_("No CRM lead/opportunity is linked."))
        return {"type": "ir.actions.act_window", "res_model": "crm.lead", "res_id": self.crm_lead_id.id, "view_mode": "form", "target": "current"}

    def action_open_complaint(self):
        self.ensure_one()
        if not self.complaint_id:
            raise UserError(_("No complaint is linked."))
        return {"type": "ir.actions.act_window", "res_model": "res.complaint", "res_id": self.complaint_id.id, "view_mode": "form", "target": "current"}

    def action_open_helpdesk(self):
        self.ensure_one()
        if not self.helpdesk_ticket_id:
            raise UserError(_("No helpdesk ticket is linked."))
        return {"type": "ir.actions.act_window", "res_model": "helpdesk.ticket", "res_id": self.helpdesk_ticket_id.id, "view_mode": "form", "target": "current"}

    @api.model
    def _find_partner_by_phone(self, normalized_phone):
        if not normalized_phone:
            return self.env["res.partner"]
        partners = self.env["res.partner"].sudo().search(["|", ("phone", "!=", False), ("mobile", "!=", False)])
        for partner in partners:
            for number in (partner.mobile, partner.phone):
                digits = re.sub(r"\D", "", number or "")
                if digits and (digits.endswith(normalized_phone) or normalized_phone.endswith(digits)):
                    return partner
        return self.env["res.partner"]

    @api.model
    def _find_crm_by_phone(self, normalized_phone):
        if not normalized_phone:
            return self.env["crm.lead"]
        leads = self.env["crm.lead"].sudo().search(["|", ("phone", "!=", False), ("mobile", "!=", False)], order="id desc", limit=500)
        for lead in leads:
            for number in (lead.mobile, lead.phone):
                digits = re.sub(r"\D", "", number or "")
                if digits and (digits.endswith(normalized_phone) or normalized_phone.endswith(digits)):
                    return lead
        return self.env["crm.lead"]

    @api.model
    def get_or_create_for_incoming(self, account, phone, contact_name=None, wa_id=None):
        normalized = account._normalize_phone(phone)
        conversation = self.sudo().search([("account_id", "=", account.id), ("phone", "=", normalized)], limit=1)
        if conversation:
            updates = {}
            if contact_name and not conversation.contact_name:
                updates["contact_name"] = contact_name
            if wa_id and not conversation.wa_id:
                updates["wa_id"] = wa_id
            if conversation.state in ("resolved", "closed"):
                updates["state"] = "open"
                updates["resolved_at"] = False
            if updates:
                conversation.write(updates)
            return conversation

        partner = self._find_partner_by_phone(normalized)
        if not partner and account.auto_create_contact:
            partner = self.env["res.partner"].sudo().create({
                "name": contact_name or f"WhatsApp {normalized}",
                "mobile": normalized,
            })

        lead = self._find_crm_by_phone(normalized)
        if not lead and account.auto_create_lead:
            lead = self.env["crm.lead"].sudo().create({
                "name": f"WhatsApp Lead - {contact_name or normalized}",
                "contact_name": contact_name or False,
                "phone": normalized,
                "partner_id": partner.id if partner else False,
                "description": _("Automatically created from an incoming WhatsApp conversation."),
            })

        return self.sudo().create({
            "account_id": account.id,
            "phone": normalized,
            "wa_id": wa_id or normalized,
            "contact_name": contact_name or (partner.name if partner else False),
            "partner_id": partner.id if partner else False,
            "crm_lead_id": lead.id if lead else False,
            "team_id": account.default_team_id.id if account.default_team_id else False,
        })
