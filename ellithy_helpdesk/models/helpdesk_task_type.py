from odoo import models, fields


class HelpdeskTaskType(models.Model):
    _name = 'helpdesk.task.type'
    _description = 'Team Tasks'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Task Name",required=True, tracking=True)

    team_id = fields.Many2one(
        'helpdesk.team',
        string="Team",
        required=True,
        tracking=True,
        ondelete='cascade'
    )

    duration_hours = fields.Float(
        string="Duration (Hours)",
        default=1.0,
        required=True,
        tracking=True,
        help="Expected time to solve this task"
    )

    member_ids = fields.Many2many(
        'res.users',
        string="Team Members",
        related='team_id.member_ids',
        readonly=True
    )

    responsible_id = fields.Many2one(
        'res.users',
        string="Responsible User",
        domain="[('id', 'in', member_ids)]",
        tracking=True
    )

    equipment_id = fields.Many2one(
        'helpdesk.task.equipment',
        string="Required Equipment",
        tracking=True
    )

class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    assign_method = fields.Selection(selection_add=[
        ('manual', "Don't Assign (Manual by Manager)")
    ],default='manual', ondelete={'manual': 'set default'})

    manager_id = fields.Many2one(
        'res.users',
        string="Team Manager",
        required=False,
        help="The person responsible for assigning tickets to team members."
    )

    team_leader_id = fields.Many2one(
        'res.users',
        string="Team Leader",
        required=False,
        help="The secondary person responsible for the team."
    )


class HelpdeskStage(models.Model):
    _inherit = 'helpdesk.stage'

    # is_hold_stage = fields.Boolean(string="Is Hold Stage", help="If checked, tickets in this stage will stop the SLA clock.")
    is_escalation_stage = fields.Boolean(string="Is Escalation Stage")
    escalation_level = fields.Selection([
        ('none', 'None'),
        ('leader', 'Team Leader'),
        ('manager', 'Manager'),
        ('overdue', 'Overdue')
    ], default='none')
    # is_default_return_stage = fields.Boolean(
    #     string="Is Default Return Stage",
    #     help="Check this to make tickets return to this stage after being unblocked."
    # )