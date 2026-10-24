from odoo import models, fields

class ResArea(models.Model):
    _name = 'res.area'
    _description = 'Area'
    _rec_name = 'area_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    area_name = fields.Char(string="Area Name",translate=True)
    name_ar = fields.Char(string="Area Name (Arabic)")
    branch_area = fields.Many2one('res.branch',string="Branch Name")
