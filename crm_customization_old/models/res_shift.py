from odoo import models, fields,api

class ResShift(models.Model):
    _name = 'res.shift'
    _description = 'Shift'
    _rec_name = 'shift_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    shift_name = fields.Char(string="Shift name")
    day = fields.Many2one( 'res.day',string="Day")
    from_date = fields.Float(string="From")
    to_date = fields.Float(string="To")
