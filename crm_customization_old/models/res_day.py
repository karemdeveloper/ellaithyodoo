from odoo import models, fields,api

class ResDay(models.Model):
    _name = 'res.day'
    _description = 'Days'
    _rec_name = 'day'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    day = fields.Char(string="Name")
