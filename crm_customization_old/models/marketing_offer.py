from odoo import models, fields,api

class MarketingOffers(models.Model):
    _name = 'marketing.offers'
    _description = 'Marketing Offers'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    name = fields.Char(string="Name")
