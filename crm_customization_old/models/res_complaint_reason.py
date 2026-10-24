from odoo import models, fields,api

class ResComplaintReason(models.Model):
    _name = 'res.complaint.reason'
    _description = 'Complaint Reason'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name")
    has_user = fields.Boolean(string="Has User")
