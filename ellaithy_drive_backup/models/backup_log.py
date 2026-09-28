from odoo import fields, models


class EllaithyDriveBackupLog(models.Model):
    _name = 'ellaithy.drive.backup.log'
    _description = 'Google Drive Backup Log'
    _order = 'started_at desc, id desc'

    config_id = fields.Many2one('ellaithy.drive.backup.config', required=True, ondelete='cascade')
    started_at = fields.Datetime(required=True, default=fields.Datetime.now)
    finished_at = fields.Datetime()
    status = fields.Selection([
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], required=True, default='running', index=True)
    filename = fields.Char()
    drive_file_id = fields.Char()
    drive_web_view_link = fields.Char()
    size_bytes = fields.Integer()
    message = fields.Text()
