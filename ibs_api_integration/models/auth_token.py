import hashlib
import os
from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.addons.ibs_api_integration.core.auth import generate_token, token_expiration

class APIToken(models.Model):
    """API Access Token model"""
    _name = "api.token"
    _description = "API Access Token"
    
    token = fields.Char("Access Token", required=True, index=True)
    user_id = fields.Many2one("res.users", string="User", required=True, ondelete="cascade")
    expires = fields.Datetime("Expires", required=True)
    
    @api.model
    def get_or_create_token(self, user_id=None):
        """Get existing token or create a new one for the user"""
        if not user_id:
            return False
            
        # Check for existing valid token
        token = self.search([
            ("user_id", "=", user_id),
            ("expires", ">", fields.Datetime.now())
        ], limit=1)
        
        if token:
            return token.token
            
        # Create new token
        expiration = token_expiration()
        token_value = generate_token()
        
        self.create({
            "token": token_value,
            "user_id": user_id,
            "expires": expiration,
        })
        
        return token_value

