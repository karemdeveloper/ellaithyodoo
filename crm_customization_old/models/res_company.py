from odoo import models, fields

class ResCompany(models.Model):
    _name = 'res.company.custom'
    _description = 'Company'
    _rec_name = 'company_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    company_name = fields.Char(string="Company Name")
