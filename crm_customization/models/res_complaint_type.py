from odoo import models, fields,api

class ResComplaintType(models.Model):
    _name = 'res.complaint.type'
    _description = 'Complaint Type'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name")
    department_id = fields.Many2one('res.department', string='Department')
    sla_duration = fields.Char(string='SLA Duration', help='Expected time to resolve this type of complaint')
    email_template_id = fields.Many2one('mail.template', string='Email Template', 
                                        domain="[('model', '=', 'res.complaint')]",
                                        help='Email template to use when sending complaint notifications')

