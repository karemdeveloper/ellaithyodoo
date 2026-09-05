from odoo import models, fields, api

class InActiveRequest(models.Model):
    _name = 'inactive.request'
    _description = 'Inactive Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'inactive_reason'

    date = fields.Date(string="Date")
    date_from = fields.Datetime(string="From")
    date_to = fields.Datetime(string="To")
    inactive_reason = fields.Many2one('inactive.reason', string="In Active reason")
    state = fields.Selection([
        ('to_approve', 'To Approve'),
        ('approved', 'Approved'),
        ('refused', 'Refused')
    ], string="State", default='to_approve', tracking=True)
    scheduled_inactive = fields.Boolean(string="Scheduled", default=False)

    # ===== Buttons actions =====
    def action_approve(self):
        """Set state to Approved"""
        now = fields.Datetime.now()
        for rec in self:
            rec.state = 'approved'
            if rec.date_from and rec.date_from > now:
                # Future scheduled: cron will apply it at date_from
                rec.scheduled_inactive = True
            else:
                # Apply immediately
                member = self.env['crm.team.member'].sudo().search([('user_id', '=', rec.create_uid.id)], limit=1)
                if member:
                    member.state = 'inactive'
                    if rec.date_to:
                        member.date_to = rec.date_to

    def action_refuse(self):
        """Set state to Refused"""
        for rec in self:
            rec.state = 'refused'
###################################################################

    team_leader = fields.Many2one('res.users', string="Team Leader", compute='_compute_team_leader', store=True)

    @api.depends('create_uid')
    def _compute_team_leader(self):
        for rec in self:
            member = self.env['crm.team.member'].search([('user_id', '=', rec.create_uid.id)], limit=1)
            rec.team_leader = member.team_leader.id if member else False
####################################################################################################
    # field to store the salesperson (current user) who created the inactive request
    salesperson_id = fields.Many2one('res.users',string='Salesperson',default=lambda self: self.env.user,readonly=False,tracking=True)