from odoo import models, fields, api


class MailActivitySchedule(models.TransientModel):
    _inherit = 'mail.activity.schedule'

    # Override the date_deadline field to use Datetime instead of Date
    date_deadline = fields.Datetime(
        string='Due Date',
        default=fields.Datetime.now
    )
