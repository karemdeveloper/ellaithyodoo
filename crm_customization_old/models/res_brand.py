from odoo import models, fields

class ResBrand(models.Model):
    _name = 'res.brand'
    _description = 'Brand'
    _rec_name = 'brand_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    brand_name = fields.Char(string="Brand Name",translate=True)
    name_ar = fields.Char(string="Brand Name (Arabic)")
    sub_brand_ids = fields.One2many('res.sub.brand', 'brand', string="Sub Brands")
