from odoo import models, fields,api

class ResEscalation(models.Model):
    _name = 'res.escalation'
    _description = 'Escalation Line'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name")
