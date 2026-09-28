from odoo import _, http
from odoo.http import request
from werkzeug.utils import redirect


class EllaithyDriveBackupOAuth(http.Controller):

    @http.route('/ellaithy_drive_backup/oauth/callback', type='http', auth='user', csrf=False, methods=['GET'])
    def google_oauth_callback(self, **params):
        if not request.env.user.has_group('base.group_system'):
            return request.not_found()
        error = params.get('error')
        if error:
            return request.make_response(_('Google authorization failed: %s') % error, headers=[('Content-Type', 'text/plain; charset=utf-8')])
        code = params.get('code')
        state = params.get('state', '')
        try:
            config_id_text, state_token = state.split(':', 1)
            config = request.env['ellaithy.drive.backup.config'].sudo().browse(int(config_id_text)).exists()
            if not config or not config.oauth_state or config.oauth_state != state_token:
                return request.make_response(_('Invalid or expired OAuth state.'), status=400)
            if not code:
                return request.make_response(_('Google did not return an authorization code.'), status=400)
            config._exchange_code(code)
            return redirect(f'/web#id={config.id}&model=ellaithy.drive.backup.config&view_type=form')
        except Exception as exc:
            return request.make_response(_('Google authorization failed: %s') % str(exc), status=400)
