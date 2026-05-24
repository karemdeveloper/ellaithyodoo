import functools
from odoo import http
from odoo.http import request
from odoo.addons.ibs_api_integration.core.helpers import error_response

def require_token(func):
    """Decorator to validate API token before processing request"""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        auth_header = request.httprequest.headers.get("Authorization")
        
        if not auth_header:
            return error_response("missing_authorization", "Authorization header is required", 401)
            
        try:
            auth_parts = auth_header.split()
            if len(auth_parts) != 2 or auth_parts[0].lower() != "bearer":
                return error_response("invalid_authorization", "Authorization must use Bearer scheme", 401)
                
            token = auth_parts[1]
        except Exception:
            return error_response("invalid_authorization", "Invalid Authorization header format", 401)
            
        token_record = (
            request.env["api.token"].sudo().search([("token", "=", token)], order="id DESC", limit=1)
        )
        
        if not token_record:
            return error_response("invalid_token", "Token not found or expired", 401)
            
        if token_record.get_or_create_token(user_id=token_record.user_id.id) != token:
            return error_response("expired_token", "Token has expired", 401)
            
        request.session.uid = token_record.user_id.id
        request.update_env(user=token_record.user_id.id)
        return func(self, *args, **kwargs)
        
    return wrapper 