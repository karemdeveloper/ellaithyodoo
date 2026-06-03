from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _authenticate(cls, endpoint):
        # Corrupt sessions (uid set but session_token missing) cause a TypeError
        # in security.check_session. Clear them before the check runs.
        if request.session.uid and not request.session.session_token:
            request.session.logout(keep_db=True)
        try:
            return super()._authenticate(endpoint)
        except Exception:
            # Session is invalid/expired — clear it and retry as a clean request.
            # Safe for auth="none" endpoints; they don't rely on session state.
            request.session.logout(keep_db=True)
            return super()._authenticate(endpoint)
