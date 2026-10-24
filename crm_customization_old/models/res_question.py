from odoo import models, fields,api

class ResQuestion(models.Model):
    _name = 'res.question'
    _description = 'Questions'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name")
