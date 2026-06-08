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

        # 2. Redistribute each lead
        reassigned_count = 0
        for lead in open_leads:
            branch_id = lead.branch_name.id if lead.branch_name else False
            if not branch_id:
                _logger.warning(
                    "Lead id=%s has no branch → skipping redistribution.", lead.id)
                continue

            new_salesperson = self.env['distribute.sequence']\
                ._get_next_salesperson_for_branch(branch_id)

            if not new_salesperson:
                _logger.warning(
                    "No available salesperson for branch id=%s → "
                    "lead id=%s left unassigned.", branch_id, lead.id)
                lead.write({'user_id': False})
                lead.message_post(
                    body=_(
                        "Salesperson <b>%s</b> was archived. "
                        "No available salesperson found in branch <b>%s</b> "
                        "— opportunity left unassigned.",
                        archived_user.name,
                        lead.branch_name.branch_name,
                    )
                )
                continue

            old_name = archived_user.name
            new_name = new_salesperson.name

            lead.write({'user_id': new_salesperson.id})
            lead.message_post(
                body=_(
                    "Salesperson changed from <b>%s</b> to <b>%s</b> "
                    "because <b>%s</b> was archived (Archive & Redistribute).",
                    old_name, new_name, old_name,
                )
            )
            reassigned_count += 1
            _logger.info(
                "Lead id=%s reassigned from %s → %s",
                lead.id, old_name, new_name
            )

        # 3. Archive the user
        archived_user.write({'active': False})

        # 4. Archive the linked contact (partner) if still active
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

        # 5. Show result notification
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