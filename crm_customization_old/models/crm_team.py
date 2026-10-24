from odoo import models, fields,api

class CrmTeam(models.Model):
    _inherit = 'crm.team'
    branch_name = fields.Many2one('res.branch', string="Branch")
