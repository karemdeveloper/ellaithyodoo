from odoo import api, fields, models


class EllaithyWhatsAppTeam(models.Model):
    _name = "ellaithy.whatsapp.team"
    _description = "WhatsApp Team"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    supervisor_id = fields.Many2one("res.users", string="Supervisor")
    member_ids = fields.Many2many("res.users", string="Agents")
    assignment_mode = fields.Selection(
        [("manual", "Manual"), ("round_robin", "Round Robin")],
        default="round_robin",
        required=True,
    )
    last_assigned_user_id = fields.Many2one("res.users", copy=False)

    def _next_user(self):
        self.ensure_one()
        members = self.member_ids.filtered(lambda u: u.active and not u.share).sorted("id")
        if not members:
            return False
        if self.assignment_mode == "manual":
            return False
        ids = members.ids
        if self.last_assigned_user_id.id in ids:
            pos = ids.index(self.last_assigned_user_id.id)
            user = members[(pos + 1) % len(members)]
        else:
            user = members[0]
        self.sudo().last_assigned_user_id = user.id
        return user
