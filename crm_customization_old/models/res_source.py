from odoo import models, fields

class ResSource(models.Model):
    _name = 'res.source'
    _description = 'Source'
    _rec_name = 'source_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    source_name = fields.Char(string="Source Name")
