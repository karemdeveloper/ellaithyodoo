from odoo import models, fields, api


class ResService(models.Model):
    _name = 'res.service'
    _description = 'Service'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Service Name', required=True, tracking=True)

