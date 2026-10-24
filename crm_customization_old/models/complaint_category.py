from odoo import models, fields, api
from datetime import date

class ComplaintCategory(models.Model):
    _name = 'complaint.category'
    _description = 'Complaint Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Complaint Category', required=True, copy=False,
                        tracking=True)
