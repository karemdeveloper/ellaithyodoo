from collections import defaultdict

from odoo import models, fields, _
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    branch_id = fields.Many2one(
        'res.branch', string='Branch',
        help='Branch for complaint access control')

    def action_archive_and_redistribute(self):
        """
        Archive this user (and their linked contact) and redistribute all
        their open opportunities (excluding won/lost) using the same
        round-robin distribution logic.
        """
        self.ensure_one()
        archived_user = self

        # 1. Fetch open opportunities assigned to this user
        # Use sudo() to bypass record rules — this action must access all leads
        # regardless of the calling user's branch restrictions.
        open_leads = self.env['crm.lead'].sudo().search([
            ('user_id', '=', archived_user.id),
            ('active', '=', True),
            ('probability', '<', 100),   # not won
        ])
        # Extra safety: exclude anything explicitly marked lost via stage
        open_leads = open_leads.filtered(
            lambda l: not l.stage_id.is_lost
        )

        _logger.info(
            "Archive & Redistribute: user=%s | open opportunities found=%s",
            archived_user.name, len(open_leads)
        )

        # 2. Archive the user first so the distribution below skips them.
        #    Their sales team memberships are archived too (as Odoo's own
        #    Archive action does). action_archive() is avoided on purpose:
        #    mail's override would delete every activity assigned to the user.
        self.env['crm.team.member'].sudo().search([
            ('user_id', '=', archived_user.id),
        ]).action_archive()
        archived_user.write({'active': False})

        # 3. Pick the new salesperson of every lead: one round-robin batch per
        #    branch gives the same turns as picking lead by lead, but saves
        #    the shared pointer once per branch instead of once per lead.
        Sequence = self.env['distribute.sequence']
        assignments = {}  # lead -> new salesperson (False: none available)
        for branch, branch_leads in open_leads.grouped('branch_name').items():
            if not branch:
                _logger.warning(
                    "Leads %s have no branch → skipping redistribution.",
                    branch_leads.ids)
                continue
            salespersons = Sequence._get_next_salespersons_for_branch(
                branch.id, len(branch_leads))
            if not salespersons:
                _logger.warning(
                    "No available salesperson for branch id=%s → "
                    "leads %s left unassigned.", branch.id, branch_leads.ids)
                salespersons = [False] * len(branch_leads)
            assignments.update(zip(branch_leads, salespersons))

        # 4. Apply the assignments in batches (one write per salesperson).
        #    crm.lead.write() syncs the new salesperson to the customer.
        old_name = archived_user.name
        lead_batches = defaultdict(lambda: self.env['crm.lead'].sudo())
        customer_owner = {}  # customer -> salesperson of their last lead
        bodies = {}
        reassigned_count = 0
        for lead in open_leads:
            if lead not in assignments:
                continue
            new_salesperson = assignments[lead]
            lead_batches[new_salesperson] |= lead
            if lead.partner_id:
                customer_owner[lead.partner_id] = new_salesperson
            if not new_salesperson:
                bodies[lead.id] = _(
                    "Salesperson <b>%s</b> was archived. "
                    "No available salesperson found in branch <b>%s</b> "
                    "— opportunity left unassigned.",
                    old_name,
                    lead.branch_name.branch_name,
                )
                continue

            bodies[lead.id] = _(
                "Salesperson changed from <b>%s</b> to <b>%s</b> "
                "because <b>%s</b> was archived (Archive & Redistribute).",
                old_name, new_salesperson.name, old_name,
            )
            reassigned_count += 1
            _logger.info(
                "Lead id=%s reassigned from %s → %s",
                lead.id, old_name, new_salesperson.name
            )

        for new_salesperson, leads in lead_batches.items():
            leads.write({'user_id': new_salesperson.id if new_salesperson else False})
        # Lead by lead, a customer with several leads kept the salesperson of
        # the last one; batched writes may leave another one, so restore it.
        for customer, new_salesperson in customer_owner.items():
            owner_id = new_salesperson.id if new_salesperson else False
            if customer.user_id.id != owner_id:
                customer.with_context(mail_auto_subscribe_no_notify=True).write(
                    {'user_id': owner_id})
        # Same chatter note as message_post, created in one batch
        open_leads.browse(list(bodies))._message_log_batch(bodies=bodies)

        # 5. Clear the archived salesperson from their remaining customers so
        #    their next opportunity goes through the distribution logic.
        remaining_partners = self.env['res.partner'].sudo().search([
            ('user_id', '=', archived_user.id),
        ])
        remaining_partners.write({'user_id': False})
        _logger.info(
            "Salesperson %s cleared from %s remaining customer(s).",
            archived_user.name, len(remaining_partners)
        )

        # 6. Archive the linked contact (partner) if still active
        if archived_user.partner_id and archived_user.partner_id.active:
            archived_user.partner_id.sudo().write({'active': False})
            _logger.info(
                "Partner '%s' (id=%s) archived alongside user.",
                archived_user.partner_id.name, archived_user.partner_id.id
            )

        _logger.info(
            "User %s archived. Opportunities reassigned: %s / %s",
            archived_user.name, reassigned_count, len(open_leads)
        )

        # 7. Show result notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Archive & Redistribute'),
                'message': _(
                    '%s archived. %s opportunity(ies) redistributed.',
                    archived_user.name, reassigned_count
                ),
                'type': 'success',
                'sticky': False,
            }
        }