import json
import logging
import os
import secrets
import tempfile
from datetime import datetime, timedelta, time as dt_time

import pytz
import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.service import db as service_db

_logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
DRIVE_FILES_URL = 'https://www.googleapis.com/drive/v3/files'
DRIVE_UPLOAD_URL = 'https://www.googleapis.com/upload/drive/v3/files'
DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive.file'


class EllaithyDriveBackupConfig(models.Model):
    _name = 'ellaithy.drive.backup.config'
    _description = 'Google Drive Backup Configuration'
    _rec_name = 'name'

    name = fields.Char(required=True, default='Google Drive Backup')
    active = fields.Boolean(default=True)

    google_client_id = fields.Char(string='Google Client ID', required=True)
    google_client_secret = fields.Char(string='Google Client Secret', required=True)
    google_refresh_token = fields.Char(string='Google Refresh Token', copy=False)
    google_folder_id = fields.Char(string='Google Drive Folder ID', help='Leave empty and the module will create its own Odoo Backups folder.')
    google_folder_name = fields.Char(string='Drive Folder Name', default='Odoo Backups', required=True)
    oauth_state = fields.Char(copy=False)
    google_connected = fields.Boolean(compute='_compute_google_connected')

    backup_format = fields.Selection([
        ('zip', 'ZIP - Database + Filestore'),
        ('dump', 'PostgreSQL Dump - Database Only'),
    ], default='zip', required=True)

    schedule_enabled = fields.Boolean(default=True)
    backup_time = fields.Float(string='Daily Backup Time', default=2.0, help='Time in the selected timezone, e.g. 2.0 = 02:00.')
    timezone = fields.Selection(selection=lambda self: [(tz, tz) for tz in pytz.all_timezones], default=lambda self: self.env.user.tz or 'UTC', required=True)
    next_backup_at = fields.Datetime(string='Next Backup At', readonly=True)
    last_backup_at = fields.Datetime(string='Last Backup At', readonly=True)
    last_success_at = fields.Datetime(string='Last Successful Backup', readonly=True)
    last_error = fields.Text(readonly=True)

    retention_days = fields.Integer(default=30, required=True, help='Google Drive backups older than this number of days will be deleted. Set 0 to disable cleanup.')
    filename_prefix = fields.Char(default='odoo-backup', required=True)

    log_ids = fields.One2many('ellaithy.drive.backup.log', 'config_id', string='Backup History')

    @api.depends('google_refresh_token')
    def _compute_google_connected(self):
        for rec in self:
            rec.google_connected = bool(rec.google_refresh_token)

    @api.constrains('backup_time')
    def _check_backup_time(self):
        for rec in self:
            if rec.backup_time < 0 or rec.backup_time >= 24:
                raise ValidationError(_('Daily Backup Time must be between 0.00 and 23.99.'))

    @api.constrains('retention_days')
    def _check_retention_days(self):
        for rec in self:
            if rec.retention_days < 0:
                raise ValidationError(_('Retention Days cannot be negative.'))

    def write(self, vals):
        result = super().write(vals)
        if {'schedule_enabled', 'backup_time', 'timezone'} & set(vals):
            for rec in self:
                rec._set_next_backup()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._set_next_backup()
        return records

    def _set_next_backup(self, from_dt=None):
        for rec in self:
            if not rec.schedule_enabled:
                rec.next_backup_at = False
                continue
            now_utc = from_dt or fields.Datetime.now()
            if isinstance(now_utc, str):
                now_utc = fields.Datetime.from_string(now_utc)
            tz = pytz.timezone(rec.timezone or 'UTC')
            aware_now = pytz.UTC.localize(now_utc).astimezone(tz)
            hour = int(rec.backup_time)
            minute = int(round((rec.backup_time - hour) * 60))
            if minute >= 60:
                hour = (hour + 1) % 24
                minute = 0
            target_local = tz.localize(datetime.combine(aware_now.date(), dt_time(hour, minute)))
            if target_local <= aware_now:
                target_local += timedelta(days=1)
            rec.next_backup_at = target_local.astimezone(pytz.UTC).replace(tzinfo=None)

    def _redirect_uri(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url').rstrip('/')
        return f'{base_url}/ellaithy_drive_backup/oauth/callback'

    def action_connect_google(self):
        self.ensure_one()
        if not self.google_client_id or not self.google_client_secret:
            raise UserError(_('Please enter Google Client ID and Google Client Secret first.'))
        self.oauth_state = secrets.token_urlsafe(32)
        params = {
            'client_id': self.google_client_id,
            'redirect_uri': self._redirect_uri(),
            'response_type': 'code',
            'scope': DRIVE_SCOPE,
            'access_type': 'offline',
            'prompt': 'consent',
            'state': f'{self.id}:{self.oauth_state}',
        }
        req = requests.Request('GET', GOOGLE_AUTH_URL, params=params).prepare()
        return {'type': 'ir.actions.act_url', 'url': req.url, 'target': 'self'}

    def _exchange_code(self, code):
        self.ensure_one()
        response = requests.post(GOOGLE_TOKEN_URL, data={
            'code': code,
            'client_id': self.google_client_id,
            'client_secret': self.google_client_secret,
            'redirect_uri': self._redirect_uri(),
            'grant_type': 'authorization_code',
        }, timeout=30)
        if not response.ok:
            raise UserError(_('Google OAuth token exchange failed: %s') % response.text)
        payload = response.json()
        refresh_token = payload.get('refresh_token')
        if not refresh_token:
            raise UserError(_('Google did not return a refresh token. Reconnect and ensure consent is granted.'))
        self.sudo().write({'google_refresh_token': refresh_token, 'oauth_state': False})

    def action_disconnect_google(self):
        self.write({'google_refresh_token': False, 'oauth_state': False})
        return True

    def _get_access_token(self):
        self.ensure_one()
        if not self.google_refresh_token:
            raise UserError(_('Google Drive is not connected.'))
        response = requests.post(GOOGLE_TOKEN_URL, data={
            'client_id': self.google_client_id,
            'client_secret': self.google_client_secret,
            'refresh_token': self.google_refresh_token,
            'grant_type': 'refresh_token',
        }, timeout=30)
        if not response.ok:
            raise UserError(_('Unable to refresh Google access token: %s') % response.text)
        return response.json()['access_token']

    def _google_headers(self):
        return {'Authorization': f'Bearer {self._get_access_token()}'}

    def _ensure_drive_folder(self):
        self.ensure_one()
        headers = self._google_headers()
        if self.google_folder_id:
            params = {'fields': 'id,name,mimeType', 'supportsAllDrives': 'true'}
            response = requests.get(f'{DRIVE_FILES_URL}/{self.google_folder_id}', headers=headers, params=params, timeout=30)
            if response.ok:
                data = response.json()
                if data.get('mimeType') != 'application/vnd.google-apps.folder':
                    raise UserError(_('The configured Google Drive ID is not a folder.'))
                return data
            raise UserError(_('The configured Drive folder is not accessible to this app. Leave Folder ID empty and let the module create its own folder. Google response: %s') % response.text)

        create_headers = dict(headers)
        create_headers['Content-Type'] = 'application/json; charset=UTF-8'
        metadata = {
            'name': self.google_folder_name or 'Odoo Backups',
            'mimeType': 'application/vnd.google-apps.folder',
            'appProperties': {'odoo_backup_folder': 'true', 'odoo_config_id': str(self.id)},
        }
        response = requests.post(
            DRIVE_FILES_URL,
            headers=create_headers,
            params={'fields': 'id,name,mimeType', 'supportsAllDrives': 'true'},
            data=json.dumps(metadata),
            timeout=30,
        )
        if not response.ok:
            raise UserError(_('Unable to create Google Drive backup folder: %s') % response.text)
        data = response.json()
        self.sudo().google_folder_id = data['id']
        return data

    def action_test_connection(self):
        self.ensure_one()
        data = self._ensure_drive_folder()
        raise UserError(_('Connection successful. Folder: %s') % data.get('name'))

    def _backup_filename(self):
        self.ensure_one()
        stamp = fields.Datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        extension = 'zip' if self.backup_format == 'zip' else 'dump'
        safe_db = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in self.env.cr.dbname)
        return f'{self.filename_prefix}-{safe_db}-{stamp}.{extension}'

    def _create_backup_file(self, path):
        self.ensure_one()
        with open(path, 'wb') as stream:
            service_db.dump_db(self.env.cr.dbname, stream, backup_format=self.backup_format)

    def _upload_resumable(self, path, filename):
        self.ensure_one()
        headers = self._google_headers()
        file_size = os.path.getsize(path)
        folder = self._ensure_drive_folder()
        metadata = {
            'name': filename,
            'parents': [folder['id']],
            'appProperties': {
                'odoo_backup': 'true',
                'odoo_database': self.env.cr.dbname,
                'odoo_config_id': str(self.id),
            },
        }
        init_headers = dict(headers)
        init_headers.update({
            'Content-Type': 'application/json; charset=UTF-8',
            'X-Upload-Content-Type': 'application/octet-stream',
            'X-Upload-Content-Length': str(file_size),
        })
        params = {'uploadType': 'resumable', 'supportsAllDrives': 'true'}
        init = requests.post(DRIVE_UPLOAD_URL, headers=init_headers, params=params, data=json.dumps(metadata), timeout=30)
        if not init.ok:
            raise UserError(_('Could not start Google Drive upload: %s') % init.text)
        upload_url = init.headers.get('Location')
        if not upload_url:
            raise UserError(_('Google Drive did not return a resumable upload URL.'))

        with open(path, 'rb') as backup_file:
            upload_headers = {'Content-Type': 'application/octet-stream', 'Content-Length': str(file_size)}
            uploaded = requests.put(upload_url, headers=upload_headers, data=backup_file, timeout=(30, 3600))
        if uploaded.status_code not in (200, 201):
            raise UserError(_('Google Drive upload failed: %s') % uploaded.text)
        return uploaded.json()

    def _cleanup_remote(self):
        self.ensure_one()
        if not self.retention_days:
            return
        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
        headers = self._google_headers()
        folder = self._ensure_drive_folder()
        query = f"'{folder['id']}' in parents and trashed = false and appProperties has {{ key='odoo_backup' and value='true' }} and appProperties has {{ key='odoo_config_id' and value='{self.id}' }}"
        page_token = None
        while True:
            params = {
                'q': query,
                'fields': 'nextPageToken,files(id,name,createdTime)',
                'pageSize': 100,
                'supportsAllDrives': 'true',
                'includeItemsFromAllDrives': 'true',
            }
            if page_token:
                params['pageToken'] = page_token
            response = requests.get(DRIVE_FILES_URL, headers=headers, params=params, timeout=30)
            if not response.ok:
                _logger.warning('Unable to list old Drive backups: %s', response.text)
                return
            data = response.json()
            for item in data.get('files', []):
                created = item.get('createdTime')
                if not created:
                    continue
                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00')).replace(tzinfo=None)
                if created_dt < cutoff:
                    delete = requests.delete(
                        f"{DRIVE_FILES_URL}/{item['id']}",
                        headers=headers,
                        params={'supportsAllDrives': 'true'},
                        timeout=30,
                    )
                    if not delete.ok:
                        _logger.warning('Unable to delete old Drive backup %s: %s', item.get('name'), delete.text)
            page_token = data.get('nextPageToken')
            if not page_token:
                break

    def action_backup_now(self):
        for rec in self:
            rec._run_backup()
        return True

    def _run_backup(self):
        self.ensure_one()
        if not self.google_refresh_token:
            raise UserError(_('Connect Google Drive before creating a backup.'))

        log = self.env['ellaithy.drive.backup.log'].create({
            'config_id': self.id,
            'status': 'running',
            'started_at': fields.Datetime.now(),
        })
        filename = self._backup_filename()
        suffix = '.zip' if self.backup_format == 'zip' else '.dump'
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix='odoo_backup_', suffix=suffix, delete=False) as tmp:
                temp_path = tmp.name
            self._create_backup_file(temp_path)
            file_size = os.path.getsize(temp_path)
            uploaded = self._upload_resumable(temp_path, filename)
            file_id = uploaded.get('id')
            web_link = False
            if file_id:
                response = requests.get(
                    f'{DRIVE_FILES_URL}/{file_id}',
                    headers=self._google_headers(),
                    params={'fields': 'id,name,webViewLink', 'supportsAllDrives': 'true'},
                    timeout=30,
                )
                if response.ok:
                    web_link = response.json().get('webViewLink')

            now = fields.Datetime.now()
            log.write({
                'status': 'success',
                'finished_at': now,
                'filename': filename,
                'drive_file_id': file_id,
                'drive_web_view_link': web_link,
                'size_bytes': file_size,
                'message': _('Backup created and uploaded successfully.'),
            })
            self.write({'last_backup_at': now, 'last_success_at': now, 'last_error': False})
            try:
                self._cleanup_remote()
            except Exception:
                _logger.exception('Remote retention cleanup failed for backup config %s', self.id)
            return True
        except Exception as exc:
            now = fields.Datetime.now()
            _logger.exception('Odoo Google Drive backup failed for config %s', self.id)
            log.write({
                'status': 'failed',
                'finished_at': now,
                'filename': filename,
                'message': str(exc),
            })
            self.write({'last_backup_at': now, 'last_error': str(exc)})
            if isinstance(exc, UserError):
                raise
            raise UserError(_('Backup failed: %s') % str(exc))
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    _logger.warning('Could not remove temporary backup file %s', temp_path)

    @api.model
    def _cron_run_due_backups(self):
        now = fields.Datetime.now()
        configs = self.search([
            ('active', '=', True),
            ('schedule_enabled', '=', True),
            ('google_refresh_token', '!=', False),
            '|', ('next_backup_at', '=', False), ('next_backup_at', '<=', now),
        ])
        for config in configs:
            try:
                if not config.next_backup_at:
                    config._set_next_backup(from_dt=now - timedelta(days=1))
                if config.next_backup_at and config.next_backup_at <= now:
                    try:
                        config._run_backup()
                    except Exception:
                        _logger.exception('Scheduled Google Drive backup failed for config %s', config.id)
                    finally:
                        config._set_next_backup(from_dt=now)
            except Exception:
                _logger.exception('Unable to process backup schedule for config %s', config.id)
        return True
