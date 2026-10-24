from odoo import models, fields, api

class CrmTeamMember(models.Model):
    _inherit = 'crm.team.member'

    shift = fields.Many2many('res.shift', string="Shift")
    state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string="Status", default='active', tracking=True)
    date_to = fields.Datetime(string="To")
    team_leader = fields.Many2one(
        'res.users',
        string='Team Leader',
        related='crm_team_id.user_id',
        store=True,
        readonly=True
    )

    # Computed field to check if user has permission to edit state directly
    can_edit_state_directly = fields.Boolean(
        string='Can Edit State Directly',
        compute='_compute_can_edit_state_directly'
    )

    @api.depends_context('uid')
    def _compute_can_edit_state_directly(self):
        """Check if current user has permission to edit state directly"""
        has_permission = self.env.user.has_group('crm_customization.group_direct_inactive_members')
        for rec in self:
            rec.can_edit_state_directly = has_permission
    @api.model
    def _cron_check_inactive_members(self):
        """Deactivate members whose date_to has passed, and activate scheduled inactive requests."""
        now = fields.Datetime.now()

        # Reactivate members whose inactive period has ended
        expired_members = self.search([
            ('date_to', '<', now),
            ('state', '=', 'inactive')
        ])
        expired_members.write({'state': 'active'})

        # Apply scheduled inactive requests whose date_from has arrived
        pending_requests = self.env['inactive.request'].search([
            ('state', '=', 'approved'),
            ('scheduled_inactive', '=', True),
            ('date_from', '<=', now),
        ])
        for req in pending_requests:
            member = self.search([('user_id', '=', req.create_uid.id)], limit=1)
            if member:
                member.state = 'inactive'
                if req.date_to:
                    member.date_to = req.date_to
            req.scheduled_inactive = False