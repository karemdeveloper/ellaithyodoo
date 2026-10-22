from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class CrmOpportunityPartnerSync(models.Model):
    _name = 'crm.opportunity.partner.sync'
    _description = 'CRM Opportunity Partner Salesperson Sync'
    _order = 'id asc'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='restrict', index=True)
    lead_id = fields.Many2one('crm.lead', ondelete='cascade', index=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('error', 'Error'),
    ], default='pending', required=True, index=True)
    attempts = fields.Integer(default=0)
    last_error = fields.Char()

    @api.model
    def enqueue(self, partner, user, lead=False):
        """Queue the non-critical partner.user_id synchronization."""
        if not partner or not user or partner.user_id.id == user.id:
            return False
        return self.sudo().create({
            'partner_id': partner.id,
            'user_id': user.id,
            'lead_id': lead.id if lead else False,
        })

    @api.model
    def _cron_process(self, batch_size=200):
        jobs = self.sudo().search([('state', '=', 'pending')], limit=batch_size, order='id asc')
        for job in jobs:
            try:
                with self.env.cr.savepoint():
                    partner = job.partner_id.exists()
                    user = job.user_id.exists()
                    if partner and user and user.active and partner.user_id.id != user.id:
                        partner.with_context(
                            tracking_disable=True,
                            mail_notrack=True,
                            mail_create_nosubscribe=True,
                        ).write({'user_id': user.id})
                    job.write({
                        'state': 'done',
                        'attempts': job.attempts + 1,
                        'last_error': False,
                    })
            except Exception as exc:
                _logger.exception('Partner salesperson background sync failed for job %s', job.id)
                job.write({
                    'state': 'error' if job.attempts >= 4 else 'pending',
                    'attempts': job.attempts + 1,
                    'last_error': str(exc)[:250],
                })
        return True
