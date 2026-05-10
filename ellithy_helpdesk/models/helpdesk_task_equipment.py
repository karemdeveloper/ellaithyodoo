from odoo import models, fields



class HelpdeskTaskEquipment(models.Model):
    _name = 'helpdesk.task.equipment'
    _description = 'Task Equipment'

    name = fields.Char(string="Equipment Name", required=True)
    active = fields.Boolean(default=True)