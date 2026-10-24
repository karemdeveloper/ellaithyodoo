from odoo import models, fields,api

class ComplaintUser(models.Model):
    _name = 'complaint.user'
    _description = 'Complaint User'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string=" User Name")
