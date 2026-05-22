from odoo import models, fields, api
from datetime import datetime, timedelta
import hashlib
import os

class ApiToken(models.Model):
    _name = 'api.token'
    _description = 'API Access Token'
    _rec_name = 'user_id'

    token = fields.Char(required=True, index=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    expires = fields.Datetime(required=True)

    _sql_constraints = [
        ('user_id_unique', 'UNIQUE(user_id)', 'Only one active token per user!')
    ]

    @api.model
    def get_or_create_token(self, user_id):
        # Reuse valid token
        existing = self.search([
            ('user_id', '=', user_id),
            ('expires', '>', fields.Datetime.now())
        ], limit=1)

        if existing:
            return existing.token

        self.search([('user_id', '=', user_id)]).unlink()

        new_token = hashlib.sha256(os.urandom(40)).hexdigest()
        expiration = datetime.now() + timedelta(days=30)

        self.create({
            'token': new_token,
            'user_id': user_id,
            'expires': expiration,
        })

        return new_token