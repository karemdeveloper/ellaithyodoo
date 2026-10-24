from odoo import models, fields,api

class CallType(models.Model):
    _name = 'call.type'
    _description = 'Call Type'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string=" name")

