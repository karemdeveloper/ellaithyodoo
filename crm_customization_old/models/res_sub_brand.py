from odoo import models, fields

class ResSubBrand(models.Model):
    _name = 'res.sub.brand'
    _description = ' Sub Brand'
    _rec_name = 'sub_brand_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    sub_brand_name = fields.Char(string=" Sub Brand Name",translate=True)
    name_ar = fields.Char(string="Sub Brand Name (Arabic)")
    brand=fields.Many2one('res.brand',string="Brand")