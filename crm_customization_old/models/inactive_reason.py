from odoo import models, fields,api

class InactiveReason(models.Model):
    _name = 'inactive.reason'
    _description = 'Inactive Reason'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string=" name")

