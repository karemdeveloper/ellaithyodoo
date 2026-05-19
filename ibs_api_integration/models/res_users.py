from odoo import models, fields

class ResUsers(models.Model):
    _inherit = "res.users"
    
    api_token_ids = fields.One2many("api.token", "user_id", string="API Tokens")