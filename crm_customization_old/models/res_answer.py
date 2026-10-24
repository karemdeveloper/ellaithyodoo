from odoo import models, fields,api

class ResAnswer(models.Model):
    _name = 'res.answer'
    _description = 'Answers'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name")
