from odoo import models, fields,api

class ResDepartment(models.Model):
    _name = 'res.department'
    _description = 'Department'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name")
    department_user = fields.Many2many('res.users', string="Department Users", tracking=True)
    alias_email = fields.Char(string='Alias Email', help='Email address for this department to receive complaints')
    department_manager_id = fields.Many2one('res.users', string='Department Manager', tracking=True)