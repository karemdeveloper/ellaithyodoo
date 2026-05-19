import json

from odoo import http
from odoo.addons.ibs_api_integration.core.helpers import success_response, error_response
from odoo.exceptions import AccessDenied, AccessError
from odoo.http import request


class AuthenticationEndpoint(http.Controller):
    """Handles token issuance and revocation for the IBS API."""

    @http.route("/api/v1/auth/token", methods=["POST"], type="http", auth="none", csrf=False)
    def get_token(self, **post):
        """Issue a Bearer token for valid Odoo credentials.

        Reads credentials from request headers (not the body) so they are
        never logged by web-server access logs.

        Headers:
            db       – Odoo database name
            username – Odoo user login
            password – Odoo user password

        Returns 200 with access_token, uid, company_id, partner_id, employee_id.
        Returns 400 when headers are missing, 401 on bad credentials.
        """
        headers = request.httprequest.headers
        db = headers.get("db")
        username = headers.get("username")
        password = headers.get("password")

        if not db or not username or not password:
            return error_response(
                "missing_parameters",
                "Required parameters missing in headers: db, username, password",
                400,
            )

        try:
            request.session.update(http.get_default_session(), db=db)
            credential = {"login": username, "password": password, "type": "password"}
            uid = request.session.authenticate(db, credential)
        except AccessError as e:
            return error_response("access_error", f"Access error: {e.name}", 403)
        except AccessDenied:
            return error_response("access_denied", "Invalid credentials", 401)
        except Exception as e:
            return error_response("authentication_error", str(e), 500)

        if not uid:
            return error_response("authentication_failed", "Authentication failed", 401)

        token_model = request.env["api.token"].sudo()
        user_id = uid.get("uid") if isinstance(uid, dict) else uid
        access_token = token_model.get_or_create_token(user_id=user_id)

        return success_response(
            {
                "uid": user_id,
                "company_id": request.env.user.company_id.id,
                "partner_id": request.env.user.partner_id.id,
                "employee_id": request.env.user.employee_id.id
                if request.env.user.employee_id
                else None,
                "access_token": access_token,
            },
            200,
        )

    @http.route(["/api/v1/auth/token"], methods=["DELETE"], type="http", auth="none", csrf=False)
    def revoke_token(self, **post):
        """Revoke an active Bearer token.

        Query parameter:
            access_token – the token string to invalidate

        Returns 200 on success, 400 when the token is missing or invalid.
        """
        token_model = request.env["api.token"]
        access_token = post.get("access_token")

        if not access_token:
            return error_response("missing_token", "Access token is required", 400)

        token_record = token_model.search([("token", "=", access_token)], limit=1)
        if not token_record:
            return error_response("invalid_token", "Invalid or expired token", 400)

        token_record.unlink()
        return success_response({"message": "Token successfully revoked", "revoked": True})
